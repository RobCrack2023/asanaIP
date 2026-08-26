from django.db import migrations, models


def copy_cost_into_amount(apps, schema_editor):
    """Existing products were priced straight in pesos.

    cost_amount is the new source of truth for the landed cost, so it has to
    start out holding what cost already says — otherwise the first save would
    recompute every catalog cost down to zero.
    """
    Product = apps.get_model('core', 'Product')
    ProductPriceEntry = apps.get_model('core', 'ProductPriceEntry')

    Product.objects.update(cost_amount=models.F('cost'))
    ProductPriceEntry.objects.update(cost_amount=models.F('cost'))


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_currencies_and_exchange_rates'),
    ]

    operations = [
        migrations.RunPython(copy_cost_into_amount, migrations.RunPython.noop),
    ]
