from rest_framework.test import APITestCase

from .models import Client, Opportunity, Organization, Quote, User


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
            'line_items': [{'description': 'Servicio', 'quantity': 1, 'unit_price': 1000}],
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
            'line_items': [{'description': 'Servicio', 'quantity': 2, 'unit_price': 1500}],
        }, format='json')
        self.assertEqual(quote.status_code, 201)
        self.assertEqual(str(quote.data['total_amount']), '3000.00')
