from decimal import Decimal

from django.db import migrations


def _markup(price, cost):
    if not cost:
        return None
    return ((Decimal(price) / Decimal(cost)) - Decimal('1')).quantize(Decimal('0.0001'))


def derive_margins_from_prices(apps, schema_editor):
    """Read the margin back out of the prices that were entered by hand.

    Price used to be typed and margin inferred; now margin is the input. The
    figures have to come out identical, so each existing product keeps the
    margin its current cost and price already imply.
    """
    Product = apps.get_model('core', 'Product')
    QuoteItem = apps.get_model('core', 'QuoteItem')

    for product in Product.objects.exclude(cost=0):
        product.default_margin = _markup(product.unit_price, product.cost)
        product.save(update_fields=['default_margin'])

    for item in QuoteItem.objects.exclude(unit_cost=0):
        item.margin = _markup(item.unit_price, item.unit_cost)
        item.save(update_fields=['margin'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0021_margin_drives_price'),
    ]

    operations = [
        migrations.RunPython(derive_margins_from_prices, migrations.RunPython.noop),
    ]
