from datetime import timedelta
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from .models import (
    Area, Asset, Client, ExchangeRate, ExpenseConcept, ExpenseRate, ExpenseSheet, Opportunity,
    OpportunityActivity, Organization, Product, ProductPriceEntry, Project, ProjectExpense,
    Quote, QuoteItem, Team, User,
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


class ClientFacingQuoteTests(APITestCase):
    """What leaves the company, and what must never leave with it."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.admin = User.objects.create_user(
            username='jefa', password='secret', organization=self.org, is_staff=True,
        )
        self.client.login(username='vendedor', password='secret')

        client = Client.objects.create(organization=self.org, name='Agrícola Los Nogales')
        opportunity = Opportunity.objects.create(
            organization=self.org, client=client, name='Estación meteorológica',
        )
        response = self.client.post('/api/quotes/', {
            'opportunity': opportunity.id,
            'issue_date': '2026-08-26',
            'items': [{
                'description': 'Datalogger CR310', 'quantity': 1,
                'unit_cost': '1457536', 'margin': '0.35',
            }],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.quote = Quote.objects.get(pk=response.data['id'])

    def test_the_client_payload_carries_no_cost_margin_or_profit(self):
        response = self.client.get(f'/api/quotes/{self.quote.id}/client-view/')

        quote = response.data['quote']
        self.assertNotIn('total_cost', quote)
        self.assertNotIn('total_profit', quote)
        self.assertNotIn('margin', quote)
        for field in ('unit_cost', 'margin', 'cost_subtotal', 'profit', 'effective_margin'):
            self.assertNotIn(field, quote['items'][0])

    def test_the_client_payload_still_carries_the_prices(self):
        response = self.client.get(f'/api/quotes/{self.quote.id}/client-view/')

        quote = response.data['quote']
        self.assertEqual(str(quote['items'][0]['unit_price']), '1967673.60')
        self.assertEqual(str(quote['total_amount']), '2341531.58')
        self.assertEqual(quote['client_name'], 'Agrícola Los Nogales')

    def test_the_pdf_never_prints_the_landed_cost(self):
        """The figure 1.457.536 is in the quote; it must not be in the file."""
        response = self.client.get(f'/api/quotes/{self.quote.id}/pdf/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        # Text is compressed inside the PDF, so assert on the source instead:
        # nothing but ClientQuoteSerializer can reach the builder.
        self.assertNotIn('unit_cost', str(response.content))

    def test_another_company_cannot_reach_the_pdf(self):
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        User.objects.create_user(username='intruso', password='secret',
                                 organization=other, is_sales=True)
        self.client.logout()
        self.client.login(username='intruso', password='secret')

        response = self.client.get(f'/api/quotes/{self.quote.id}/pdf/')

        self.assertEqual(response.status_code, 404)

    def test_the_template_is_created_on_first_read(self):
        response = self.client.get('/api/quote-template/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['document_title'], 'COTIZACIÓN')
        # Printing the quote's own notes is opt-in: they may be internal.
        self.assertFalse(response.data['show_quote_notes'])

    def test_sales_may_read_the_template_but_not_change_it(self):
        response = self.client.patch('/api/quote-template/',
                                     {'company_name': 'Otra'}, format='json')

        self.assertEqual(response.status_code, 403)

    def test_staff_may_change_the_template(self):
        self.client.logout()
        self.client.login(username='jefa', password='secret')

        response = self.client.patch('/api/quote-template/', {
            'company_name': 'Ingeniería y Proyectos LTDA', 'accent_color': '#1a3f6b',
        }, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['company_name'], 'Ingeniería y Proyectos LTDA')
        self.assertEqual(response.data['accent_color'], '#1A3F6B')

    def test_a_broken_colour_is_refused(self):
        self.client.logout()
        self.client.login(username='jefa', password='secret')

        response = self.client.patch('/api/quote-template/',
                                     {'accent_color': 'azul'}, format='json')

        self.assertEqual(response.status_code, 400)


class CostCategoryTests(APITestCase):
    """Equipment, own labour and operating expenses, told apart."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.client.login(username='vendedor', password='secret')

        client = Client.objects.create(organization=self.org, name='Agrícola Los Nogales')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=client, name='Estación meteorológica',
        )

    def _product(self, **extra):
        payload = {'name': 'Ficha', 'default_margin': '0.3', 'cost_amount': '100000'}
        payload.update(extra)
        response = self.client.post('/api/products/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def _quote(self, items):
        return self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id, 'issue_date': '2026-08-26', 'items': items,
        }, format='json')

    def test_a_catalog_entry_is_equipment_unless_it_says_otherwise(self):
        product = self._product(name='Datalogger CR310')

        self.assertEqual(product['category'], 'equipo')
        self.assertEqual(product['category_display'], 'Equipo o material')

    def test_an_expense_is_a_catalog_entry_like_any_other(self):
        """The Cálculo sheet keeps "Gastos operacionales" in the same list."""
        product = self._product(name='Gastos operacionales para instalación',
                                category='gasto', default_margin='0.2')

        self.assertEqual(product['category'], 'gasto')
        # Priced the same way: cost marked up, price derived.
        self.assertEqual(str(product['unit_price']), '120000.00')

    def test_a_quoted_line_inherits_the_category_of_its_product(self):
        product = self._product(name='Flete a terreno', category='flete')

        response = self._quote([{
            'product': product['id'], 'description': 'Flete a terreno',
            'quantity': 1, 'unit_cost': '100000', 'margin': '0.2',
        }])

        self.assertEqual(response.data['items'][0]['category'], 'flete')

    def test_a_line_may_override_the_category_it_inherited(self):
        product = self._product(name='Flete a terreno', category='flete')

        response = self._quote([{
            'product': product['id'], 'description': 'Flete a terreno',
            'category': 'gasto', 'quantity': 1, 'unit_cost': '100000', 'margin': '0.2',
        }])

        self.assertEqual(response.data['items'][0]['category'], 'gasto')

    def test_the_breakdown_splits_cost_sale_and_margin_by_category(self):
        """The reading the spreadsheet cannot give: a blended margin, opened up."""
        response = self._quote([
            {'description': 'Datalogger', 'category': 'equipo',
             'quantity': 1, 'unit_cost': '1000000', 'margin': '0.3'},
            {'description': 'Instalación', 'category': 'servicio',
             'quantity': 1, 'unit_cost': '500000', 'margin': '1.8'},
            {'description': 'Gastos operacionales', 'category': 'gasto',
             'quantity': 1, 'unit_cost': '500000', 'margin': '0.2'},
        ])

        rows = {row['category']: row for row in response.data['category_totals']}
        self.assertEqual(list(rows), ['equipo', 'servicio', 'gasto'])
        self.assertEqual(str(rows['equipo']['cost']), '1000000.00')
        self.assertEqual(str(rows['equipo']['margin']), '0.3000')
        self.assertEqual(str(rows['servicio']['margin']), '1.8000')
        self.assertEqual(str(rows['gasto']['margin']), '0.2000')
        # Half the cost is equipment, a quarter each for labour and expenses.
        self.assertEqual(str(rows['equipo']['cost_share']), '0.5000')
        self.assertEqual(str(rows['gasto']['cost_share']), '0.2500')
        # And the blended margin the totals report is none of the three.
        self.assertEqual(str(response.data['margin']), '0.6500')

    def test_the_breakdown_only_lists_categories_actually_used(self):
        response = self._quote([
            {'description': 'Datalogger', 'quantity': 1, 'unit_cost': '1000000', 'margin': '0.3'},
        ])

        self.assertEqual([row['category'] for row in response.data['category_totals']],
                         ['equipo'])

    def test_the_category_stays_out_of_the_client_document(self):
        """How the company classifies its costs is not the client's business."""
        created = self._quote([
            {'description': 'Gastos operacionales', 'category': 'gasto',
             'quantity': 1, 'unit_cost': '500000', 'margin': '0.2'},
        ])

        response = self.client.get(f'/api/quotes/{created.data["id"]}/client-view/')

        quote = response.data['quote']
        self.assertNotIn('category_totals', quote)
        self.assertNotIn('category', quote['items'][0])

    def test_reclassifying_the_catalog_leaves_sent_quotes_alone(self):
        product = self._product(name='Flete a terreno', category='flete')
        created = self._quote([{
            'product': product['id'], 'description': 'Flete a terreno',
            'quantity': 1, 'unit_cost': '100000', 'margin': '0.2',
        }])

        self.client.patch(f'/api/products/{product["id"]}/',
                          {'category': 'gasto'}, format='json')

        response = self.client.get(f'/api/quotes/{created.data["id"]}/')
        self.assertEqual(response.data['items'][0]['category'], 'flete')


class ExpenseSheetTests(APITestCase):
    """The breakdown behind an operating-expense figure."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.client.login(username='vendedor', password='secret')

        client = Client.objects.create(organization=self.org, name='Agrícola Los Nogales')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=client, name='Estación meteorológica',
        )

    def _sheet(self, lines=None, **extra):
        payload = {
            'opportunity': self.opportunity.id,
            'name': 'Gastos instalación',
            'lines': lines if lines is not None else [
                {'block': 'viaje', 'description': 'Alojamiento',
                 'unit_amount': '55000', 'quantity': '2', 'days': '3'},
                {'block': 'operaciones', 'description': 'Prevencionista',
                 'unit_amount': '180000', 'quantity': '1', 'days': '2'},
                {'block': 'flete', 'description': 'Flete a terreno',
                 'unit_amount': '450000', 'quantity': '1', 'days': '1'},
            ],
        }
        payload.update(extra)
        return self.client.post('/api/expense-sheets/', payload, format='json')

    def test_a_line_costs_unit_times_quantity_times_days(self):
        """55.000 la noche, dos personas, tres noches."""
        response = self._sheet(lines=[{
            'block': 'viaje', 'description': 'Alojamiento',
            'unit_amount': '55000', 'quantity': '2', 'days': '3',
        }])

        self.assertEqual(response.status_code, 201)
        self.assertEqual(str(response.data['lines'][0]['subtotal']), '330000.00')

    def test_a_one_off_expense_needs_no_days(self):
        """Days default to one, so a flat charge is not multiplied by anything."""
        response = self._sheet(lines=[{
            'block': 'flete', 'description': 'Flete a terreno', 'unit_amount': '450000',
        }])

        self.assertEqual(str(response.data['lines'][0]['subtotal']), '450000.00')

    def test_the_sheet_totals_by_block(self):
        response = self._sheet()

        rows = {row['block']: row for row in response.data['block_totals']}
        self.assertEqual([row['block'] for row in response.data['block_totals']],
                         ['viaje', 'flete', 'operaciones'])
        self.assertEqual(str(rows['viaje']['total']), '330000.00')
        self.assertEqual(str(rows['operaciones']['total']), '360000.00')
        self.assertEqual(str(response.data['total']), '1140000.00')

    def test_an_empty_block_is_left_out_rather_than_shown_as_zero(self):
        """No Flete lines means freight was not costed, not that it is free."""
        response = self._sheet(lines=[{
            'block': 'viaje', 'description': 'Viáticos', 'unit_amount': '35000',
        }])

        self.assertEqual([row['block'] for row in response.data['block_totals']], ['viaje'])

    def test_each_block_says_what_quote_line_it_becomes(self):
        """Cálculo writes them as separate rows, not one lump."""
        response = self._sheet()

        rows = {row['block']: row for row in response.data['block_totals']}
        self.assertEqual(rows['viaje']['quote_description'], 'Gastos de viaje')
        self.assertEqual(rows['viaje']['category'], 'gasto')
        self.assertEqual(rows['flete']['quote_description'], 'Flete')
        self.assertEqual(rows['flete']['category'], 'flete')
        self.assertEqual(rows['operaciones']['category'], 'gasto')

    def test_a_new_sheet_can_start_from_an_old_one(self):
        source = self._sheet()

        response = self.client.post('/api/expense-sheets/', {
            'opportunity': self.opportunity.id,
            'name': 'Próximo proyecto',
            'copy_from': source.data['id'],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data['lines']), 3)
        self.assertEqual(str(response.data['total']), '1140000.00')
        # A copy, not a shared reference: editing one must not touch the other.
        self.assertNotEqual(response.data['lines'][0]['id'], source.data['lines'][0]['id'])

    def test_editing_a_sheet_replaces_its_lines(self):
        sheet = self._sheet()

        response = self.client.patch(f'/api/expense-sheets/{sheet.data["id"]}/', {
            'lines': [{'block': 'viaje', 'description': 'Pasajes',
                       'unit_amount': '85000', 'quantity': '2', 'days': '2'}],
        }, format='json')

        self.assertEqual(len(response.data['lines']), 1)
        self.assertEqual(str(response.data['total']), '340000.00')

    def test_a_line_with_zero_days_is_refused(self):
        response = self._sheet(lines=[{
            'block': 'viaje', 'description': 'Alojamiento',
            'unit_amount': '55000', 'quantity': '1', 'days': '0',
        }])

        self.assertEqual(response.status_code, 400)

    def test_a_sheet_cannot_be_hung_on_another_company_opportunity(self):
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        client_b = Client.objects.create(organization=other, name='Otro')
        theirs = Opportunity.objects.create(organization=other, client=client_b, name='Suya')

        response = self._sheet(opportunity=theirs.id)

        self.assertEqual(response.status_code, 400)

    def test_another_company_cannot_read_the_sheet(self):
        sheet = self._sheet()
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        User.objects.create_user(username='intruso', password='secret',
                                 organization=other, is_sales=True)
        self.client.logout()
        self.client.login(username='intruso', password='secret')

        response = self.client.get(f'/api/expense-sheets/{sheet.data["id"]}/')

        self.assertEqual(response.status_code, 404)

    def test_deleting_the_sheet_leaves_the_quote_it_produced_alone(self):
        """The quote copied a number; it does not read the sheet."""
        sheet = self._sheet()
        quote = self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id,
            'items': [{'description': 'Gastos operacionales', 'category': 'gasto',
                       'quantity': 1, 'unit_cost': '360000', 'margin': '0.2'}],
        }, format='json')

        self.client.delete(f'/api/expense-sheets/{sheet.data["id"]}/')

        response = self.client.get(f'/api/quotes/{quote.data["id"]}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(str(response.data['items'][0]['unit_cost']), '360000.00')
        self.assertFalse(ExpenseSheet.objects.exists())


class ProjectExpenseTests(APITestCase):
    """What execution actually cost, against what the deal promised."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org,
            is_sales=True, first_name='Ana', last_name='Soto',
        )
        self.area = Area.objects.create(name='Proyectos', organization=self.org)
        self.team = Team.objects.create(name='Terreno', area=self.area)
        self.client.login(username='vendedor', password='secret')

        client = Client.objects.create(organization=self.org, name='Agrícola Los Nogales')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=client, name='Estación meteorológica',
        )
        # Equipos 1.000.000 al 30% y gastos 500.000 al 20%: costo 1.500.000,
        # venta 1.900.000.
        self.quote = self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id,
            'status': 'approved',
            'items': [
                {'description': 'Datalogger', 'category': 'equipo',
                 'quantity': 1, 'unit_cost': '1000000', 'margin': '0.3'},
                {'description': 'Gastos operacionales', 'category': 'gasto',
                 'quantity': 1, 'unit_cost': '500000', 'margin': '0.2'},
            ],
        }, format='json').data

    def _win(self):
        response = self.client.post(f'/api/opportunities/{self.opportunity.id}/mark_won/',
                                    {'team_id': self.team.id}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        return Project.objects.get(pk=response.data['project'])

    def _expense(self, **extra):
        payload = {'project': self.project.id, 'description': 'Neumático camioneta',
                   'category': 'flete', 'amount': '185000'}
        payload.update(extra)
        return self.client.post('/api/project-expenses/', payload, format='json')

    def test_winning_stamps_what_the_deal_promised(self):
        project = self._win()

        self.assertEqual(str(project.budget_cost), '1500000.00')
        self.assertEqual(str(project.budget_sale), '1900000.00')
        self.assertEqual([row['category'] for row in project.budget_categories],
                         ['equipo', 'gasto'])

    def test_editing_the_quote_afterwards_does_not_move_the_yardstick(self):
        """The project was sold on a document; changing it later proves nothing."""
        project = self._win()

        self.client.patch(f'/api/quotes/{self.quote["id"]}/', {
            'items': [{'description': 'Datalogger', 'category': 'equipo',
                       'quantity': 1, 'unit_cost': '9000000', 'margin': '0.3'}],
        }, format='json')

        project.refresh_from_db()
        self.assertEqual(str(project.budget_cost), '1500000.00')

    def test_the_latest_quote_is_used_when_none_is_approved(self):
        Quote.objects.update(status='sent')
        self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id,
            'items': [{'description': 'Revisada', 'quantity': 1,
                       'unit_cost': '2000000', 'margin': '0.5'}],
        }, format='json')

        project = self._win()

        self.assertEqual(str(project.budget_cost), '2000000.00')

    def test_an_expense_lands_on_top_of_the_budget_not_instead_of_it(self):
        """Nobody re-enters the datalogger they already quoted."""
        self.project = self._win()
        self._expense(amount='185000')
        self._expense(description='Noche extra', category='gasto', amount='55000')

        summary = self.client.get(f'/api/projects/{self.project.id}/costs/').data

        self.assertEqual(str(summary['extra_cost']), '240000.00')
        self.assertEqual(str(summary['real_cost']), '1740000.00')

    def test_the_margin_falls_while_the_sale_stays_put(self):
        self.project = self._win()
        self._expense(amount='240000')

        summary = self.client.get(f'/api/projects/{self.project.id}/costs/').data

        # Quoted 1.500.000 of cost against a sale of 1.900.000.
        self.assertEqual(str(summary['quoted_margin']), '0.2667')
        self.assertEqual(str(summary['quoted_profit']), '400000.00')
        # The client accepted a document, so the 240.000 comes out of profit.
        self.assertEqual(str(summary['real_margin']), '0.0920')
        self.assertEqual(str(summary['real_profit']), '160000.00')
        self.assertEqual(str(summary['budget_sale']), '1900000.00')

    def test_costs_are_compared_on_the_categories_the_deal_was_priced_with(self):
        self.project = self._win()
        self._expense(description='Noche extra', category='gasto', amount='180000')

        summary = self.client.get(f'/api/projects/{self.project.id}/costs/').data

        rows = {row['category']: row for row in summary['by_category']}
        self.assertEqual(str(rows['gasto']['budget']), '500000.00')
        self.assertEqual(str(rows['gasto']['extra']), '180000.00')
        self.assertEqual(str(rows['gasto']['real']), '680000.00')
        # A category with nothing extra still shows what it was budgeted at.
        self.assertEqual(str(rows['equipo']['extra']), '0.00')
        self.assertEqual(str(rows['equipo']['real']), '1000000.00')

    def test_an_unbudgeted_category_still_appears(self):
        """A tyre nobody quoted for is exactly what this has to surface."""
        self.project = self._win()
        self._expense(category='flete', amount='185000')

        summary = self.client.get(f'/api/projects/{self.project.id}/costs/').data

        rows = {row['category']: row for row in summary['by_category']}
        self.assertEqual(str(rows['flete']['budget']), '0.00')
        self.assertEqual(str(rows['flete']['extra']), '185000.00')
        self.assertEqual(str(rows['flete']['real']), '185000.00')

    def test_an_expense_of_zero_is_refused(self):
        self.project = self._win()

        response = self._expense(amount='0')

        self.assertEqual(response.status_code, 400)

    def test_the_expense_records_who_entered_it(self):
        self.project = self._win()

        response = self._expense()

        self.assertEqual(response.data['recorded_by_name'], 'Ana Soto')

    def test_a_team_member_cannot_read_what_the_project_earns(self):
        """Everyone on the team can open the project; the margin is not theirs."""
        self.project = self._win()
        member = User.objects.create_user(username='tecnico', password='secret',
                                          organization=self.org)
        self.team.members.add(member)
        self.client.logout()
        self.client.login(username='tecnico', password='secret')

        response = self.client.get(f'/api/projects/{self.project.id}/costs/')

        self.assertEqual(response.status_code, 403)

    def test_an_expense_cannot_be_hung_on_another_company_project(self):
        self.project = self._win()
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        their_area = Area.objects.create(name='Suya', organization=other)
        their_team = Team.objects.create(name='Suyo', area=their_area)
        theirs = Project.objects.create(name='Proyecto ajeno', team=their_team)

        response = self._expense(project=theirs.id)

        self.assertEqual(response.status_code, 400)


class ExpenseConceptTests(APITestCase):
    """Concepts hold no price, only the values they have been seen at."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.client.login(username='vendedor', password='secret')

        client = Client.objects.create(organization=self.org, name='Agrícola Los Nogales')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=client, name='Estación meteorológica',
        )
        area = Area.objects.create(name='Proyectos', organization=self.org)
        team = Team.objects.create(name='Terreno', area=area)
        self.project = Project.objects.create(name='Estación', team=team)

    # ── helpers ────────────────────────────────────────────────────────────
    def _days_ago(self, days):
        return (timezone.localdate() - timedelta(days=days)).isoformat()

    def _concept(self, **extra):
        payload = {'name': 'Alojamiento', 'block': 'viaje', 'unit': 'noche'}
        payload.update(extra)
        response = self.client.post('/api/expense-concepts/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def _rate(self, concept_id, amount, date=None, source='cotizado', **extra):
        payload = {'unit_amount': amount, 'source': source}
        if date:
            payload['date'] = date
        payload.update(extra)
        return self.client.post(f'/api/expense-concepts/{concept_id}/rates/', payload,
                                format='json')

    def _sheet(self, lines, **extra):
        payload = {'opportunity': self.opportunity.id, 'name': 'Gastos', 'lines': lines}
        payload.update(extra)
        return self.client.post('/api/expense-sheets/', payload, format='json')

    def _line(self, concept_id, amount, **extra):
        line = {'block': 'viaje', 'description': 'Alojamiento', 'concept': concept_id,
                'unit_amount': amount, 'quantity': '2', 'days': '3'}
        line.update(extra)
        return line

    def _expense(self, **extra):
        payload = {'project': self.project.id, 'description': 'Arriendo camioneta',
                   'category': 'gasto', 'amount': '260000'}
        payload.update(extra)
        return self.client.post('/api/project-expenses/', payload, format='json')

    def _detail(self, concept_id):
        return self.client.get(f'/api/expense-concepts/{concept_id}/').data

    # ── the concept itself ─────────────────────────────────────────────────
    def test_a_new_concept_knows_no_value_and_is_not_stale(self):
        concept = self._concept()

        self.assertIsNone(concept['latest_amount'])
        self.assertIsNone(concept['age_days'])
        # No value is a different state from an old value.
        self.assertFalse(concept['is_stale'])

    def test_a_concept_can_be_created_already_knowing_a_value(self):
        concept = self._concept(initial_amount='55000')

        self.assertEqual(concept['latest_amount'], '55000.00')
        self.assertEqual(concept['latest_source'], 'estimado')
        self.assertEqual(concept['age_days'], 0)

    def test_names_are_unique_per_company_ignoring_case(self):
        self._concept(name='Alojamiento')

        response = self.client.post('/api/expense-concepts/',
                                    {'name': 'alojamiento', 'block': 'viaje'}, format='json')

        self.assertEqual(response.status_code, 400)

    def test_another_company_may_reuse_the_name(self):
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        ExpenseConcept.objects.create(organization=other, name='Alojamiento')

        concept = self._concept(name='Alojamiento')

        self.assertEqual(concept['name'], 'Alojamiento')

    # ── the value history ──────────────────────────────────────────────────
    def test_the_latest_value_is_the_newest_by_date_not_by_entry(self):
        """A receipt typed a month late must not overwrite a newer quote."""
        concept = self._concept()
        self._rate(concept['id'], '60000', date=self._days_ago(0))
        self._rate(concept['id'], '40000', date=self._days_ago(100))

        detail = self._detail(concept['id'])

        self.assertEqual(detail['latest_amount'], '60000.00')

    def test_a_value_goes_stale_after_ninety_days_and_is_flagged_not_replaced(self):
        concept = self._concept()
        self._rate(concept['id'], '55000', date=self._days_ago(91))

        detail = self._detail(concept['id'])

        self.assertTrue(detail['is_stale'])
        self.assertEqual(detail['age_days'], 91)
        self.assertEqual(detail['stale_after_days'], 90)
        # Still offered: stale means "check it", never "forget it".
        self.assertEqual(detail['latest_amount'], '55000.00')

    def test_ninety_days_exactly_is_still_fresh(self):
        concept = self._concept()
        self._rate(concept['id'], '55000', date=self._days_ago(90))

        self.assertFalse(self._detail(concept['id'])['is_stale'])

    def test_a_hand_entered_value_cannot_claim_to_be_real(self):
        """Real keeps meaning money actually paid only if nobody can type it."""
        concept = self._concept()

        response = self._rate(concept['id'], '55000', source='real')

        self.assertEqual(response.status_code, 400)

    def test_the_history_lists_every_value_newest_first(self):
        concept = self._concept()
        self._rate(concept['id'], '50000', date=self._days_ago(60))
        self._rate(concept['id'], '60000', date=self._days_ago(5))
        self._rate(concept['id'], '55000', date=self._days_ago(30))

        response = self.client.get(f'/api/expense-concepts/{concept["id"]}/rates/')

        self.assertEqual([r['unit_amount'] for r in response.data],
                         ['60000.00', '55000.00', '50000.00'])

    # ── values typed into an expense sheet ─────────────────────────────────
    def test_a_sheet_line_remembers_the_concept_it_came_from(self):
        concept = self._concept()

        response = self._sheet([self._line(concept['id'], '55000')])

        self.assertEqual(response.data['lines'][0]['concept'], concept['id'])

    def test_a_price_typed_in_a_sheet_feeds_the_history(self):
        concept = self._concept()

        self._sheet([self._line(concept['id'], '58000')])

        rates = ExpenseRate.objects.filter(concept_id=concept['id'])
        self.assertEqual(rates.count(), 1)
        self.assertEqual(str(rates[0].unit_amount), '58000.00')
        self.assertEqual(rates[0].source, 'estimado')

    def test_typing_the_value_already_on_file_adds_nothing(self):
        concept = self._concept(initial_amount='55000')

        self._sheet([self._line(concept['id'], '55000')])

        self.assertEqual(ExpenseRate.objects.filter(concept_id=concept['id']).count(), 1)

    def test_typing_a_different_value_becomes_the_new_reference(self):
        concept = self._concept(initial_amount='55000')

        self._sheet([self._line(concept['id'], '61000')])

        self.assertEqual(ExpenseRate.objects.filter(concept_id=concept['id']).count(), 2)
        self.assertEqual(self._detail(concept['id'])['latest_amount'], '61000.00')

    def test_retyping_a_stale_value_confirms_it_and_starts_the_age_over(self):
        concept = self._concept()
        self._rate(concept['id'], '55000', date=self._days_ago(120))
        self.assertTrue(self._detail(concept['id'])['is_stale'])

        self._sheet([self._line(concept['id'], '55000')])

        detail = self._detail(concept['id'])
        self.assertFalse(detail['is_stale'])
        self.assertEqual(detail['age_days'], 0)

    def test_a_blank_value_is_not_a_value(self):
        concept = self._concept()

        self._sheet([self._line(concept['id'], '0')])

        self.assertFalse(ExpenseRate.objects.filter(concept_id=concept['id']).exists())

    def test_saving_the_same_sheet_twice_does_not_duplicate_the_value(self):
        concept = self._concept()
        sheet = self._sheet([self._line(concept['id'], '58000')])

        self.client.patch(f'/api/expense-sheets/{sheet.data["id"]}/',
                          {'lines': [self._line(concept['id'], '58000')]}, format='json')

        self.assertEqual(ExpenseRate.objects.filter(concept_id=concept['id']).count(), 1)

    def test_a_line_cannot_use_another_company_concept(self):
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        theirs = ExpenseConcept.objects.create(organization=other, name='Suyo')

        response = self._sheet([self._line(theirs.id, '55000')])

        self.assertEqual(response.status_code, 400)

    def test_copying_a_sheet_keeps_the_concepts(self):
        concept = self._concept()
        source = self._sheet([self._line(concept['id'], '55000')])

        response = self.client.post('/api/expense-sheets/', {
            'opportunity': self.opportunity.id, 'name': 'Copia',
            'copy_from': source.data['id'],
        }, format='json')

        self.assertEqual(response.data['lines'][0]['concept'], concept['id'])

    # ── values learned from real expenses ──────────────────────────────────
    def test_a_real_expense_teaches_the_concept_what_a_unit_cost(self):
        """260.000 for four days of the pickup is 65.000 a day."""
        concept = self._concept(name='Arriendo de camioneta', block='operaciones', unit='día')

        self._expense(concept=concept['id'], units='4', supplier='Rent a Car Maule',
                      incurred_on=self._days_ago(10))

        rate = ExpenseRate.objects.get(concept_id=concept['id'])
        self.assertEqual(str(rate.unit_amount), '65000.00')
        self.assertEqual(rate.source, 'real')
        self.assertEqual(rate.supplier, 'Rent a Car Maule')
        self.assertEqual(rate.date.isoformat(), self._days_ago(10))

    def test_the_value_is_dated_when_the_money_was_spent_not_when_typed(self):
        concept = self._concept(name='Arriendo de camioneta', block='operaciones')
        self._rate(concept['id'], '70000', date=self._days_ago(0))

        self._expense(concept=concept['id'], units='4', incurred_on=self._days_ago(200))

        # The old receipt joins the history but does not displace the newer quote.
        self.assertEqual(ExpenseRate.objects.filter(concept_id=concept['id']).count(), 2)
        self.assertEqual(self._detail(concept['id'])['latest_amount'], '70000.00')

    def test_correcting_an_expense_corrects_the_value_it_taught(self):
        concept = self._concept(name='Arriendo de camioneta', block='operaciones')
        expense = self._expense(concept=concept['id'], units='4')

        self.client.patch(f'/api/project-expenses/{expense.data["id"]}/',
                          {'amount': '300000'}, format='json')

        rates = ExpenseRate.objects.filter(concept_id=concept['id'])
        self.assertEqual(rates.count(), 1)
        self.assertEqual(str(rates[0].unit_amount), '75000.00')

    def test_taking_the_concept_off_an_expense_removes_the_value_it_taught(self):
        concept = self._concept(name='Arriendo de camioneta', block='operaciones')
        expense = self._expense(concept=concept['id'], units='4')

        self.client.patch(f'/api/project-expenses/{expense.data["id"]}/',
                          {'concept': None}, format='json')

        self.assertFalse(ExpenseRate.objects.filter(concept_id=concept['id']).exists())

    def test_deleting_an_expense_removes_the_value_it_taught(self):
        """The history must not carry a price from a receipt that is gone."""
        concept = self._concept(name='Arriendo de camioneta', block='operaciones')
        expense = self._expense(concept=concept['id'], units='4')

        self.client.delete(f'/api/project-expenses/{expense.data["id"]}/')

        self.assertFalse(ExpenseRate.objects.filter(concept_id=concept['id']).exists())

    def test_an_expense_without_a_concept_leaves_no_trace_in_the_history(self):
        self._expense()

        self.assertFalse(ExpenseRate.objects.exists())

    def test_an_expense_cannot_use_another_company_concept(self):
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        theirs = ExpenseConcept.objects.create(organization=other, name='Suyo')

        response = self._expense(concept=theirs.id, units='4')

        self.assertEqual(response.status_code, 400)

    def test_units_must_be_greater_than_zero(self):
        concept = self._concept()

        response = self._expense(concept=concept['id'], units='0')

        self.assertEqual(response.status_code, 400)

    # ── housekeeping ───────────────────────────────────────────────────────
    def test_starter_loads_the_usual_concepts_without_values_and_is_safe_to_repeat(self):
        first = self.client.post('/api/expense-concepts/starter/')
        second = self.client.post('/api/expense-concepts/starter/')

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data['created'], 8)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.data['created'], 0)
        concepts = self.client.get('/api/expense-concepts/').data
        self.assertEqual(len(concepts), 8)
        # None of them has a fixed price, so none is loaded with one.
        self.assertTrue(all(c['latest_amount'] is None for c in concepts))

    def test_starter_does_not_duplicate_a_concept_that_already_exists(self):
        self._concept(name='alojamiento')

        response = self.client.post('/api/expense-concepts/starter/')

        self.assertEqual(response.data['created'], 7)

    def test_another_company_cannot_see_the_concepts(self):
        concept = self._concept()
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        User.objects.create_user(username='intruso', password='secret',
                                 organization=other, is_sales=True)
        self.client.logout()
        self.client.login(username='intruso', password='secret')

        self.assertEqual(self.client.get('/api/expense-concepts/').data, [])
        self.assertEqual(
            self.client.get(f'/api/expense-concepts/{concept["id"]}/').status_code, 404)

    def test_concepts_filter_by_block_and_by_active(self):
        self._concept(name='Alojamiento', block='viaje')
        self._concept(name='Prevencionista', block='operaciones')
        retired = self._concept(name='Antiguo', block='operaciones')
        self.client.patch(f'/api/expense-concepts/{retired["id"]}/',
                          {'is_active': False}, format='json')

        by_block = self.client.get('/api/expense-concepts/?block=operaciones').data
        active = self.client.get('/api/expense-concepts/?active=1').data

        self.assertEqual(sorted(c['name'] for c in by_block), ['Antiguo', 'Prevencionista'])
        self.assertEqual(sorted(c['name'] for c in active), ['Alojamiento', 'Prevencionista'])

    def test_deactivating_a_concept_keeps_its_history(self):
        concept = self._concept(initial_amount='55000')

        self.client.patch(f'/api/expense-concepts/{concept["id"]}/',
                          {'is_active': False}, format='json')

        self.assertEqual(ExpenseRate.objects.filter(concept_id=concept['id']).count(), 1)

    def test_deleting_a_concept_leaves_the_sheets_and_expenses_that_used_it(self):
        concept = self._concept(name='Arriendo de camioneta', block='operaciones')
        sheet = self._sheet([self._line(concept['id'], '65000')])
        expense = self._expense(concept=concept['id'], units='4')

        self.client.delete(f'/api/expense-concepts/{concept["id"]}/')

        self.assertEqual(
            self.client.get(f'/api/expense-sheets/{sheet.data["id"]}/').data['lines'][0]['concept'],
            None)
        self.assertEqual(ProjectExpense.objects.get(pk=expense.data['id']).concept_id, None)


class InternalCostLineTests(APITestCase):
    """Costs the company carries without charging for them, and never shows."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.client.login(username='vendedor', password='secret')

        client = Client.objects.create(organization=self.org, name='Cliente de Prueba S.A.')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=client, name='Mantención estación',
        )
        area = Area.objects.create(name='Proyectos', organization=self.org)
        self.team = Team.objects.create(name='Terreno', area=area)

    SALE_LINE = {'description': 'Mantención de la estación', 'category': 'servicio',
                 'quantity': 1, 'unit_cost': '1000000', 'margin': '1.0'}
    INTERNAL_LINE = {'description': 'Sueldos del equipo en terreno', 'category': 'servicio',
                     'quantity': 1, 'unit_cost': '500000', 'is_internal': True}

    def _quote(self, items, **extra):
        payload = {'opportunity': self.opportunity.id, 'issue_date': '2026-08-07',
                   'items': items}
        payload.update(extra)
        response = self.client.post('/api/quotes/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def test_an_internal_line_counts_in_the_cost_but_charges_nothing(self):
        quote = self._quote([self.SALE_LINE, self.INTERNAL_LINE])

        self.assertEqual(str(quote['total_cost']), '1500000.00')
        # Only the sale line is charged: 1.000.000 at a margin of 100%.
        self.assertEqual(str(quote['subtotal']), '2000000.00')
        internal = quote['items'][1]
        self.assertTrue(internal['is_internal'])
        self.assertEqual(str(internal['unit_price']), '0.00')
        self.assertEqual(str(internal['subtotal']), '0.00')
        self.assertIsNone(internal['margin'])

    def test_internal_costs_pull_the_blended_margin_down(self):
        without = self._quote([self.SALE_LINE])
        with_internal = self._quote([self.SALE_LINE, self.INTERNAL_LINE])

        self.assertEqual(str(without['margin']), '1.0000')
        # 2.000.000 of sale over 1.500.000 of cost.
        self.assertEqual(str(with_internal['margin']), '0.3333')

    def test_an_internal_line_drops_the_margin_price_and_discount_it_arrives_with(self):
        quote = self._quote([dict(self.INTERNAL_LINE, margin='0.5', unit_price='999999',
                                  discount_percent='10')])

        line = quote['items'][0]
        self.assertIsNone(line['margin'])
        self.assertEqual(str(line['unit_price']), '0.00')
        self.assertEqual(str(line['discount_percent']), '0.00')

    def test_an_internal_line_needs_its_cost(self):
        response = self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id,
            'items': [{'description': 'Sueldos', 'quantity': 1, 'is_internal': True}],
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_an_internal_cost_shows_in_its_category_at_minus_one_hundred_percent(self):
        quote = self._quote([self.SALE_LINE, dict(self.INTERNAL_LINE, category='gasto')])

        rows = {row['category']: row for row in quote['category_totals']}
        self.assertEqual(str(rows['gasto']['cost']), '500000.00')
        self.assertEqual(str(rows['gasto']['sale']), '0.00')
        self.assertEqual(str(rows['gasto']['margin']), '-1.0000')

    def test_the_client_never_sees_an_internal_line(self):
        quote = self._quote([self.SALE_LINE, self.INTERNAL_LINE])

        response = self.client.get(f'/api/quotes/{quote["id"]}/client-view/')

        shown = response.data['quote']
        self.assertEqual([item['description'] for item in shown['items']],
                         ['Mantención de la estación'])
        self.assertNotIn('Sueldos', str(shown))
        self.assertEqual(str(shown['subtotal']), '2000000.00')

    def test_the_pdf_still_builds_when_there_are_internal_lines(self):
        quote = self._quote([self.SALE_LINE, self.INTERNAL_LINE])

        response = self.client.get(f'/api/quotes/{quote["id"]}/pdf/')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))

    # ── a project that was already running when the deal was recorded ─────────
    def _won_ready(self):
        self._quote([self.SALE_LINE, self.INTERNAL_LINE], status='approved')
        return Opportunity.objects.get(pk=self.opportunity.pk)

    def test_the_budget_stamped_on_a_project_includes_the_internal_costs(self):
        opportunity = self._won_ready()

        project = opportunity.mark_won(team=self.team, user=self.user)

        self.assertEqual(str(project.budget_cost), '1500000.00')
        self.assertEqual(str(project.budget_sale), '2000000.00')

    def test_a_won_deal_can_adopt_a_project_that_already_exists(self):
        existing = Project.objects.create(name='Mantención ya ejecutada', team=self.team,
                                          description='Descripción propia.')
        opportunity = self._won_ready()

        project = opportunity.mark_won(user=self.user, project=existing)

        self.assertEqual(project.pk, existing.pk)
        self.assertEqual(Project.objects.count(), 1)
        opportunity.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(opportunity.project_id, existing.pk)
        self.assertEqual(opportunity.stage, 'ganada')
        self.assertEqual(str(existing.budget_cost), '1500000.00')
        # What the project already said about itself is not overwritten.
        self.assertEqual(existing.description, 'Descripción propia.')
        activity = opportunity.activities.filter(kind='won').get()
        self.assertIn('vinculado', activity.body)

    def test_an_adopted_project_gets_a_section_only_if_it_has_none(self):
        bare = Project.objects.create(name='Sin secciones', team=self.team)
        self._won_ready().mark_won(user=self.user, project=bare)
        self.assertEqual([s.name for s in bare.sections.all()], ['General'])

    def test_a_project_cannot_back_two_opportunities(self):
        existing = Project.objects.create(name='Ya ejecutada', team=self.team)
        self._won_ready().mark_won(user=self.user, project=existing)
        other = Opportunity.objects.create(
            organization=self.org, client=self.opportunity.client, name='Otra oportunidad')

        with self.assertRaises(ValueError):
            other.mark_won(user=self.user, project=existing)

    def test_winning_needs_either_a_team_or_a_project(self):
        with self.assertRaises(ValueError):
            self._won_ready().mark_won(user=self.user)


class ProvisionAndCommissionTests(APITestCase):
    """Expenses that consume an estimate, and the seller's share of the profit."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.client.login(username='vendedor', password='secret')

        self.customer = Client.objects.create(organization=self.org, name='Cliente de Prueba S.A.')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=self.customer, name='Mantención estación',
        )
        area = Area.objects.create(name='Proyectos', organization=self.org)
        self.team = Team.objects.create(name='Terreno', area=area)

    # Sale of 2.000.000 on a cost of 1.000.000, plus 500.000 of operating
    # expenses carried as an internal provision: cost 1.500.000, profit 500.000.
    SALE = {'description': 'Mantención', 'category': 'equipo', 'quantity': 1,
            'unit_cost': '1000000', 'margin': '1.0'}
    PROVISION = {'description': 'Gastos operacionales', 'category': 'gasto', 'quantity': 1,
                 'unit_cost': '500000', 'is_internal': True, 'is_provision': True}

    def _quote(self, items=None, opportunity=None, **extra):
        payload = {'opportunity': (opportunity or self.opportunity).id, 'status': 'approved',
                   'issue_date': '2026-08-07',
                   'items': items if items is not None else [self.SALE, self.PROVISION]}
        payload.update(extra)
        response = self.client.post('/api/quotes/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return response.data

    def _project(self, **quote_extra):
        self._quote(**quote_extra)
        return self.opportunity.mark_won(team=self.team, user=self.user)

    def _spend(self, project, amount, category='gasto', description='Viáticos'):
        response = self.client.post('/api/project-expenses/', {
            'project': project.id, 'description': description,
            'category': category, 'amount': amount,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)

    def _costs(self, project):
        return self.client.get(f'/api/projects/{project.id}/costs/').data

    # ── provisions ─────────────────────────────────────────────────────────
    def test_a_provision_is_counted_in_the_quote_and_in_its_category(self):
        quote = self._quote()

        self.assertEqual(str(quote['provision_total']), '500000.00')
        rows = {row['category']: row for row in quote['category_totals']}
        self.assertEqual(str(rows['gasto']['provision']), '500000.00')
        self.assertEqual(str(rows['equipo']['provision']), '0.00')

    def test_a_provision_needs_its_estimated_cost(self):
        response = self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id,
            'items': [{'description': 'Gastos', 'quantity': 1, 'unit_price': '500000',
                       'is_provision': True}],
        }, format='json')

        self.assertEqual(response.status_code, 400)

    def test_a_provision_may_also_be_charged_to_the_client(self):
        """Internal and provision are independent: some deals sell the expenses."""
        charged = dict(self.PROVISION, is_internal=False, margin='0.2')
        quote = self._quote([self.SALE, charged])

        self.assertEqual(str(quote['provision_total']), '500000.00')
        self.assertEqual(str(quote['subtotal']), '2600000.00')
        shown = self.client.get(f'/api/quotes/{quote["id"]}/client-view/').data['quote']
        self.assertEqual(len(shown['items']), 2)

    def test_winning_stamps_the_provision_on_the_project(self):
        project = self._project()

        self.assertEqual(str(project.budget_provision), '500000.00')
        gasto = [r for r in project.budget_categories if r['category'] == 'gasto'][0]
        self.assertEqual(gasto['provision'], '500000.00')

    def test_expenses_replace_the_provision_instead_of_adding_to_it(self):
        """The trip was already inside the 500.000; counting both is counting it twice."""
        project = self._project()
        self._spend(project, '185000')

        summary = self._costs(project)

        self.assertEqual(str(summary['extra_cost']), '185000.00')
        # 1.500.000 budgeted, less the 500.000 estimate, plus the 185.000 really spent.
        self.assertEqual(str(summary['real_cost']), '1185000.00')
        self.assertEqual(str(summary['provision_balance']), '315000.00')

    def test_spending_less_than_the_provision_leaves_the_margin_better_than_quoted(self):
        project = self._project()
        self._spend(project, '185000')

        summary = self._costs(project)

        self.assertGreater(summary['real_margin'], summary['quoted_margin'])
        self.assertEqual(str(summary['real_profit']), '815000.00')

    def test_spending_past_the_provision_adds_to_the_cost(self):
        """An overrun still shows: the tyre that the estimate did not cover."""
        project = self._project()
        self._spend(project, '600000')

        summary = self._costs(project)

        self.assertEqual(str(summary['real_cost']), '1600000.00')
        self.assertEqual(str(summary['provision_balance']), '-100000.00')

    def test_the_category_table_adds_up_to_the_real_cost(self):
        project = self._project()
        self._spend(project, '100000', category='gasto')
        self._spend(project, '30000', category='flete', description='Peajes')

        summary = self._costs(project)

        rows = {row['category']: row for row in summary['by_category']}
        # The estimate is replaced by what was spent in that category.
        self.assertEqual(str(rows['gasto']['budget']), '500000.00')
        self.assertEqual(str(rows['gasto']['provision']), '500000.00')
        self.assertEqual(str(rows['gasto']['real']), '100000.00')
        # An unbudgeted category still shows.
        self.assertEqual(str(rows['flete']['real']), '30000.00')
        self.assertEqual(str(rows['equipo']['real']), '1000000.00')
        self.assertEqual(sum(row['real'] for row in summary['by_category']),
                         summary['real_cost'])

    def test_a_project_quoted_without_a_provision_still_adds_expenses_on_top(self):
        other = Opportunity.objects.create(
            organization=self.org, client=self.customer, name='Sin provisión')
        self._quote([self.SALE], opportunity=other)
        project = other.mark_won(team=self.team, user=self.user)
        self._spend(project, '185000')

        summary = self._costs(project)

        self.assertEqual(str(summary['provision']), '0.00')
        self.assertEqual(str(summary['real_cost']), '1185000.00')

    # ── the seller's commission ────────────────────────────────────────────
    def test_the_commission_is_a_share_of_the_profit(self):
        quote = self._quote(commission_rate='10', commission_to='Vendedor de Prueba')

        # Profit is 2.000.000 of sale less 1.500.000 of cost.
        self.assertEqual(str(quote['total_profit']), '500000.00')
        self.assertEqual(str(quote['commission_amount']), '50000.00')
        self.assertEqual(str(quote['net_profit']), '450000.00')
        self.assertEqual(quote['commission_to'], 'Vendedor de Prueba')

    def test_the_commission_does_not_change_the_margin(self):
        """The spreadsheet shows it under the profit, so the margin keeps its meaning."""
        plain = self._quote()
        with_commission = self._quote(commission_rate='10')

        self.assertEqual(str(plain['margin']), str(with_commission['margin']))
        self.assertEqual(str(with_commission['total_cost']), '1500000.00')

    def test_a_deal_that_loses_money_owes_no_commission(self):
        quote = self._quote([dict(self.SALE, margin='0.0'), self.PROVISION],
                            commission_rate='10')

        self.assertEqual(str(quote['total_profit']), '-500000.00')
        self.assertEqual(str(quote['commission_amount']), '0.00')
        self.assertEqual(str(quote['net_profit']), '-500000.00')

    def test_the_commission_never_reaches_the_client(self):
        quote = self._quote(commission_rate='10', commission_to='Vendedor de Prueba')

        shown = self.client.get(f'/api/quotes/{quote["id"]}/client-view/').data['quote']

        self.assertNotIn('commission', str(shown))
        self.assertNotIn('Vendedor de Prueba', str(shown))
        self.assertNotIn('net_profit', shown)
        self.assertNotIn('provision', str(shown))

    def test_a_commission_rate_outside_zero_to_a_hundred_is_refused(self):
        for rate in ('150', '-5'):
            response = self.client.post('/api/quotes/', {
                'opportunity': self.opportunity.id, 'commission_rate': rate,
                'items': [self.SALE],
            }, format='json')
            self.assertEqual(response.status_code, 400, rate)

    def test_the_project_freezes_the_commission_it_was_sold_under(self):
        project = self._project(commission_rate='10', commission_to='Vendedor de Prueba')
        quote = Quote.objects.get()

        self.client.patch(f'/api/quotes/{quote.id}/', {'commission_rate': '25'}, format='json')

        project.refresh_from_db()
        self.assertEqual(str(project.commission_rate), '10.00')
        self.assertEqual(project.commission_to, 'Vendedor de Prueba')

    def test_the_commission_follows_the_real_profit(self):
        project = self._project(commission_rate='10', commission_to='Vendedor de Prueba')
        self._spend(project, '185000')

        summary = self._costs(project)

        self.assertEqual(str(summary['budget_commission']), '50000.00')
        self.assertEqual(str(summary['quoted_net_profit']), '450000.00')
        # Spent less than estimated, so the profit grows and the commission with it.
        self.assertEqual(str(summary['real_profit']), '815000.00')
        self.assertEqual(str(summary['real_commission']), '81500.00')
        self.assertEqual(str(summary['real_net_profit']), '733500.00')

    def test_an_overrun_that_erases_the_profit_erases_the_commission(self):
        project = self._project(commission_rate='10')
        self._spend(project, '2000000')

        summary = self._costs(project)

        self.assertEqual(str(summary['real_profit']), '-1000000.00')
        self.assertEqual(str(summary['real_commission']), '0.00')
        self.assertEqual(str(summary['real_net_profit']), '-1000000.00')


class ProjectClosingAndSummaryTests(APITestCase):
    """The page read when the work is over, and the books being shut."""

    def setUp(self):
        self.org = Organization.objects.create(name='Empresa A', slug='empresa-a')
        self.user = User.objects.create_user(
            username='vendedor', password='secret', organization=self.org, is_sales=True,
        )
        self.staff = User.objects.create_user(
            username='jefa', password='secret', organization=self.org, is_staff=True,
        )
        self.technician = User.objects.create_user(
            username='tecnico', password='secret', organization=self.org,
        )
        self.client.login(username='vendedor', password='secret')

        ExchangeRate.objects.create(organization=self.org, date='2026-06-25', uf=Decimal('40000'))
        self.customer = Client.objects.create(organization=self.org, name='Cliente de Prueba S.A.')
        self.opportunity = Opportunity.objects.create(
            organization=self.org, client=self.customer, name='Mantención estación',
        )
        area = Area.objects.create(name='Proyectos', organization=self.org)
        self.team = Team.objects.create(name='Terreno', area=area)
        self.team.members.add(self.technician)

        # Sale of 2.000.000 over a cost of 1.000.000, 500.000 of it a provision.
        response = self.client.post('/api/quotes/', {
            'opportunity': self.opportunity.id, 'status': 'approved',
            'issue_date': '2026-08-07', 'display_currency': 'UF',
            'commission_rate': '10', 'commission_to': 'Vendedor de Prueba',
            'items': [
                {'description': 'Mantención', 'category': 'servicio', 'quantity': 1,
                 'unit_cost': '1000000', 'margin': '1.0'},
                {'description': 'Gastos operacionales', 'category': 'gasto', 'quantity': 1,
                 'unit_cost': '500000', 'is_internal': True, 'is_provision': True},
            ],
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.project = self.opportunity.mark_won(team=self.team, user=self.user)

    # ── helpers ────────────────────────────────────────────────────────────
    def _spend(self, amount, day='2026-10-19', category='gasto', description='Viáticos',
               project=None):
        return self.client.post('/api/project-expenses/', {
            'project': (project or self.project).id, 'description': description,
            'category': category, 'amount': amount, 'incurred_on': day,
        }, format='json')

    def _summary(self, project=None):
        return self.client.get(f'/api/projects/{(project or self.project).id}/summary/')

    def _close(self, **payload):
        return self.client.post(f'/api/projects/{self.project.id}/close/', payload, format='json')

    # ── the summary ────────────────────────────────────────────────────────
    def test_the_summary_gathers_the_whole_picture(self):
        self._spend('185000', day='2026-10-19', description='Alojamiento')
        self._spend('15000', day='2026-10-21', description='Peajes', category='flete')
        self._spend('40000', day='2026-10-19', description='Cena')
        Asset.objects.create(project=self.project, name='Informe de mantención.pdf',
                             asset_type='file', uploaded_by=self.user)

        summary = self._summary().data

        self.assertEqual(summary['project']['name'], self.project.name)
        self.assertEqual(summary['project']['team'], 'Terreno')
        self.assertEqual(summary['deal']['client'], 'Cliente de Prueba S.A.')
        self.assertEqual(summary['deal']['quote']['number'], 1)
        self.assertEqual(summary['period']['days'], 3)
        self.assertEqual(str(summary['period']['from']), '2026-10-19')
        self.assertEqual(str(summary['period']['to']), '2026-10-21')
        self.assertEqual(summary['expenses']['count'], 3)
        self.assertEqual(str(summary['expenses']['total']), '240000.00')
        self.assertEqual([documento['name'] for documento in summary['documents']],
                         ['Informe de mantención.pdf'])
        self.assertEqual(summary['tasks'], {'total': 0, 'completed': 0})

    def test_the_result_is_the_same_figures_the_costs_tab_shows(self):
        self._spend('185000')

        summary = self._summary().data
        costs = self.client.get(f'/api/projects/{self.project.id}/costs/').data

        for key in ('budget_cost', 'real_cost', 'real_profit', 'real_commission',
                    'real_net_profit', 'provision_balance'):
            self.assertEqual(summary['result'][key], costs[key], key)

    def test_expenses_are_listed_by_day_in_order_and_the_largest_first(self):
        self._spend('40000', day='2026-10-20', description='Cena')
        self._spend('185000', day='2026-10-19', description='Alojamiento')
        self._spend('15000', day='2026-10-20', description='Peajes')

        expenses = self._summary().data['expenses']

        self.assertEqual([str(day['date']) for day in expenses['by_day']],
                         ['2026-10-19', '2026-10-20'])
        self.assertEqual(str(expenses['by_day'][1]['total']), '55000.00')
        self.assertEqual(expenses['by_day'][1]['count'], 2)
        self.assertEqual([item['description'] for item in expenses['largest']],
                         ['Alojamiento', 'Cena', 'Peajes'])

    def test_the_sale_reads_in_the_currency_the_quote_was_made_in(self):
        """2.000.000 pesos at 40.000 a UF is 50 UF, which is how the client reads it."""
        quote = self._summary().data['deal']['quote']

        self.assertEqual(quote['display_currency'], 'UF')
        self.assertEqual(str(quote['sale_in_display_currency']), '50.00')

    def test_a_project_with_no_deal_still_has_a_summary(self):
        bare = Project.objects.create(name='Sin trato', team=self.team)

        summary = self._summary(bare).data

        self.assertIsNone(summary['deal'])
        self.assertEqual(summary['expenses']['count'], 0)
        self.assertIsNone(summary['period']['from'])
        self.assertEqual(summary['period']['days'], 0)

    # ── closing ────────────────────────────────────────────────────────────
    def test_closing_records_the_day_the_person_and_what_was_concluded(self):
        response = self._close(closed_on='2026-10-23', notes='Se cumplió el alcance.')

        self.assertEqual(response.status_code, 200)
        project = response.data['project']
        self.assertTrue(project['is_closed'])
        self.assertEqual(str(project['closed_on']), '2026-10-23')
        self.assertEqual(project['closed_by_name'], 'vendedor')
        self.assertEqual(project['closing_notes'], 'Se cumplió el alcance.')
        costs = self.client.get(f'/api/projects/{self.project.id}/costs/').data
        self.assertTrue(costs['is_closed'])

    def test_closing_without_a_date_means_today(self):
        response = self._close()

        self.assertEqual(response.data['project']['closed_on'], timezone.localdate())

    def test_an_invalid_closing_date_is_refused(self):
        for bad in ('2026-02-31', 'ayer'):
            self.assertEqual(self._close(closed_on=bad).status_code, 400, bad)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_closed)

    def test_a_closed_project_cannot_be_closed_again(self):
        self._close()

        self.assertEqual(self._close().status_code, 400)

    def test_the_figures_do_not_change_when_the_project_closes(self):
        self._spend('185000')
        before = self._summary().data['result']

        self._close()
        after = self._summary().data['result']

        for key in ('real_cost', 'real_profit', 'real_commission', 'real_net_profit'):
            self.assertEqual(before[key], after[key], key)

    # ── the books are shut ─────────────────────────────────────────────────
    def test_a_closed_project_takes_no_new_expenses(self):
        self._close()

        response = self._spend('50000')

        self.assertEqual(response.status_code, 400)
        self.assertIn('cerrado', str(response.data))
        self.assertEqual(self.project.expenses.count(), 0)

    def test_a_closed_project_does_not_let_an_expense_be_changed_or_deleted(self):
        expense = self._spend('185000').data
        self._close()

        patched = self.client.patch(f'/api/project-expenses/{expense["id"]}/',
                                    {'amount': '1'}, format='json')
        deleted = self.client.delete(f'/api/project-expenses/{expense["id"]}/')

        self.assertEqual(patched.status_code, 400)
        self.assertEqual(deleted.status_code, 400)
        self.assertEqual(str(self.project.expenses.get().amount), '185000.00')

    def test_an_expense_cannot_be_moved_into_a_closed_project(self):
        other = Project.objects.create(name='Otro cerrado', team=self.team,
                                       closed_on=timezone.localdate())
        expense = self._spend('185000').data

        response = self.client.patch(f'/api/project-expenses/{expense["id"]}/',
                                     {'project': other.id}, format='json')

        self.assertEqual(response.status_code, 400)

    def test_reopening_lets_expenses_in_again_and_keeps_the_conclusions(self):
        self._close(notes='Conclusiones escritas.')

        reopened = self.client.post(f'/api/projects/{self.project.id}/reopen/')

        self.assertEqual(reopened.status_code, 200)
        self.assertFalse(reopened.data['project']['is_closed'])
        self.assertIsNone(reopened.data['project']['closed_on'])
        self.assertEqual(reopened.data['project']['closing_notes'], 'Conclusiones escritas.')
        self.assertEqual(self._spend('30000').status_code, 201)

    def test_an_open_project_cannot_be_reopened(self):
        response = self.client.post(f'/api/projects/{self.project.id}/reopen/')

        self.assertEqual(response.status_code, 400)

    # ── who can see and do this ────────────────────────────────────────────
    def test_the_team_that_executes_cannot_read_or_close_the_summary(self):
        self.client.logout()
        self.client.login(username='tecnico', password='secret')

        self.assertEqual(self._summary().status_code, 403)
        self.assertEqual(self._close().status_code, 403)
        self.assertEqual(
            self.client.post(f'/api/projects/{self.project.id}/reopen/').status_code, 403)

    def test_another_company_cannot_reach_the_summary(self):
        other = Organization.objects.create(name='Empresa B', slug='empresa-b')
        User.objects.create_user(username='intruso', password='secret',
                                 organization=other, is_sales=True)
        self.client.logout()
        self.client.login(username='intruso', password='secret')

        self.assertEqual(self._summary().status_code, 404)
        self.assertEqual(self._close().status_code, 404)

    def test_the_plain_project_endpoint_neither_shows_nor_accepts_the_closing(self):
        """Every member of the team reads that endpoint; the closing is not theirs."""
        self.client.logout()
        self.client.login(username='jefa', password='secret')

        shown = self.client.get(f'/api/projects/{self.project.id}/').data
        self.client.patch(f'/api/projects/{self.project.id}/',
                          {'closed_on': '2026-10-23'}, format='json')

        self.assertNotIn('closed_on', shown)
        self.assertNotIn('closing_notes', shown)
        self.project.refresh_from_db()
        self.assertFalse(self.project.is_closed)
