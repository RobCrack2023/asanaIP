from decimal import Decimal

from rest_framework.test import APITestCase

from .models import (
    Area, Client, ExchangeRate, Opportunity, OpportunityActivity, Organization,
    Product, ProductPriceEntry, Quote, QuoteItem, Team, User,
)


class CrossTenantCrmTests(APITestCase):
    """The CRM endpoints must not accept relations owned by another company."""

    def setUp(self):
        self.org_a = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.org_b = Organization.objects.create(name='Empresa B', slug='empresa-b')

        self.user_a = User.objects.create_user(
            username='vendedor_a', password='secret', organization=self.org_a, is_sales=True
        )
        self.user_b = User.objects.create_user(
            username='vendedor_b', password='secret', organization=self.org_b, is_sales=True
        )

        self.client_a = Client.objects.create(organization=self.org_a, name='Cliente A')
        self.client_b = Client.objects.create(organization=self.org_b, name='Cliente B')

        self.opportunity_b = Opportunity.objects.create(
            organization=self.org_b, client=self.client_b, name='Oportunidad ajena'
        )

        self.client.login(username='vendedor_a', password='secret')

    def test_cannot_attach_quote_to_another_orgs_opportunity(self):
        response = self.client.post('/api/quotes/', {
            'opportunity': self.opportunity_b.id,
            'items': [{'description': 'Servicio', 'quantity': 1, 'unit_price': 1000}],
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('opportunity', response.data)
        self.assertFalse(Quote.objects.filter(opportunity=self.opportunity_b).exists())

    def test_cannot_create_opportunity_for_another_orgs_client(self):
        response = self.client.post('/api/opportunities/', {
            'client': self.client_b.id,
            'name': 'Intento cruzado',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('client', response.data)
        self.assertFalse(Opportunity.objects.filter(name='Intento cruzado').exists())

    def test_cannot_assign_another_orgs_user_as_owner(self):
        opportunity = Opportunity.objects.create(
            organization=self.org_a, client=self.client_a, name='Propia'
        )

        response = self.client.patch(
            f'/api/opportunities/{opportunity.id}/', {'owner': self.user_b.id}, format='json'
        )

        self.assertEqual(response.status_code, 400)
        opportunity.refresh_from_db()
        self.assertIsNone(opportunity.owner)

    def test_own_organization_still_works(self):
        create = self.client.post('/api/opportunities/', {
            'client': self.client_a.id,
            'name': 'Oportunidad propia',
        }, format='json')
        self.assertEqual(create.status_code, 201)

        quote = self.client.post('/api/quotes/', {
            'opportunity': create.data['id'],
            'items': [{'description': 'Servicio', 'quantity': 2, 'unit_price': 1500}],
        }, format='json')
        self.assertEqual(quote.status_code, 201)
        self.assertEqual(str(quote.data['subtotal']), '3000.00')
        self.assertEqual(str(quote.data['total_amount']), '3570.00')


class OpportunityTimelineTests(APITestCase):
    """Stage moves are recorded automatically; notes are posted by the team."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', first_name='Vera', last_name='Soto',
            organization=self.org, is_sales=True,
        )
        self.client_record = Client.objects.create(organization=self.org, name='Cliente A')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=self.client_record, name='Planta nueva',
        )
        self.client.login(username='vendedor', password='secret')

    def test_stage_change_is_recorded_with_author_and_stages(self):
        response = self.client.patch(
            f'/api/opportunities/{self.opportunity.id}/', {'stage': 'negociacion'}, format='json'
        )
        self.assertEqual(response.status_code, 200)

        activity = self.opportunity.activities.get()
        self.assertEqual(activity.kind, OpportunityActivity.Kind.STAGE_CHANGE)
        self.assertEqual(activity.from_stage, 'prospecto')
        self.assertEqual(activity.to_stage, 'negociacion')
        self.assertEqual(activity.author, self.user)

    def test_editing_other_fields_does_not_create_an_entry(self):
        self.client.patch(
            f'/api/opportunities/{self.opportunity.id}/',
            {'estimated_amount': '4500000'}, format='json',
        )
        self.assertEqual(self.opportunity.activities.count(), 0)

    def test_marking_lost_records_the_reason(self):
        self.client.post(
            f'/api/opportunities/{self.opportunity.id}/mark_lost/',
            {'reason': 'Precio fuera de presupuesto'}, format='json',
        )
        activity = self.opportunity.activities.get()
        self.assertEqual(activity.kind, OpportunityActivity.Kind.LOST)
        self.assertEqual(activity.body, 'Precio fuera de presupuesto')
        self.assertEqual(activity.to_stage, 'perdida')

    def test_marking_won_records_the_project(self):
        area = Area.objects.create(organization=self.org, name='Ingeniería')
        team = Team.objects.create(area=area, name='Montaje')

        response = self.client.post(
            f'/api/opportunities/{self.opportunity.id}/mark_won/',
            {'team_id': team.id}, format='json',
        )
        self.assertEqual(response.status_code, 200)

        activity = self.opportunity.activities.get()
        self.assertEqual(activity.kind, OpportunityActivity.Kind.WON)
        self.assertIn('Montaje', activity.body)

    def test_can_post_a_note(self):
        response = self.client.post('/api/opportunity-activities/', {
            'opportunity': self.opportunity.id,
            'kind': 'call',
            'body': 'Llamé a Rodrigo, pide revisar el alcance.',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['author_name'], 'Vera Soto')
        self.assertFalse(response.data['is_system'])

    def test_cannot_fake_a_stage_change(self):
        response = self.client.post('/api/opportunity-activities/', {
            'opportunity': self.opportunity.id,
            'kind': 'stage_change',
            'body': 'Movida inventada',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('kind', response.data)

    def test_system_entries_cannot_be_deleted(self):
        self.client.patch(
            f'/api/opportunities/{self.opportunity.id}/', {'stage': 'negociacion'}, format='json'
        )
        activity = self.opportunity.activities.get()

        response = self.client.delete(f'/api/opportunity-activities/{activity.id}/')

        self.assertEqual(response.status_code, 400)
        self.assertTrue(self.opportunity.activities.filter(pk=activity.pk).exists())


class QuoteTests(APITestCase):
    """Totals are derived from the items; numbering runs per company."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.client_record = Client.objects.create(organization=self.org, name='Cliente A')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=self.client_record, name='Planta nueva',
        )
        self.product = Product.objects.create(
            organization=self.org, name='Bomba centrífuga', sku='BC-1', unit_price=Decimal('850000'),
        )
        self.client.login(username='vendedor', password='secret')

    def _post_quote(self, items, **extra):
        return self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id, 'items': items, **extra,
        }, format='json')

    def test_totals_are_computed_from_items_with_tax(self):
        response = self._post_quote([
            {'description': 'Bomba', 'quantity': 2, 'unit_price': '100000'},
            {'description': 'Montaje', 'quantity': 1, 'unit_price': '50000'},
        ])

        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data['subtotal']), '250000.00')
        self.assertEqual(str(response.data['tax_amount']), '47500.00')
        self.assertEqual(str(response.data['total_amount']), '297500.00')

    def test_discount_is_applied_per_item(self):
        response = self._post_quote([
            {'description': 'Bomba', 'quantity': 2, 'unit_price': '100000', 'discount_percent': '10'},
        ])

        self.assertEqual(str(response.data['subtotal']), '180000.00')
        self.assertEqual(str(response.data['items'][0]['subtotal']), '180000.00')

    def test_client_cannot_dictate_the_total(self):
        response = self._post_quote(
            [{'description': 'Bomba', 'quantity': 1, 'unit_price': '100000'}],
            total_amount='1',
        )

        self.assertEqual(str(response.data['total_amount']), '119000.00')

    def test_tax_rate_is_configurable_and_stored(self):
        response = self._post_quote(
            [{'description': 'Servicio exento', 'quantity': 1, 'unit_price': '100000'}],
            tax_rate='0',
        )

        self.assertEqual(str(response.data['tax_amount']), '0.00')
        self.assertEqual(str(response.data['total_amount']), '100000.00')

    def test_numbers_run_sequentially_per_organization(self):
        first = self._post_quote([{'description': 'A', 'quantity': 1, 'unit_price': '1000'}])
        second = self._post_quote([{'description': 'B', 'quantity': 1, 'unit_price': '1000'}])

        self.assertEqual(first.data['number'], 1)
        self.assertEqual(second.data['number'], 2)
        self.assertEqual(second.data['reference'], 'Cotización N° 2')

    def test_deleting_a_quote_does_not_reuse_its_number(self):
        first = self._post_quote([{'description': 'A', 'quantity': 1, 'unit_price': '1000'}])
        self.client.delete(f"/api/quotes/{first.data['id']}/")

        second = self._post_quote([{'description': 'B', 'quantity': 1, 'unit_price': '1000'}])

        self.assertEqual(second.data['number'], 2)

    def test_item_can_point_at_a_catalog_product(self):
        response = self._post_quote([{
            'product': self.product.id, 'description': 'Bomba centrífuga',
            'quantity': 1, 'unit_price': '850000',
        }])

        self.assertEqual(response.data['items'][0]['product'], self.product.id)
        self.assertEqual(self.product.quote_items.count(), 1)

    def test_editing_the_catalog_does_not_rewrite_a_sent_quote(self):
        self._post_quote([{
            'product': self.product.id, 'description': 'Bomba centrífuga',
            'quantity': 1, 'unit_price': '850000',
        }])

        self.product.name = 'Bomba centrífuga XL'
        self.product.unit_price = Decimal('990000')
        self.product.save()

        item = QuoteItem.objects.get()
        self.assertEqual(item.description, 'Bomba centrífuga')
        self.assertEqual(item.unit_price, Decimal('850000'))

    def test_updating_items_restates_the_totals(self):
        created = self._post_quote([{'description': 'A', 'quantity': 1, 'unit_price': '100000'}])

        response = self.client.patch(f"/api/quotes/{created.data['id']}/", {
            'items': [{'description': 'A', 'quantity': 3, 'unit_price': '100000'}],
        }, format='json')

        self.assertEqual(str(response.data['subtotal']), '300000.00')
        self.assertEqual(QuoteItem.objects.count(), 1)

    def test_validity_cannot_precede_the_issue_date(self):
        response = self._post_quote(
            [{'description': 'A', 'quantity': 1, 'unit_price': '1000'}],
            issue_date='2026-08-20', valid_until='2026-08-10',
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn('valid_until', response.data)

    def test_rejects_a_zero_quantity(self):
        response = self._post_quote([{'description': 'A', 'quantity': 0, 'unit_price': '1000'}])
        self.assertEqual(response.status_code, 400)

    def test_cannot_quote_another_orgs_product(self):
        other_org = Organization.objects.create(name='Empresa B', slug='empresa-b')
        foreign = Product.objects.create(organization=other_org, name='Ajeno', unit_price=1)

        response = self._post_quote([{
            'product': foreign.id, 'description': 'Ajeno', 'quantity': 1, 'unit_price': '1000',
        }])

        self.assertEqual(response.status_code, 400)


class ProductCostHistoryTests(APITestCase):
    """The catalog carries both sides of the deal, and remembers every change."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', first_name='Vera', last_name='Soto',
            organization=self.org, is_sales=True,
        )
        self.client.login(username='vendedor', password='secret')

    def _create(self, **extra):
        payload = {'name': 'Cerco perimetral 5x5', 'cost_amount': '900000',
                   'default_margin': '1.8', 'supplier': 'Prodalam'}
        payload.update(extra)
        return self.client.post('/api/products/', payload, format='json')

    def test_the_price_follows_from_the_cost_and_the_margin(self):
        """900.000 at a margin of 1.8 prices at 2.520.000, as the sheet does."""
        response = self._create()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data['unit_price']), '2520000.00')
        self.assertEqual(str(response.data['margin']), '1.8000')
        self.assertEqual(str(response.data['unit_profit']), '1620000.00')

    def test_a_price_sent_by_the_client_is_ignored(self):
        response = self._create(unit_price='1')

        self.assertEqual(str(response.data['unit_price']), '2520000.00')

    def test_changing_the_margin_restates_the_price(self):
        created = self._create()

        updated = self.client.patch(f"/api/products/{created.data['id']}/",
                                    {'default_margin': '1.0'}, format='json')

        self.assertEqual(str(updated.data['unit_price']), '1800000.00')

    def test_margin_is_null_without_a_cost(self):
        response = self._create(cost_amount='0')
        self.assertIsNone(response.data['margin'])

    def test_creating_a_product_opens_its_history(self):
        created = self._create()

        history = self.client.get(f"/api/products/{created.data['id']}/price_history/")
        self.assertEqual(len(history.data), 1)
        self.assertEqual(str(history.data[0]['cost']), '900000.00')
        self.assertEqual(history.data[0]['recorded_by_name'], 'Vera Soto')

    def test_a_cost_change_is_recorded(self):
        created = self._create()

        self.client.patch(f"/api/products/{created.data['id']}/",
                          {'cost_amount': '990000'}, format='json')

        history = self.client.get(f"/api/products/{created.data['id']}/price_history/").data
        self.assertEqual(len(history), 2)
        # Newest first.
        self.assertEqual(str(history[0]['cost']), '990000.00')
        self.assertEqual(str(history[1]['cost']), '900000.00')

    def test_changing_the_supplier_is_recorded(self):
        created = self._create()

        self.client.patch(f"/api/products/{created.data['id']}/", {'supplier': 'Jano'}, format='json')

        history = self.client.get(f"/api/products/{created.data['id']}/price_history/").data
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]['supplier'], 'Jano')

    def test_renaming_does_not_pollute_the_history(self):
        created = self._create()

        self.client.patch(f"/api/products/{created.data['id']}/",
                          {'name': 'Cerco perimetral 5x5 reforzado'}, format='json')

        history = self.client.get(f"/api/products/{created.data['id']}/price_history/").data
        self.assertEqual(len(history), 1)

    def test_history_entry_reports_the_margin_of_its_moment(self):
        created = self._create()
        entry = Product.objects.get(pk=created.data['id']).price_history.first()

        self.assertEqual(str(entry.margin), '1.8000')
        self.assertEqual(ProductPriceEntry.objects.count(), 1)


class QuoteProfitTests(APITestCase):
    """A quote reports what it costs, not only what it charges."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        client_record = Client.objects.create(organization=self.org, name='AES')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=client_record, name='Estación Solar Oriente',
        )
        self.client.login(username='vendedor', password='secret')

    def _post_quote(self, items, **extra):
        return self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id, 'items': items, **extra,
        }, format='json')

    def test_cost_and_profit_roll_up_from_the_items(self):
        """Two lines lifted from the AES evaluación: cerco 5x5 and torre de 3 metros."""
        response = self._post_quote([
            {'description': 'Cerco perimetral 5x5', 'quantity': 2,
             'unit_cost': '900000', 'margin': '1.8'},
            {'description': 'Torre 3 metros', 'quantity': 2,
             'unit_cost': '400000', 'margin': '1.0'},
        ])

        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data['subtotal']), '6640000.00')
        self.assertEqual(str(response.data['total_cost']), '2600000.00')
        self.assertEqual(str(response.data['total_profit']), '4040000.00')
        self.assertEqual(str(response.data['margin']), '1.5538')

    def test_a_discount_eats_into_the_margin(self):
        full = self._post_quote([
            {'description': 'Cerco', 'quantity': 1, 'unit_cost': '900000', 'margin': '1.8'},
        ])
        discounted = self._post_quote([
            {'description': 'Cerco', 'quantity': 1, 'unit_cost': '900000',
             'margin': '1.8', 'discount_percent': '20'},
        ])

        self.assertEqual(str(full.data['margin']), '1.8000')
        self.assertEqual(str(discounted.data['margin']), '1.2400')
        self.assertEqual(str(discounted.data['total_profit']), '1116000.00')

    def test_margin_is_null_when_nothing_is_costed(self):
        response = self._post_quote([
            {'description': 'Servicio', 'quantity': 1, 'unit_price': '100000'},
        ])

        self.assertIsNone(response.data['margin'])
        self.assertEqual(str(response.data['total_cost']), '0.00')

    def test_profit_ignores_tax(self):
        """VAT is collected for the state, so it must not inflate the profit."""
        response = self._post_quote([
            {'description': 'Cerco', 'quantity': 1, 'unit_cost': '900000', 'margin': '1.8'},
        ], tax_rate='19')

        self.assertEqual(str(response.data['tax_amount']), '478800.00')
        self.assertEqual(str(response.data['total_amount']), '2998800.00')
        self.assertEqual(str(response.data['total_profit']), '1620000.00')

    def test_editing_the_catalog_does_not_restate_a_quoted_cost(self):
        product = Product.objects.create(
            organization=self.org, name='Cerco', cost_amount=900000, cost=900000,
            default_margin=Decimal('1.8'), unit_price=2520000,
        )
        self._post_quote([{
            'product': product.id, 'description': 'Cerco', 'quantity': 1,
            'unit_cost': '900000', 'margin': '1.8',
        }])

        product.cost = 990000
        product.save()

        item = QuoteItem.objects.get()
        self.assertEqual(item.unit_cost, Decimal('900000'))


class ExchangeRateTests(APITestCase):
    """Imported costs land in pesos through the company's rate table."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.client.login(username='vendedor', password='secret')

    def _set_rates(self, uf='35800', usd='950', eur='980', date='2026-08-25'):
        return self.client.post('/api/exchange-rates/', {
            'date': date, 'uf': uf, 'usd': usd, 'eur': eur,
        }, format='json')

    def _create_product(self, **extra):
        payload = {'name': 'Datalogger CR1000X', 'default_margin': '0.3'}
        payload.update(extra)
        return self.client.post('/api/products/', payload, format='json')

    def test_a_ddp_cost_ignores_the_import_multiplier(self):
        """AES sheet row 15: USD 2.817,5 at 950 DDP is 2.676.625 — the 1,1 is not applied.

        Under DDP the supplier already covers freight and duties.
        """
        self._set_rates()

        response = self._create_product(
            currency='USD', cost_amount='2817.5', incoterm='DDP', import_multiplier='1.1',
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data['cost']), '2676625.00')
        self.assertEqual(str(response.data['cost_rate']), '950.00')

    def test_a_cif_cost_adds_the_import_multiplier(self):
        """AES sheet row 17: EUR 1.733,8 at 980 CIF with 1,1 is 1.869.036,40."""
        self._set_rates()

        response = self._create_product(
            name='Estación HD52.3D147', currency='EUR', cost_amount='1733.8',
            incoterm='CIF', import_multiplier='1.1',
        )

        self.assertEqual(str(response.data['cost']), '1869036.40')

    def test_the_same_purchase_costs_more_when_we_clear_customs(self):
        self._set_rates()
        ddp = self._create_product(name='A', currency='USD', cost_amount='1000',
                                   incoterm='DDP', import_multiplier='1.2')
        fob = self._create_product(name='B', currency='USD', cost_amount='1000',
                                   incoterm='FOB', import_multiplier='1.2')

        self.assertEqual(str(ddp.data['cost']), '950000.00')
        self.assertEqual(str(fob.data['cost']), '1140000.00')

    def test_a_peso_cost_is_taken_as_is(self):
        self._set_rates()

        response = self._create_product(name='Cerco', currency='CLP', cost_amount='900000')

        self.assertEqual(str(response.data['cost']), '900000.00')
        self.assertEqual(str(response.data['cost_rate']), '1.00')

    def test_costing_in_a_currency_with_no_rate_is_refused(self):
        response = self._create_product(currency='USD', cost_amount='2817.5')

        self.assertEqual(response.status_code, 400)
        self.assertIn('currency', response.data)

    def test_a_moved_rate_marks_the_cost_stale_without_changing_it(self):
        self._set_rates()
        created = self._create_product(currency='USD', cost_amount='2817.5')

        self._set_rates(usd='1000', date='2026-08-26')

        product = self.client.get(f"/api/products/{created.data['id']}/").data
        self.assertTrue(product['cost_is_stale'])
        # Still the old figure: rates are never applied behind the user's back.
        self.assertEqual(str(product['cost']), '2676625.00')

    def test_refreshing_restates_the_cost_and_records_it(self):
        self._set_rates()
        created = self._create_product(currency='USD', cost_amount='2817.5')
        self._set_rates(usd='1000', date='2026-08-26')

        refresh = self.client.post('/api/products/refresh_costs/', {}, format='json')

        self.assertEqual(refresh.data['updated'], 1)
        product = self.client.get(f"/api/products/{created.data['id']}/").data
        self.assertEqual(str(product['cost']), '2817500.00')
        self.assertFalse(product['cost_is_stale'])

        history = self.client.get(f"/api/products/{created.data['id']}/price_history/").data
        self.assertEqual(len(history), 2)
        self.assertIn('1000', history[0]['note'])
        self.assertEqual(str(history[1]['cost_rate']), '950.00')

    def test_refreshing_leaves_peso_products_alone(self):
        self._set_rates()
        self._create_product(name='Cerco', currency='CLP', cost_amount='900000')
        self._set_rates(usd='1000', date='2026-08-26')

        refresh = self.client.post('/api/products/refresh_costs/', {}, format='json')

        self.assertEqual(refresh.data['updated'], 0)

    def test_refreshing_without_rates_is_refused(self):
        response = self.client.post('/api/products/refresh_costs/', {}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_recording_the_same_day_twice_overwrites_it(self):
        self._set_rates()
        corrected = self._set_rates(usd='999')

        self.assertEqual(corrected.status_code, 201)
        self.assertEqual(str(corrected.data['usd']), '999.00')
        self.assertEqual(ExchangeRate.objects.count(), 1)

    def test_current_returns_the_most_recent_day(self):
        self._set_rates(usd='950', date='2026-08-25')
        self._set_rates(usd='1000', date='2026-08-26')

        current = self.client.get('/api/exchange-rates/current/')

        self.assertEqual(str(current.data['usd']), '1000.00')

    def test_current_is_empty_before_any_rate_is_loaded(self):
        self.assertIsNone(self.client.get('/api/exchange-rates/current/').data)

    def test_rates_are_scoped_to_the_organization(self):
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        ExchangeRate.objects.create(organization=other, date='2026-08-25', usd=Decimal('9999'))

        self.assertEqual(len(self.client.get('/api/exchange-rates/').data), 0)


class QuoteCurrencyTests(APITestCase):
    """A quote keeps the rates it was issued with, and can be read in any of them."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        client_record = Client.objects.create(organization=self.org, name='AES')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=client_record, name='Estación Solar Oriente',
        )
        self.client.login(username='vendedor', password='secret')

    def _quote(self, **extra):
        return self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id,
            'items': [{'description': 'Cerco', 'quantity': 1,
                       'unit_cost': '900000', 'margin': '1.8'}],
            **extra,
        }, format='json')

    def test_rates_are_stamped_at_issue_time(self):
        ExchangeRate.objects.create(organization=self.org, date='2026-08-25',
                                    uf=Decimal('35800'), usd=Decimal('950'), eur=Decimal('980'))

        response = self._quote()

        self.assertEqual(str(response.data['rate_usd']), '950.00')
        self.assertEqual(str(response.data['rate_uf']), '35800.00')

    def test_a_later_rate_move_does_not_restate_an_issued_quote(self):
        ExchangeRate.objects.create(organization=self.org, date='2026-08-25', usd=Decimal('950'))
        created = self._quote()

        ExchangeRate.objects.create(organization=self.org, date='2026-08-26', usd=Decimal('1100'))

        quote = self.client.get(f"/api/quotes/{created.data['id']}/").data
        self.assertEqual(str(quote['rate_usd']), '950.00')

    def test_display_currency_exposes_its_divisor(self):
        ExchangeRate.objects.create(organization=self.org, date='2026-08-25',
                                    uf=Decimal('35800'), usd=Decimal('950'))

        response = self._quote(display_currency='USD')

        self.assertEqual(response.data['display_currency'], 'USD')
        self.assertEqual(str(response.data['display_rate']), '950.00')
        # Amounts stay in pesos; only the presentation changes.
        self.assertEqual(str(response.data['subtotal']), '2520000.00')

    def test_pesos_need_no_conversion(self):
        response = self._quote()
        self.assertEqual(str(response.data['display_rate']), '1.00')

    def test_a_missing_rate_never_blanks_the_document(self):
        """Asking for USD with no dollar loaded must not divide by zero."""
        response = self._quote(display_currency='USD')

        self.assertEqual(str(response.data['display_rate']), '1.00')


class QuoteLinePricingTests(APITestCase):
    """Margin prices the line; the catalog only supplies the starting point."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        User.objects.create_user(username='vendedor', password='secret',
                                 organization=self.org, is_sales=True)
        client_record = Client.objects.create(organization=self.org, name='AES')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=client_record, name='Estación',
        )
        self.client.login(username='vendedor', password='secret')

    def _post(self, items):
        return self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id, 'items': items,
        }, format='json')

    def test_the_line_margin_can_differ_from_the_catalog(self):
        """A tight deal is quoted at a lower margin without touching the catalog."""
        product = Product.objects.create(
            organization=self.org, name='Cerco', cost_amount=900000, cost=900000,
            default_margin=Decimal('1.8'), unit_price=2520000,
        )

        response = self._post([{
            'product': product.id, 'description': 'Cerco', 'quantity': 1,
            'unit_cost': '900000', 'margin': '1.2',
        }])

        self.assertEqual(str(response.data['items'][0]['unit_price']), '1980000.00')
        product.refresh_from_db()
        self.assertEqual(product.default_margin, Decimal('1.8'))

    def test_a_line_without_cost_states_its_price(self):
        """Not everything quoted is bought — a service can just have a price."""
        response = self._post([
            {'description': 'Asesoría en terreno', 'quantity': 1, 'unit_price': '450000'},
        ])

        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data['items'][0]['unit_price']), '450000.00')
        self.assertIsNone(response.data['items'][0]['effective_margin'])

    def test_a_costed_line_must_say_its_margin(self):
        response = self._post([
            {'description': 'Cerco', 'quantity': 1, 'unit_cost': '900000'},
        ])

        self.assertEqual(response.status_code, 400)

    def test_a_line_with_neither_cost_nor_price_is_refused(self):
        response = self._post([{'description': 'Vacío', 'quantity': 1}])

        self.assertEqual(response.status_code, 400)

    def test_effective_margin_reports_what_the_discount_left(self):
        response = self._post([{
            'description': 'Cerco', 'quantity': 1, 'unit_cost': '900000',
            'margin': '1.8', 'discount_percent': '20',
        }])

        item = response.data['items'][0]
        # Quoted at 1.8, but 20% off the price leaves 1.24 actually earned.
        self.assertEqual(str(item['margin']), '1.8000')
        self.assertEqual(str(item['effective_margin']), '1.2400')
