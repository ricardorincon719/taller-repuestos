from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps.accounts.forms import EmailAuthenticationForm, ImportedUserPasswordResetForm
from apps.accounts.views import RateLimitedLoginView, RateLimitedPasswordResetView
from apps.dashboard.views import legal_cookies, legal_privacy, legal_terms
from config.views import (
    GOOGLE_SITE_VERIFICATION_FILE,
    google_site_verification,
    health_check,
    liveness_check,
)

handler400 = "config.views.bad_request"
handler403 = "config.views.permission_denied"
handler404 = "config.views.page_not_found"
handler500 = "config.views.server_error"

urlpatterns = [
    path("health/", health_check, name="health-check"),
    path("health/live/", liveness_check, name="liveness-check"),
    path(
        GOOGLE_SITE_VERIFICATION_FILE,
        google_site_verification,
        name="google-site-verification",
    ),
    path("admin/", admin.site.urls),
    path("legal/terminos/", legal_terms, name="legal-terms"),
    path("legal/privacidad/", legal_privacy, name="legal-privacy"),
    path("legal/cookies/", legal_cookies, name="legal-cookies"),
    path("cuenta/", include("apps.accounts.urls")),
    path(
        "login/",
        RateLimitedLoginView.as_view(
            template_name="registration/login.html",
            authentication_form=EmailAuthenticationForm,
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path(
        "recuperar-clave/",
        RateLimitedPasswordResetView.as_view(
            template_name="registration/password_reset_form.html",
            email_template_name="registration/password_reset_email.txt",
            html_email_template_name="registration/password_reset_email.html",
            subject_template_name="registration/password_reset_subject.txt",
            form_class=ImportedUserPasswordResetForm,
        ),
        name="password_reset",
    ),
    path(
        "recuperar-clave/enviado/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "restablecer/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "restablecer/completo/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),
    path("suscripcion/", include("apps.billing.urls")),
    path("negocio/", include("apps.organizations.urls")),
    path("", include("apps.dashboard.urls")),
    path("clientes/", include("apps.customers.urls")),
    path("presupuestos/", include("apps.quotes.urls")),
]
