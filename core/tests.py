from decimal import Decimal

from rest_framework.test import APITestCase

from .models import (
    Area, Client, Opportunity, OpportunityActivity, Organization, Product, Quote,
    QuoteItem, Team, User,
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
