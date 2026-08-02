import json
from urllib.parse import urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class PaddleAPIError(RuntimeError):
    pass


def paddle_api_request(path, *, method="GET", payload=None):
    if not settings.PADDLE_API_KEY:
        raise PaddleAPIError("Paddle API key is not configured")
    body = json.dumps(payload or {}).encode() if payload is not None else None
    request = Request(
        f"{settings.PADDLE_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {settings.PADDLE_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "TallerPro/1.0",
        },
    )
    try:
        with urlopen(request, timeout=settings.PADDLE_API_TIMEOUT) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:1000]
        raise PaddleAPIError(f"Paddle returned HTTP {exc.code}: {detail}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise PaddleAPIError("Paddle API is temporarily unavailable") from exc


def create_customer_portal_session(subscription):
    payload = {}
    if subscription.provider_subscription_id:
        payload["subscription_ids"] = [subscription.provider_subscription_id]
    response = paddle_api_request(
        f"customers/{subscription.provider_customer_id}/portal-sessions",
        method="POST",
        payload=payload,
    )
    try:
        portal_url = response["data"]["urls"]["general"]["overview"]
    except (KeyError, TypeError) as exc:
        raise PaddleAPIError("Paddle returned an incomplete portal session") from exc
    if urlparse(portal_url).scheme != "https":
        raise PaddleAPIError("Paddle returned an invalid portal URL")
    return portal_url
