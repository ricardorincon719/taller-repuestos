from django.utils import translation

from .models import Membership


class OrganizationLanguageMiddleware:
    """Activate the active organization's language for authenticated app pages."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = self._get_organization_language(request)
        language_activated = False
        if language:
            translation.activate(language)
            request.LANGUAGE_CODE = translation.get_language()
            language_activated = True

        try:
            response = self.get_response(request)
        finally:
            if language_activated:
                translation.deactivate()

        if language:
            response.headers.setdefault("Content-Language", request.LANGUAGE_CODE)
        return response

    def _get_organization_language(self, request):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return None

        membership = getattr(request, "current_membership", None)
        if membership is None:
            membership = (
                Membership.objects.select_related("organization")
                .filter(user=user, is_active=True, organization__is_active=True)
                .order_by("created_at")
                .first()
            )
            if membership is not None:
                request.current_membership = membership

        if membership is None:
            return None
        return membership.organization.language
