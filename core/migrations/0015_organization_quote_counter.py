from django.db import migrations, models
from django.db.models import Max


def seed_counters(apps, schema_editor):
    """Start each counter above the highest number already issued."""
    Organization = apps.get_model('core', 'Organization')
    for organization in Organization.objects.all():
        highest = organization.quotes.aggregate(Max('number'))['number__max'] or 0
        if highest:
            organization.quote_counter = highest
            organization.save(update_fields=['quote_counter'])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_migrate_quote_line_items'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='quote_counter',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.RunPython(seed_counters, migrations.RunPython.noop),
    ]
