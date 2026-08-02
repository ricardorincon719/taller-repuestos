from django.conf import settings

from apps.organizations.models import Membership, OrganizationDeletionRequest


def app_context(request):
    context = {
        "legal_entity_name": settings.LEGAL_ENTITY_NAME,
        "legal_entity_address": settings.LEGAL_ENTITY_ADDRESS,
        "legal_contact_email": settings.LEGAL_CONTACT_EMAIL,
        "legal_jurisdiction": settings.LEGAL_JURISDICTION,
        "legal_document_version": settings.LEGAL_DOCUMENT_VERSION,
        "public_plan_price_label": settings.PUBLIC_PLAN_PRICE_LABEL,
        "trial_days": settings.TRIAL_DAYS,
    }
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return context
    memberships = Membership.objects.select_related("organization").filter(
        user=user, is_active=True, organization__is_active=True
    )
    context["available_memberships"] = memberships
    current_membership = getattr(request, "current_membership", None)
    context["current_membership"] = current_membership
    if current_membership is not None:
        context["pending_organization_deletion"] = OrganizationDeletionRequest.objects.filter(
            organization=current_membership.organization,
            cancelled_at__isnull=True,
        ).first()
    return context
