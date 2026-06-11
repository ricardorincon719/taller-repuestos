import uuid

from django.db import migrations, models


def populate_share_tokens(apps, schema_editor):
    Quote = apps.get_model("quotes", "Quote")
    for quote in Quote.objects.filter(share_token__isnull=True).iterator():
        quote.share_token = uuid.uuid4()
        quote.save(update_fields=("share_token",))


class Migration(migrations.Migration):
    dependencies = [
        ("quotes", "0002_quote_legacy_id_quote_legacy_source_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="quote",
            name="share_token",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(populate_share_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="quote",
            name="share_token",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
