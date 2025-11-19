from django import template
from django.utils import timezone
from datetime import datetime

register = template.Library()


@register.filter
def from_now(value):
    """
    Format a datetime as "X ago" similar to moment.js fromNow().
    Only shows the largest unit (e.g., "24 days ago" not "3 weeks, 3 days ago").
    """
    if not value:
        return ""

    try:
        # Get current time (will be naive if USE_TZ=False, aware if USE_TZ=True)
        now = timezone.now()

        # Handle different input types
        if isinstance(value, str):
            # If it's a string, try to parse it
            from django.utils.dateparse import parse_datetime

            parsed = parse_datetime(value)
            if parsed:
                value = parsed
            else:
                return ""

        # Check if value is a datetime-like object
        if not isinstance(value, datetime):
            return ""

        # When USE_TZ=False, both now and value are naive
        # When USE_TZ=True, both should be aware
        # Calculate delta directly - Python handles naive vs aware correctly
        delta = now - value

        # If in the future, return "in X"
        if delta.total_seconds() < 0:
            delta = -delta
            prefix = "in "
        else:
            prefix = ""
            suffix = " ago"

        total_seconds = delta.total_seconds()

        # Calculate different time units
        # Use rounding for days to match moment.js behavior (rounds to nearest day)
        # For other units, use floor division to match moment.js thresholds
        years = int(total_seconds // (365 * 24 * 60 * 60))
        months = int(total_seconds // (30 * 24 * 60 * 60))
        days = round(total_seconds / (24 * 60 * 60))  # Round to nearest day
        hours = int(total_seconds // (60 * 60))
        minutes = int(total_seconds // 60)

        # Return only the largest unit, matching moment.js fromNow() behavior
        # Skip weeks - use days for anything less than a month
        if years > 0:
            return f"{prefix}{years} year{'s' if years != 1 else ''}{suffix if prefix == '' else ''}"
        elif months > 0:
            return f"{prefix}{months} month{'s' if months != 1 else ''}{suffix if prefix == '' else ''}"
        elif days > 0:
            return f"{prefix}{days} day{'s' if days != 1 else ''}{suffix if prefix == '' else ''}"
        elif hours > 0:
            return f"{prefix}{hours} hour{'s' if hours != 1 else ''}{suffix if prefix == '' else ''}"
        elif minutes > 0:
            return f"{prefix}{minutes} minute{'s' if minutes != 1 else ''}{suffix if prefix == '' else ''}"
        else:
            return "just now"
    except Exception as e:
        # Return empty string on any error to prevent template errors
        # In development, you might want to log this
        return ""
