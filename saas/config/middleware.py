import logging
import time
import uuid


logger = logging.getLogger("taller_pro.requests")


class RequestIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        started = time.monotonic()
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        logger.info(
            "request",
            extra={
                "request_id": request.request_id,
                "status_code": response.status_code,
                "user_id": getattr(getattr(request, "user", None), "pk", None),
                "organization_id": getattr(
                    getattr(getattr(request, "current_membership", None), "organization", None),
                    "pk",
                    None,
                ),
                "duration_ms": round((time.monotonic() - started) * 1000, 2),
                "method": request.method,
                "path": request.path,
            },
        )
        return response


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline' https://cdn.paddle.com; "
            "frame-src https://*.paddle.com; connect-src 'self' https://*.paddle.com; "
            "font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self' https://*.paddle.com",
        )
        response.headers.setdefault(
            "Permissions-Policy",
            'camera=(), microphone=(), geolocation=(), payment=(self "https://*.paddle.com")',
        )
        return response
