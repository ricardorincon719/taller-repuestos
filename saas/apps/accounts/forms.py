from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.utils.translation import gettext_lazy as _

from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True}))


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(label=_("Nombre"), max_length=150)
    last_name = forms.CharField(label=_("Apellido"), max_length=150, required=False)
    email = forms.EmailField(label="Email")
    organization_name = forms.CharField(label=_("Nombre del negocio"), max_length=160)
    phone = forms.CharField(label=_("Teléfono"), max_length=40, required=False)
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "organization_name",
            "phone",
            "password1",
            "password2",
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Ya existe una cuenta con este email.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("website"):
            raise forms.ValidationError("Registro inválido.")
        return cleaned_data


class ResendActivationForm(forms.Form):
    email = forms.EmailField(label="Email")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()


class ImportedUserPasswordResetForm(forms.Form):
    email = forms.EmailField(label="Email", max_length=254)

    def save(
        self,
        domain_override=None,
        subject_template_name="registration/password_reset_subject.txt",
        email_template_name="registration/password_reset_email.txt",
        use_https=False,
        token_generator=None,
        from_email=None,
        request=None,
        html_email_template_name="registration/password_reset_email.html",
        extra_email_context=None,
    ):
        from django.conf import settings
        from django.contrib.auth.tokens import default_token_generator
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.urls import reverse
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        token_generator = token_generator or default_token_generator
        email = self.cleaned_data["email"].lower()
        users = User.objects.filter(email__iexact=email, is_active=True)
        for user in users:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = token_generator.make_token(user)
            reset_path = reverse(
                "password_reset_confirm", kwargs={"uidb64": uid, "token": token}
            )
            reset_url = f"{settings.SITE_URL}{reset_path}"
            context = {
                "email": user.email,
                "user": user,
                "uid": uid,
                "token": token,
                "reset_url": reset_url,
                **(extra_email_context or {}),
            }
            subject = "".join(
                render_to_string(subject_template_name, context).splitlines()
            )
            body = render_to_string(email_template_name, context)
            message = EmailMultiAlternatives(
                subject, body, from_email or settings.DEFAULT_FROM_EMAIL, [user.email]
            )
            if html_email_template_name:
                message.attach_alternative(
                    render_to_string(html_email_template_name, context), "text/html"
                )
            message.send()
