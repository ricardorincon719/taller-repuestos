import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db import transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.models import LegalAcceptance
from apps.billing.models import BillingNotification, Subscription
from apps.customers.models import Customer, Vehicle
from apps.quotes.models import Quote, QuoteEvent, QuoteItem

from .decorators import roles_required
from .forms import (
    InvitationAcceptanceForm,
    InvitationForm,
    MemberRoleForm,
    OrganizationDeletionForm,
    OrganizationProfileForm,
)
from .models import (
    Membership,
    Organization,
    OrganizationDeletionRequest,
    OrganizationEvent,
    OrganizationInvitation,
)
from .services import (
    change_membership_role,
    get_request_membership,
    record_organization_event,
)


logger = logging.getLogger(__name__)
User = get_user_model()


@login_required
@roles_required(Membership.Role.OWNER, Membership.Role.ADMIN)
def organization_profile(request):
    membership = get_request_membership(request)
    organization = membership.organization
    form = OrganizationProfileForm(
        request.POST or None, request.FILES or None, instance=organization
    )
    if request.method == "POST" and form.is_valid():
        organization = form.save(commit=False)
        logo = form.cleaned_data.get("logo")
        if form.cleaned_data.get("remove_logo"):
            organization.logo_data = None
            organization.logo_content_type = ""
            organization.logo_filename = ""
            organization.logo_updated_at = None
        elif logo:
            organization.logo_data = logo.read()
            organization.logo_content_type = "image/png"
            organization.logo_filename = logo.name[:180]
            organization.logo_updated_at = timezone.now()
        organization.save()
        record_organization_event(
            organization, "organization.profile_updated", actor=request.user
        )
        translation.activate(organization.language)
        request.LANGUAGE_CODE = translation.get_language()
        messages.success(request, _("Perfil del negocio actualizado."))
        return redirect("organization-profile")

    return render(
        request,
        "organizations/profile.html",
        {"form": form, "membership": membership, "organization": organization},
    )


def organization_logo(request, organization_id):
    organization = get_object_or_404(
        Organization.objects.only(
            "logo_data", "logo_content_type", "logo_updated_at", "is_active"
        ),
        pk=organization_id,
        is_active=True,
    )
    if not organization.has_logo:
        raise Http404
    response = HttpResponse(bytes(organization.logo_data), content_type="image/png")
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@roles_required(Membership.Role.OWNER, Membership.Role.ADMIN)
def team(request):
    membership = get_request_membership(request)
    organization = membership.organization
    form = InvitationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        role = form.cleaned_data["role"]
        if membership.role != Membership.Role.OWNER and role == Membership.Role.ADMIN:
            form.add_error("role", _("Solo un propietario puede invitar administradores."))
        elif Membership.objects.filter(
            organization=organization, user__email__iexact=form.cleaned_data["email"]
        ).exists():
            form.add_error("email", _("Esta persona ya pertenece al negocio."))
        else:
            invitation = OrganizationInvitation.objects.create(
                organization=organization,
                email=form.cleaned_data["email"],
                role=role,
                created_by=request.user,
                expires_at=timezone.now() + timedelta(days=7),
            )
            record_organization_event(
                organization,
                "invitation.created",
                actor=request.user,
                metadata={"email": invitation.email, "role": invitation.role},
            )
            invitation_url = (
                f"{settings.SITE_URL}"
                f"{reverse('organization-invitation-accept', args=(invitation.token,))}"
            )
            try:
                send_mail(
                    _("Invitación a %(business)s") % {"business": organization.name},
                    _(
                        "Te invitaron a colaborar en %(business)s dentro de Taller Pro. "
                        "Acepta la invitación aquí: %(url)s"
                    )
                    % {"business": organization.name, "url": invitation_url},
                    settings.DEFAULT_FROM_EMAIL,
                    [invitation.email],
                )
            except Exception:
                logger.exception("Could not send organization invitation", extra={"invitation_id": invitation.pk})
                messages.warning(
                    request,
                    _("La invitación se creó, pero el correo no pudo enviarse."),
                )
            else:
                messages.success(request, _("Invitación enviada."))
            return redirect("organization-team")
    return render(
        request,
        "organizations/team.html",
        {
            "organization": organization,
            "membership": membership,
            "memberships": organization.memberships.select_related("user").all(),
            "invitations": organization.invitations.filter(
                accepted_at__isnull=True, revoked_at__isnull=True
            ),
            "form": form,
        },
    )


def invitation_accept(request, token):
    invitation = get_object_or_404(
        OrganizationInvitation.objects.select_related("organization"), token=token
    )
    if not invitation.is_valid:
        return render(
            request,
            "organizations/invitation_accept.html",
            {"invitation": invitation, "invalid": True},
            status=410,
        )
    existing_user = User.objects.filter(email__iexact=invitation.email).first()
    if existing_user and existing_user.is_active and not request.user.is_authenticated:
        login_url = f"{reverse('login')}?next={request.path}"
        return redirect(login_url)
    form = None
    if not request.user.is_authenticated:
        form = InvitationAcceptanceForm(request.POST or None)
    if request.method == "POST" and (request.user.is_authenticated or form.is_valid()):
        with transaction.atomic():
            invitation = OrganizationInvitation.objects.select_for_update().get(pk=invitation.pk)
            if not invitation.is_valid:
                return redirect("login")
            if request.user.is_authenticated:
                user = request.user
                if user.email.casefold() != invitation.email.casefold():
                    messages.error(request, _("La invitación pertenece a otro email."))
                    return redirect("dashboard")
            else:
                user = User.objects.select_for_update().filter(
                    email__iexact=invitation.email
                ).first()
                if user is None:
                    user = User(email=invitation.email)
                user.first_name = form.cleaned_data["first_name"]
                user.last_name = form.cleaned_data["last_name"]
                user.is_active = True
                user.set_password(form.cleaned_data["password1"])
                user.save()
            Membership.objects.get_or_create(
                organization=invitation.organization,
                user=user,
                defaults={"role": invitation.role},
            )
            invitation.accepted_at = timezone.now()
            invitation.save(update_fields=("accepted_at",))
            record_organization_event(
                invitation.organization,
                "invitation.accepted",
                actor=user,
                metadata={"email": invitation.email},
            )
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session["current_organization_id"] = str(invitation.organization_id)
        messages.success(request, _("Ya formas parte del negocio."))
        return redirect("dashboard")
    return render(
        request,
        "organizations/invitation_accept.html",
        {"invitation": invitation, "form": form},
    )


@login_required
@roles_required(Membership.Role.OWNER, Membership.Role.ADMIN)
@require_POST
def invitation_revoke(request, pk):
    membership = get_request_membership(request)
    invitation = get_object_or_404(
        OrganizationInvitation,
        pk=pk,
        organization=membership.organization,
        accepted_at__isnull=True,
        revoked_at__isnull=True,
    )
    if membership.role != Membership.Role.OWNER and invitation.role == Membership.Role.ADMIN:
        raise PermissionDenied(_("Solo un propietario puede revocar invitaciones de administrador."))
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=("revoked_at",))
    record_organization_event(
        membership.organization,
        "invitation.revoked",
        actor=request.user,
        metadata={"email": invitation.email, "role": invitation.role},
    )
    messages.success(request, _("Invitación revocada."))
    return redirect("organization-team")


@login_required
@roles_required(Membership.Role.OWNER)
@require_POST
def member_update(request, pk):
    current = get_request_membership(request)
    target = get_object_or_404(
        Membership.objects.select_related("user"), pk=pk, organization=current.organization
    )
    form = MemberRoleForm(request.POST)
    if form.is_valid():
        if target.user_id == request.user.id and not form.cleaned_data["is_active"]:
            messages.error(request, _("No puedes desactivar tu propio acceso."))
            return redirect("organization-team")
        change_membership_role(
            membership=target, role=form.cleaned_data["role"], actor=request.user
        )
        target.is_active = form.cleaned_data["is_active"]
        target.save(update_fields=("is_active",))
        messages.success(request, _("Miembro actualizado."))
    return redirect("organization-team")


@login_required
@require_POST
def organization_switch(request):
    membership = get_object_or_404(
        Membership,
        organization_id=request.POST.get("organization_id"),
        user=request.user,
        is_active=True,
        organization__is_active=True,
    )
    request.session["current_organization_id"] = str(membership.organization_id)
    return redirect(request.POST.get("next") or "dashboard")


@login_required
@roles_required(Membership.Role.OWNER)
def organization_export(request):
    membership = get_request_membership(request)
    organization = membership.organization
    quote_ids = Quote.objects.filter(organization=organization).values_list("id", flat=True)
    member_user_ids = Membership.objects.filter(organization=organization).values_list(
        "user_id", flat=True
    )
    payload = {
        "exported_at": timezone.now(),
        "organization": list(
            Organization.objects.filter(pk=organization.pk).values(
                "id", "name", "legal_name", "tax_id", "email", "phone", "address",
                "city", "country", "currency", "timezone", "created_at", "updated_at",
            )
        )[0],
        "members": list(
            Membership.objects.filter(organization=organization).values(
                "user__email", "user__first_name", "user__last_name", "role", "is_active", "created_at"
            )
        ),
        "legal_acceptances": list(
            LegalAcceptance.objects.filter(user_id__in=member_user_ids).values(
                "user__email", "document", "version", "accepted_at"
            )
        ),
        "invitations": list(
            OrganizationInvitation.objects.filter(organization=organization).values(
                "email", "role", "expires_at", "accepted_at", "revoked_at", "created_at"
            )
        ),
        "organization_events": list(
            OrganizationEvent.objects.filter(organization=organization).values(
                "actor__email", "event_type", "metadata", "created_at"
            )
        ),
        "customers": list(Customer.objects.filter(organization=organization).values()),
        "vehicles": list(Vehicle.objects.filter(organization=organization).values()),
        "quotes": list(Quote.objects.filter(organization=organization).values()),
        "quote_items": list(QuoteItem.objects.filter(quote_id__in=quote_ids).values()),
        "quote_events": list(QuoteEvent.objects.filter(quote_id__in=quote_ids).values()),
    }
    try:
        subscription = Subscription.objects.get(organization=organization)
        payload["subscription"] = list(
            Subscription.objects.filter(pk=subscription.pk).values()
        )[0]
        payload["billing_notifications"] = list(
            BillingNotification.objects.filter(subscription=subscription).values(
                "notification_type", "reference_date", "sent_at"
            )
        )
    except IndexError:
        payload["subscription"] = None
        payload["billing_notifications"] = []
    except Subscription.DoesNotExist:
        payload["subscription"] = None
        payload["billing_notifications"] = []
    response = JsonResponse(payload, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = (
        f'attachment; filename="taller-pro-{organization.slug}-datos.json"'
    )
    return response


@login_required
@roles_required(Membership.Role.OWNER)
def organization_delete(request):
    membership = get_request_membership(request)
    organization = membership.organization
    form = OrganizationDeletionForm(
        request.POST or None, user=request.user, organization=organization
    )
    deletion_request = OrganizationDeletionRequest.objects.filter(
        organization=organization, cancelled_at__isnull=True
    ).first()
    if request.method == "POST" and form.is_valid():
        try:
            subscription = organization.subscription
        except Subscription.DoesNotExist:
            subscription = None
        if (
            subscription
            and subscription.provider_subscription_id
            and subscription.status != Subscription.Status.CANCELLED
            and not subscription.cancel_at_period_end
        ):
            form.add_error(
                None,
                _(
                    "Cancela primero la renovación desde el portal de pagos para evitar cobros posteriores."
                ),
            )
        else:
            deletion_request, _created = OrganizationDeletionRequest.objects.update_or_create(
                organization=organization,
                defaults={
                    "requested_by": request.user,
                    "execute_after": timezone.now()
                    + timedelta(days=settings.ACCOUNT_DELETION_GRACE_DAYS),
                    "cancelled_at": None,
                },
            )
            record_organization_event(
                organization,
                "organization.deletion_requested",
                actor=request.user,
                metadata={"execute_after": deletion_request.execute_after.isoformat()},
            )
            messages.warning(request, _("La eliminación quedó programada."))
            return redirect("organization-delete")
    return render(
        request,
        "organizations/delete.html",
        {
            "organization": organization,
            "form": form,
            "deletion_request": deletion_request,
        },
    )


@login_required
@roles_required(Membership.Role.OWNER)
@require_POST
def organization_delete_cancel(request):
    organization = get_request_membership(request).organization
    deletion_request = get_object_or_404(
        OrganizationDeletionRequest, organization=organization, cancelled_at__isnull=True
    )
    deletion_request.cancelled_at = timezone.now()
    deletion_request.save(update_fields=("cancelled_at",))
    record_organization_event(
        organization, "organization.deletion_cancelled", actor=request.user
    )
    messages.success(request, _("La eliminación fue cancelada."))
    return redirect("organization-delete")
