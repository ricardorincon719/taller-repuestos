import hashlib
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.utils.text import slugify

from apps.billing.models import Subscription
from apps.organizations.models import Membership, Organization

from .models import User


@transaction.atomic
def create_trial_account(*, email, password, first_name, last_name, organization_name, phone=""):
    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        is_active=False,
    )
    base_slug = slugify(organization_name)[:40] or "negocio"
    organization = Organization.objects.create(
        name=organization_name,
        slug=f"{base_slug}-{uuid.uuid4().hex[:8]}",
        email=email,
        phone=phone,
    )
    Membership.objects.create(
        organization=organization,
        user=user,
        role=Membership.Role.OWNER,
    )
    Subscription.objects.create(
        organization=organization,
        plan=Subscription.Plan.TRIAL,
        status=Subscription.Status.TRIALING,
        trial_ends_at=timezone.now() + timedelta(days=settings.TRIAL_DAYS),
    )
    return user


def send_activation_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    activation_path = reverse("activate-account", kwargs={"uidb64": uid, "token": token})
    activation_url = f"{settings.SITE_URL}{activation_path}"
    context = {"user": user, "activation_url": activation_url}
    send_mail(
        subject="Activa tu cuenta de Taller Pro",
        message=render_to_string("registration/activation_email.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=render_to_string("registration/activation_email.html", context),
    )


def send_password_setup_email(user):
    from .forms import ImportedUserPasswordResetForm

    form = ImportedUserPasswordResetForm({"email": user.email})
    if not form.is_valid():
        raise ValueError("Could not build password setup email.")
    form.save()


def registration_is_limited(*identifiers):
    limit = settings.REGISTRATION_RATE_LIMIT
    timeout = settings.REGISTRATION_RATE_LIMIT_WINDOW
    limited = False
    for identifier in identifiers:
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        key = f"registration-attempts:{digest}"
        if cache.add(key, 1, timeout=timeout):
            attempts = 1
        else:
            try:
                attempts = cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=timeout)
                attempts = 1
        limited = limited or attempts > limit
    return limited
