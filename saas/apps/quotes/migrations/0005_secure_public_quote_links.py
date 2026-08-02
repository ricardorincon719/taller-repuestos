from django.db import migrations


def secure_public_quote_links(apps, schema_editor):
    Quote = apps.get_model("quotes", "Quote")
    Quote.objects.filter(status__in=("draft", "cancelled")).update(
        public_access_enabled=False
    )


class Migration(migrations.Migration):
    dependencies = [
        ("quotes", "0004_quote_currency_quote_is_archived_and_more"),
    ]

    operations = [
        migrations.RunPython(secure_public_quote_links, migrations.RunPython.noop),
    ]
