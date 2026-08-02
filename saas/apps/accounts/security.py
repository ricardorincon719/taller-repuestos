import hashlib
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import RateLimitBucket


def request_ip(request):
    if settings.TRUST_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def hash_identifier(value):
    return hashlib.sha256(f"{settings.SECRET_KEY}:{value}".encode()).hexdigest()


def consume_rate_limit(scope, identifier, *, limit, window_seconds):
    key_hash = hash_identifier(f"{scope}:{identifier}")
    now = timezone.now()
    cutoff = now - timedelta(seconds=window_seconds)
    for _attempt in range(2):
        try:
            with transaction.atomic():
                bucket = RateLimitBucket.objects.select_for_update().filter(
                    key_hash=key_hash
                ).first()
                if bucket is None:
                    RateLimitBucket.objects.create(
                        key_hash=key_hash, attempts=1, window_started_at=now
                    )
                    return True
                if bucket.window_started_at <= cutoff:
                    bucket.attempts = 1
                    bucket.window_started_at = now
                else:
                    bucket.attempts += 1
                bucket.save(update_fields=("attempts", "window_started_at", "updated_at"))
                return bucket.attempts <= limit
        except IntegrityError:
            continue
    return False
