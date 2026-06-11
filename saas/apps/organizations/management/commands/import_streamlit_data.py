import hashlib
import json
from collections import Counter
from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.accounts.services import send_password_setup_email
from apps.billing.models import Subscription
from apps.customers.models import Customer
from apps.organizations.models import Membership, Organization
from apps.quotes.models import Quote, QuoteItem


SOURCE_NAME = "streamlit-json-v1"
QUOTE_STATUS_MAP = {
    "PENDIENTE": Quote.Status.SENT,
    "APROBADO": Quote.Status.APPROVED,
    "FACTURADO": Quote.Status.INVOICED,
    "RECHAZADO": Quote.Status.REJECTED,
}


class Command(BaseCommand):
    help = "Importa usuarios y presupuestos de la versión Streamlit sin copiar contraseñas."

    def add_arguments(self, parser):
        data_dir = settings.BASE_DIR.parent / "data"
        parser.add_argument(
            "--users-file",
            type=Path,
            default=data_dir / "usuarios.json",
        )
        parser.add_argument(
            "--quotes-file",
            type=Path,
            default=data_dir / "presupuestos.json",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Valida y simula toda la importación, revirtiendo la transacción.",
        )
        parser.add_argument(
            "--send-invitations",
            action="store_true",
            help="Envía un enlace para definir contraseña a las cuentas importadas.",
        )
        parser.add_argument(
            "--legacy-trial-days",
            type=int,
            default=7,
            help="Duración histórica de la prueba usada por Streamlit.",
        )

    def handle(self, *args, **options):
        users_data = self._load_json(options["users_file"], expected_type=dict)
        quotes_data = self._load_json(options["quotes_file"], expected_type=list)
        self._validate_sources(users_data, quotes_data)

        stats = Counter()
        invitation_users = []
        quotes_by_owner = {}
        for raw_quote in quotes_data:
            owner = self._normalize_email(raw_quote["usuario_creador"])
            quotes_by_owner.setdefault(owner, []).append(raw_quote)

        with transaction.atomic():
            for source_key, raw_user in users_data.items():
                email = self._normalize_email(raw_user.get("email") or source_key)
                user, user_created = self._get_or_create_user(email, raw_user)
                stats["users_created" if user_created else "users_existing"] += 1

                organization, organization_created = self._get_or_create_organization(
                    user, raw_user
                )
                stats[
                    "organizations_created" if organization_created else "organizations_existing"
                ] += 1
                self._ensure_subscription(organization, raw_user, options["legacy_trial_days"])

                if user.is_active and not user.has_usable_password():
                    invitation_users.append(user)

                self._import_quotes(
                    organization=organization,
                    user=user,
                    raw_quotes=quotes_by_owner.get(email, []),
                    stats=stats,
                )

            if options["dry_run"]:
                transaction.set_rollback(True)

        if options["send_invitations"] and not options["dry_run"]:
            for user in invitation_users:
                send_password_setup_email(user)
                stats["invitations_sent"] += 1

        mode = "SIMULACIÓN" if options["dry_run"] else "IMPORTACIÓN"
        self.stdout.write(self.style.SUCCESS(f"{mode} COMPLETADA"))
        for key in (
            "users_created",
            "users_existing",
            "organizations_created",
            "organizations_existing",
            "customers_created",
            "customers_existing",
            "quotes_created",
            "quotes_skipped",
            "items_created",
            "invitations_sent",
        ):
            self.stdout.write(f"{key}: {stats[key]}")

    def _load_json(self, path, expected_type):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CommandError(f"No existe el archivo: {path}") from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"JSON inválido en {path}: {exc}") from exc
        if not isinstance(data, expected_type):
            raise CommandError(
                f"Formato inválido en {path}: se esperaba {expected_type.__name__}."
            )
        return data

    def _validate_sources(self, users_data, quotes_data):
        known_users = set()
        for source_key, raw_user in users_data.items():
            if not isinstance(raw_user, dict):
                raise CommandError(f"Usuario inválido en la clave {source_key!r}.")
            email = self._normalize_email(raw_user.get("email") or source_key)
            try:
                validate_email(email)
            except ValidationError as exc:
                raise CommandError("El archivo contiene un email de usuario inválido.") from exc
            if email in known_users:
                raise CommandError("El archivo contiene usuarios duplicados por email.")
            known_users.add(email)

        seen_quote_ids = set()
        for position, raw_quote in enumerate(quotes_data, start=1):
            if not isinstance(raw_quote, dict):
                raise CommandError(f"Presupuesto inválido en posición {position}.")
            owner = self._normalize_email(raw_quote.get("usuario_creador", ""))
            if owner not in known_users:
                raise CommandError(
                    f"El presupuesto en posición {position} no tiene un propietario válido."
                )
            legacy_id = str(raw_quote.get("id", "")).strip()
            identity = (owner, legacy_id)
            if not legacy_id or identity in seen_quote_ids:
                raise CommandError("Hay presupuestos sin ID o con ID duplicado.")
            seen_quote_ids.add(identity)
            self._decimal(raw_quote.get("total", 0), "total")
            self._parse_datetime(raw_quote.get("fecha"))

    def _get_or_create_user(self, email, raw_user):
        user = User.objects.filter(email__iexact=email).first()
        if user is not None:
            return user, False

        is_blocked = str(raw_user.get("estado", "")).lower() == "bloqueado"
        user = User(email=email, is_active=not is_blocked)
        user.set_unusable_password()
        user.full_clean()
        user.save()
        registration_date = self._parse_date(raw_user.get("fecha_registro"))
        if registration_date:
            User.objects.filter(pk=user.pk).update(date_joined=registration_date)
            user.date_joined = registration_date
        return user, True

    def _get_or_create_organization(self, user, raw_user):
        membership = (
            Membership.objects.select_related("organization")
            .filter(user=user)
            .first()
        )
        if membership is not None:
            return membership.organization, False

        fallback_name = f"Taller {user.email.split('@', 1)[0]}"
        name = str(raw_user.get("nombre_empresa") or fallback_name).strip()[:160]
        slug_base = slugify(name)[:35] or "taller"
        digest = hashlib.sha256(user.email.encode("utf-8")).hexdigest()[:8]
        organization = Organization.objects.create(
            name=name,
            slug=f"{slug_base}-{digest}",
            email=user.email,
            is_active=user.is_active,
        )
        Membership.objects.create(
            user=user,
            organization=organization,
            role=Membership.Role.OWNER,
            is_active=user.is_active,
        )
        return organization, True

    def _ensure_subscription(self, organization, raw_user, legacy_trial_days):
        state = str(raw_user.get("estado", "prueba")).lower()
        raw_plan = str(raw_user.get("plan", "trial")).lower()
        plan = (
            Subscription.Plan.PROFESSIONAL
            if raw_plan in {"profesional", "professional"} or state == "activo"
            else Subscription.Plan.TRIAL
        )
        status = {
            "activo": Subscription.Status.ACTIVE,
            "prueba": Subscription.Status.TRIALING,
            "expirado": Subscription.Status.PAST_DUE,
            "bloqueado": Subscription.Status.CANCELLED,
        }.get(state, Subscription.Status.PAST_DUE)
        registration_date = self._parse_date(raw_user.get("fecha_registro"))
        trial_ends_at = (
            registration_date + timedelta(days=legacy_trial_days)
            if registration_date and status == Subscription.Status.TRIALING
            else None
        )
        Subscription.objects.get_or_create(
            organization=organization,
            defaults={
                "plan": plan,
                "status": status,
                "trial_ends_at": trial_ends_at,
            },
        )

    def _import_quotes(self, organization, user, raw_quotes, stats):
        customer_cache = {}
        for raw_quote in raw_quotes:
            legacy_id = str(raw_quote["id"]).strip()
            if Quote.objects.filter(
                organization=organization,
                legacy_source=SOURCE_NAME,
                legacy_id=legacy_id,
            ).exists():
                stats["quotes_skipped"] += 1
                continue

            customer, customer_created = self._get_or_create_customer(
                organization, raw_quote, customer_cache
            )
            stats["customers_created" if customer_created else "customers_existing"] += 1

            labor = self._decimal(raw_quote.get("mano_obra", 0), "mano_obra")
            parts = self._decimal(raw_quote.get("repuestos", 0), "repuestos")
            legacy_total = self._decimal(raw_quote.get("total", 0), "total")
            item_specs = []
            if parts:
                item_specs.append(("Repuestos", Decimal("1.00"), parts))
            for raw_item in raw_quote.get("items") or []:
                if not isinstance(raw_item, dict):
                    raise CommandError(f"Ítem inválido en presupuesto {legacy_id}.")
                description = str(raw_item.get("nombre") or "Ítem importado").strip()[:240]
                price = self._decimal(raw_item.get("precio", 0), "precio de ítem")
                item_specs.append((description, Decimal("1.00"), price))

            item_total = sum((spec[2] for spec in item_specs), Decimal("0.00"))
            calculated_total = labor + item_total
            discount = max(calculated_total - legacy_total, Decimal("0.00"))
            adjustment = max(legacy_total - calculated_total, Decimal("0.00"))
            if adjustment:
                item_specs.append(("Ajuste de migración", Decimal("1.00"), adjustment))

            number = self._quote_number(organization, legacy_id)
            quote = Quote.objects.create(
                organization=organization,
                number=number,
                legacy_source=SOURCE_NAME,
                legacy_id=legacy_id,
                customer=customer,
                status=QUOTE_STATUS_MAP.get(
                    str(raw_quote.get("estado", "")).upper(), Quote.Status.DRAFT
                ),
                notes=str(raw_quote.get("notas") or ""),
                labor_amount=labor,
                discount_amount=discount,
                created_by=user,
            )
            QuoteItem.objects.bulk_create(
                [
                    QuoteItem(
                        quote=quote,
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        position=position,
                    )
                    for position, (description, quantity, unit_price) in enumerate(
                        item_specs, start=1
                    )
                ]
            )
            quote.recalculate_totals()
            if quote.total_amount != legacy_total:
                raise CommandError(
                    f"No fue posible conservar el total del presupuesto {legacy_id}."
                )
            created_at = self._parse_datetime(raw_quote["fecha"])
            Quote.objects.filter(pk=quote.pk).update(
                created_at=created_at, updated_at=created_at
            )
            stats["quotes_created"] += 1
            stats["items_created"] += len(item_specs)

        max_number = (
            Quote.objects.filter(organization=organization).aggregate(Max("number"))[
                "number__max"
            ]
            or 0
        )
        if organization.next_quote_number <= max_number:
            organization.next_quote_number = max_number + 1
            organization.save(update_fields=("next_quote_number", "updated_at"))

    def _get_or_create_customer(self, organization, raw_quote, customer_cache):
        name = str(raw_quote.get("cliente") or "Cliente importado").strip()[:160]
        phone = str(raw_quote.get("telefono") or "").strip()[:40]
        email = self._normalize_email(raw_quote.get("email") or "")
        identity = (name.casefold(), phone, email)
        if identity in customer_cache:
            return customer_cache[identity], False

        query = Customer.objects.for_organization(organization).filter(
            name__iexact=name,
            phone=phone,
        )
        query = query.filter(email__iexact=email) if email else query.filter(email="")
        customer = query.first()
        created = customer is None
        if created:
            customer = Customer.objects.create(
                organization=organization,
                name=name,
                phone=phone,
                email=email,
            )
        customer_cache[identity] = customer
        return customer, created

    def _quote_number(self, organization, legacy_id):
        try:
            candidate = int(legacy_id)
        except ValueError:
            candidate = 0
        if candidate > 0 and not Quote.objects.filter(
            organization=organization, number=candidate
        ).exists():
            return candidate

        candidate = max(organization.next_quote_number, 1)
        while Quote.objects.filter(organization=organization, number=candidate).exists():
            candidate += 1
        organization.next_quote_number = candidate + 1
        organization.save(update_fields=("next_quote_number", "updated_at"))
        return candidate

    def _decimal(self, value, field_name):
        try:
            number = Decimal(str(value or 0)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError) as exc:
            raise CommandError(f"Valor inválido para {field_name}.") from exc
        if number < 0:
            raise CommandError(f"{field_name} no puede ser negativo.")
        return number

    def _parse_datetime(self, value):
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M")
        except ValueError as exc:
            raise CommandError("Fecha de presupuesto inválida.") from exc
        return timezone.make_aware(parsed, timezone.get_current_timezone())

    def _parse_date(self, value):
        if not value:
            return None
        try:
            parsed_date = datetime.strptime(str(value), "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError("Fecha de registro inválida.") from exc
        return timezone.make_aware(
            datetime.combine(parsed_date, time.min), timezone.get_current_timezone()
        )

    def _normalize_email(self, value):
        return User.objects.normalize_email(str(value).strip()).lower()
