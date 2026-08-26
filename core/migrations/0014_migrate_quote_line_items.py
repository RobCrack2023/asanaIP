from decimal import Decimal, InvalidOperation

import django.db.models.deletion
from django.db import migrations, models


def _to_decimal(value, fallback='0'):
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(fallback)


def move_line_items_into_rows(apps, schema_editor):
    """Turn each JSON line item into a QuoteItem, then restate the totals.

    Totals were previously whatever the JSON summed to, VAT included in the
    unit prices or not at all. They are recomputed here from the items so the
    subtotal / tax / total breakdown is consistent from this point on.
    """
    Quote = apps.get_model('core', 'Quote')
    QuoteItem = apps.get_model('core', 'QuoteItem')

    for quote in Quote.objects.select_related('opportunity').all():
        quote.organization_id = quote.opportunity.organization_id

        items = quote.line_items if isinstance(quote.line_items, list) else []
        subtotal = Decimal('0')
        for order, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            quantity = _to_decimal(raw.get('quantity'), '1')
            unit_price = _to_decimal(raw.get('unit_price'))
            QuoteItem.objects.create(
                quote=quote,
                description=str(raw.get('description', ''))[:200] or 'Ítem',
                quantity=quantity,
                unit_price=unit_price,
                order=order,
            )
            subtotal += (quantity * unit_price)

        # A quote with no breakdown keeps the total that was typed by hand;
        # treat it as a net figure so the recomputed total still matches.
        if not items:
            subtotal = _to_decimal(quote.total_amount)

        quote.subtotal = subtotal.quantize(Decimal('0.01'))
        quote.tax_amount = (quote.subtotal * quote.tax_rate / Decimal('100')).quantize(Decimal('0.01'))
        quote.total_amount = quote.subtotal + quote.tax_amount
        quote.save(update_fields=['organization', 'subtotal', 'tax_amount', 'total_amount'])

    # Running numbers are assigned per company, oldest quote first.
    for organization_id in Quote.objects.values_list('organization_id', flat=True).distinct():
        quotes = Quote.objects.filter(organization_id=organization_id).order_by('created_at', 'id')
        for number, quote in enumerate(quotes, start=1):
            quote.number = number
            quote.save(update_fields=['number'])


def rebuild_line_items(apps, schema_editor):
    """Put the breakdown back into JSON so the migration can be reversed."""
    Quote = apps.get_model('core', 'Quote')
    for quote in Quote.objects.prefetch_related('items').all():
        quote.line_items = [
            {
                'description': item.description,
                'quantity': float(item.quantity),
                'unit_price': float(item.unit_price),
                'subtotal': float(item.quantity * item.unit_price),
            }
            for item in quote.items.all()
        ]
        quote.save(update_fields=['line_items'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_quoteitem_quote_totals'),
    ]

    operations = [
        migrations.RunPython(move_line_items_into_rows, rebuild_line_items),
        migrations.AlterField(
            model_name='quote',
            name='organization',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                    related_name='quotes', to='core.organization'),
        ),
        migrations.AddConstraint(
            model_name='quote',
            constraint=models.UniqueConstraint(
                condition=models.Q(('number__isnull', False)),
                fields=('organization', 'number'),
                name='unique_quote_number_per_organization',
            ),
        ),
        migrations.RemoveField(
            model_name='quote',
            name='line_items',
        ),
    ]
