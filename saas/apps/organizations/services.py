from django.core.exceptions import PermissionDenied

from .models import Membership


def get_current_membership(user):
    membership = (
        Membership.objects.select_related("organization")
        .filter(user=user, is_active=True, organization__is_active=True)
        .first()
    )
    if membership is None:
        raise PermissionDenied("Tu usuario no pertenece a un taller activo.")
    return membership
