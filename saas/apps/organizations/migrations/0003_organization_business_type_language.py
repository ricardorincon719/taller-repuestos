from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0002_alter_membership_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="business_type",
            field=models.CharField(
                choices=[
                    ("auto_repair", "Taller / Oficina"),
                    ("office", "Oficina administrativa"),
                    ("personal_business", "Negocio personal"),
                    ("services", "Servicios profesionales"),
                    ("retail", "Comercio"),
                    ("other", "Otro negocio"),
                ],
                default="auto_repair",
                max_length=40,
                verbose_name="tipo de negocio",
            ),
        ),
        migrations.AddField(
            model_name="organization",
            name="language",
            field=models.CharField(
                choices=[
                    ("es", "Español"),
                    ("pt-br", "Português do Brasil"),
                ],
                default="es",
                max_length=10,
                verbose_name="idioma",
            ),
        ),
    ]
