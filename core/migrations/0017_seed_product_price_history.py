from django.db import migrations


def seed_history(apps, schema_editor):
    """Open the history with what each existing product looks like today.

    Without this the first real edit would produce a history with a single
    entry and no "before" to compare it against.
    """
    Product = apps.get_model('core', 'Product')
    ProductPriceEntry = apps.get_model('core', 'ProductPriceEntry')

    ProductPriceEntry.objects.bulk_create([
        ProductPriceEntry(
            product=product,
            cost=product.cost,
            unit_price=product.unit_price,
            supplier=product.supplier,
            note='Precio inicial registrado al habilitar el historial.',
        )
        for product in Product.objects.all()
    ])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_product_cost_and_price_history'),
    ]

    operations = [
        migrations.RunPython(seed_history, migrations.RunPython.noop),
    ]
