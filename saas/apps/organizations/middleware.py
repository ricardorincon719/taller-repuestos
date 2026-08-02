from zoneinfo import ZoneInfo

from django.core.exceptions import PermissionDenied
from django.utils import timezone, translation

from .services import get_request_membership


class OrganizationLanguageMiddleware:
    """Activate the active organization's language for authenticated app pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = self._get_organization_language(request)
        language_activated = False
        timezone_activated = False
        if language:
            translation.activate(language)
            request.LANGUAGE_CODE = translation.get_language()
            language_activated = True
        membership = getattr(request, "current_membership", None)
        if membership is not None:
            timezone.activate(ZoneInfo(membership.organization.timezone))
            timezone_activated = True

        try:
            response = self.get_response(request)
        finally:
            if language_activated:
                translation.deactivate()
            if timezone_activated:
                timezone.deactivate()

        if language:
            response.headers.setdefault("Content-Language", request.LANGUAGE_CODE)
        return response

    def _get_organization_language(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None

        try:
            membership = get_request_membership(request)
        except PermissionDenied:
            return None
        return membership.organization.language
