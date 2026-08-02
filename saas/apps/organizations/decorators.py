from functools import wraps

from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

from .services import get_request_membership


def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            membership = get_request_membership(request)
            if membership.role not in roles:
                raise PermissionDenied(_("No tienes permisos para realizar esta acción."))
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
