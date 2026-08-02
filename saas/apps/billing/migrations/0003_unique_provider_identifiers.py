from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0002_subscription_past_due_since_and_more"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                fields=("provider_customer_id",),
                condition=~models.Q(provider_customer_id=""),
                name="unique_nonempty_provider_customer",
            ),
        ),
        migrations.AddConstraint(
            model_name="subscription",
            constraint=models.UniqueConstraint(
                fields=("provider_subscription_id",),
                condition=~models.Q(provider_subscription_id=""),
                name="unique_nonempty_provider_subscription",
            ),
        ),
    ]
