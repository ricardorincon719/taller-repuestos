from django.db import migrations


def normalize_snapshot_business_type(apps, schema_editor):
    Quote = apps.get_model("quotes", "Quote")
    for quote in Quote.objects.exclude(issue_snapshot={}).select_related(
        "organization"
    ).iterator():
        snapshot = quote.issue_snapshot
        organization = snapshot.setdefault("organization", {})
        organization["business_type"] = quote.organization.business_type
        quote.issue_snapshot = snapshot
        quote.save(update_fields=("issue_snapshot",))


class Migration(migrations.Migration):
    dependencies = [
        ("quotes", "0005_secure_public_quote_links"),
    ]

    operations = [
        migrations.RunPython(normalize_snapshot_business_type, migrations.RunPython.noop),
    ]
