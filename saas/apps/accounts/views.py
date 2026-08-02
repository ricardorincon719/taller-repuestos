import logging

from django.contrib import messages
from django.conf import settings
from django.contrib.auth import login, views as auth_views
from django.contrib.auth.tokens import default_token_generator
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from django.utils.translation import gettext as _

from .forms import RegistrationForm, ResendActivationForm
from .models import User
from .security import consume_rate_limit, request_ip
from .services import (
    create_trial_account,
    registration_is_limited,
    send_activation_email,
)

logger = logging.getLogger(__name__)


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        ip_address = request_ip(request)
        email = form.cleaned_data["email"]
        if registration_is_limited(f"ip:{ip_address}", f"email:{email}"):
            form.add_error(None, _("Demasiados intentos de registro. Inténtalo más tarde."))
            return render(
                request,
                "registration/register.html",
                {"form": form},
                status=429,
            )
        try:
            user = create_trial_account(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password1"],
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                organization_name=form.cleaned_data["organization_name"],
                phone=form.cleaned_data["phone"],
                accepted_legal=True,
                ip_address=ip_address,
            )
        except IntegrityError:
            form.add_error("email", _("Ya existe una cuenta con este email."))
        else:
            delivery_failed = False
            try:
                send_activation_email(user)
            except Exception:
                delivery_failed = True
                logger.exception("Could not send account activation email", extra={"user_id": user.pk})
            return render(
                request,
                "registration/registration_sent.html",
                {"email": user.email, "delivery_failed": delivery_failed},
            )
    return render(request, "registration/register.html", {"form": form})


def activate_account(request, uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        return render(request, "registration/activation_invalid.html", status=400)

    if not user.is_active:
        user.is_active = True
        user.save(update_fields=("is_active",))
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, _("Tu cuenta fue activada correctamente."))
    return redirect("dashboard")


def resend_activation(request):
    form = ResendActivationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        allowed = consume_rate_limit(
            "activation-resend-ip",
            request_ip(request),
            limit=settings.ACTIVATION_RESEND_RATE_LIMIT,
            window_seconds=settings.AUTH_RATE_LIMIT_WINDOW,
        ) and consume_rate_limit(
            "activation-resend-email",
            email,
            limit=settings.ACTIVATION_RESEND_RATE_LIMIT,
            window_seconds=settings.AUTH_RATE_LIMIT_WINDOW,
        )
        if not allowed:
            form.add_error(None, _("Demasiadas solicitudes. Inténtalo más tarde."))
            return render(
                request, "registration/resend_activation.html", {"form": form}, status=429
            )
        user = User.objects.filter(
            email__iexact=email, is_active=False
        ).first()
        if user is not None:
            try:
                send_activation_email(user)
            except Exception:
                logger.exception(
                    "Could not resend account activation email", extra={"user_id": user.pk}
                )
        return render(request, "registration/activation_resent.html")
    return render(request, "registration/resend_activation.html", {"form": form})


class RateLimitedLoginView(auth_views.LoginView):
    def form_invalid(self, form):
        email = self.request.POST.get("username", "").strip().lower()
        allowed = consume_rate_limit(
            "login-ip",
            request_ip(self.request),
            limit=settings.LOGIN_RATE_LIMIT,
            window_seconds=settings.AUTH_RATE_LIMIT_WINDOW,
        ) and consume_rate_limit(
            "login-email",
            email,
            limit=settings.LOGIN_RATE_LIMIT,
            window_seconds=settings.AUTH_RATE_LIMIT_WINDOW,
        )
        if not allowed:
            form.add_error(None, _("Demasiados intentos. Inténtalo más tarde."))
            response = self.render_to_response(self.get_context_data(form=form))
            response.status_code = 429
            return response
        return super().form_invalid(form)


class RateLimitedPasswordResetView(auth_views.PasswordResetView):
    def post(self, request, *args, **kwargs):
        email = request.POST.get("email", "").strip().lower()
        allowed = consume_rate_limit(
            "password-reset-ip",
            request_ip(request),
            limit=settings.PASSWORD_RESET_RATE_LIMIT,
            window_seconds=settings.AUTH_RATE_LIMIT_WINDOW,
        ) and consume_rate_limit(
            "password-reset-email",
            email,
            limit=settings.PASSWORD_RESET_RATE_LIMIT,
            window_seconds=settings.AUTH_RATE_LIMIT_WINDOW,
        )
        if not allowed:
            form = self.get_form()
            form.add_error(None, _("Demasiadas solicitudes. Inténtalo más tarde."))
            response = self.render_to_response(self.get_context_data(form=form))
            response.status_code = 429
            return response
        return super().post(request, *args, **kwargs)
