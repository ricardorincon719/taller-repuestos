from django.db import connection
from django.http import HttpResponse, JsonResponse


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


def google_site_verification(request):
    return HttpResponse(GOOGLE_SITE_VERIFICATION_CONTENT, content_type="text/plain")
