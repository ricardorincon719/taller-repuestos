from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext as _


GOOGLE_SITE_VERIFICATION_FILE = "google7ed5d2f231d5892e.html"
GOOGLE_SITE_VERIFICATION_CONTENT = (
    f"google-site-verification: {GOOGLE_SITE_VERIFICATION_FILE}"
)


def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unhealthy"}, status=503)
    return JsonResponse({"status": "ok"})


def liveness_check(request):
    return JsonResponse({"status": "alive"})


def google_site_verification(request):
    return HttpResponse(GOOGLE_SITE_VERIFICATION_CONTENT, content_type="text/plain")


def bad_request(request, exception=None):
    return _error_response(
        request, 400, _("Solicitud inválida"), _("Revisa los datos e inténtalo de nuevo.")
    )


def permission_denied(request, exception=None):
    return _error_response(
        request, 403, _("Acceso no autorizado"), _("No tienes permiso para abrir esta página.")
    )


def page_not_found(request, exception=None):
    return _error_response(
        request, 404, _("Página no encontrada"), _("No encontramos la página solicitada.")
    )


def server_error(request):
    return _error_response(
        request,
        500,
        _("No pudimos completar la solicitud"),
        _("El incidente quedó registrado. Inténtalo nuevamente en unos minutos."),
    )


def csrf_failure(request, reason=""):
    return _error_response(
        request,
        403,
        _("La sesión del formulario venció"),
        _("Recarga la página y vuelve a enviar el formulario."),
    )


def _error_response(request, status, title, message):
    content = render_to_string(
        "errors/error.html",
        {"status_code": status, "error_title": title, "error_message": message},
    )
    return HttpResponse(content, status=status)
