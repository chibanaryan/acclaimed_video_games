"""Contact form spam/rate-limit guard."""

import hashlib
import time
from dataclasses import dataclass

from django.core.cache import cache

from games import config


@dataclass(frozen=True)
class SpamDecision:
    """Represents whether a contact submission should be accepted."""

    allowed: bool
    reason: str = ""
    client_ip: str = "unknown"


def evaluate(request, cleaned_data):
    """
    Evaluate a contact form submission for spam/rate-limit signals.

    Returns:
        SpamDecision: allowed=True when submission should proceed, otherwise blocked.
    """
    client_ip = get_client_ip(request)
    email = (cleaned_data.get("email") or "").strip()

    if _is_placeholder_domain(email):
        return SpamDecision(False, "placeholder_domain", client_ip)

    try:
        if _is_rate_limited(client_ip):
            return SpamDecision(False, "rate_limit", client_ip)
        if _is_duplicate(client_ip, cleaned_data):
            return SpamDecision(False, "duplicate", client_ip)
    except Exception:
        # Fail open if cache is unavailable to avoid breaking contact form usage.
        return SpamDecision(True, "cache_unavailable", client_ip)

    return SpamDecision(True, "allowed", client_ip)


def get_client_ip(request):
    """Extract client IP from X-Forwarded-For (Heroku) or REMOTE_ADDR."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _is_placeholder_domain(email):
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[1].lower()
    return domain in config.CONTACT_PLACEHOLDER_DOMAINS


def _is_rate_limited(client_ip):
    now = int(time.time())
    ten_minute_key = (
        f"{config.CONTACT_SPAM_CACHE_PREFIX}:10m:{client_ip}:"
        f"{now // config.CONTACT_RATE_LIMIT_WINDOW_SECONDS}"
    )
    day_key = f"{config.CONTACT_SPAM_CACHE_PREFIX}:24h:{client_ip}:{now // 86400}"

    ten_minute_count = _incr(ten_minute_key, config.CONTACT_RATE_LIMIT_WINDOW_SECONDS)
    day_count = _incr(day_key, 86400)

    return (
        ten_minute_count > config.CONTACT_RATE_LIMIT_PER_10_MIN
        or day_count > config.CONTACT_RATE_LIMIT_PER_24_HOURS
    )


def _incr(key, timeout):
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, timeout=timeout)
        return 1


def _is_duplicate(client_ip, cleaned_data):
    name = _normalize(cleaned_data.get("name"))
    email = _normalize(cleaned_data.get("email"))
    category = _normalize(cleaned_data.get("category"))
    message = _normalize(cleaned_data.get("message"))

    fingerprint_raw = "|".join([client_ip, name, email, category, message])
    fingerprint = hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()
    key = f"{config.CONTACT_SPAM_CACHE_PREFIX}:dup:{fingerprint}"

    if cache.add(key, 1, timeout=config.CONTACT_DUPLICATE_WINDOW_SECONDS):
        return False
    return True


def _normalize(value):
    return " ".join((value or "").strip().lower().split())
