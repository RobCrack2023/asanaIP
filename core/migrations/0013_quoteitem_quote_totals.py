import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    """Schema for itemized quotes.

    organization starts nullable so existing rows survive; 0014 backfills it
    and tightens the column.
    """

    dependencies = [
        ('core', '0012_opportunityactivity'),
    ]

    operations = [
        migrations.AddField(
            model_name='quote',
            name='organization',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE,
                                    related_name='quotes', to='core.organization'),
        ),
        migrations.AddField(
            model_name='quote',
            name='number',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='quote',
            name='issue_date',
            field=models.DateField(default=django.utils.timezone.localdate),
        ),
        migrations.AddField(
            model_name='quote',
            name='valid_until',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='quote',
            name='tax_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('19.00'), max_digits=5),
        ),
        migrations.AddField(
            model_name='quote',
            name='subtotal',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='quote',
            name='tax_amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name='QuoteItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False,
                                           verbose_name='ID')),
                ('description', models.CharField(max_length=200)),
                ('unit', models.CharField(blank=True, default='unidad', max_length=20)),
                ('quantity', models.DecimalField(decimal_places=2, default=1, max_digits=12)),
                ('unit_price', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('discount_percent', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('order', models.PositiveIntegerField(default=0)),
                ('product', models.ForeignKey(blank=True, null=True,
                                              on_delete=django.db.models.deletion.SET_NULL,
                                              related_name='quote_items', to='core.product')),
                ('quote', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='items', to='core.quote')),
            ],
            options={
                'ordering': ['order', 'id'],
            },
        ),
    ]
