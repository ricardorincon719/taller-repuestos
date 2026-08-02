from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils.translation import gettext as _

from .models import Membership, OrganizationEvent


def get_current_membership(user, organization_id=None):
    memberships = Membership.objects.select_related("organization").filter(
        user=user, is_active=True, organization__is_active=True
    )
    if organization_id:
        membership = memberships.filter(organization_id=organization_id).first()
    else:
        membership = memberships.order_by("created_at", "pk").first()
    if membership is None:
        raise PermissionDenied(_("Tu usuario no pertenece a un negocio activo."))
    return membership


def get_request_membership(request):
    membership = getattr(request, "current_membership", None)
    if membership is not None:
        return membership
    organization_id = request.session.get("current_organization_id")
    try:
        membership = get_current_membership(request.user, organization_id)
    except PermissionDenied:
        if not organization_id:
            raise
        request.session.pop("current_organization_id", None)
        membership = get_current_membership(request.user)
    request.current_membership = membership
    request.session["current_organization_id"] = str(membership.organization_id)
    return membership


def record_organization_event(organization, event_type, *, actor=None, metadata=None):
    return OrganizationEvent.objects.create(
        organization=organization,
        actor=actor,
        event_type=event_type,
        metadata=metadata or {},
    )


@transaction.atomic
def change_membership_role(*, membership, role, actor):
    membership = Membership.objects.select_for_update(of=("self",)).select_related(
        "organization", "user"
    ).get(pk=membership.pk)
    if membership.role == Membership.Role.OWNER and role != Membership.Role.OWNER:
        owners = Membership.objects.filter(
            organization=membership.organization,
            role=Membership.Role.OWNER,
            is_active=True,
        ).count()
        if owners <= 1:
            raise PermissionDenied(_("El negocio debe conservar al menos un propietario."))
    old_role = membership.role
    membership.role = role
    membership.save(update_fields=("role",))
    record_organization_event(
        membership.organization,
        "membership.role_changed",
        actor=actor,
        metadata={
            "membership_id": membership.pk,
            "user_id": membership.user_id,
            "from": old_role,
            "to": role,
        },
    )
    return membership
