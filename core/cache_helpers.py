"""
Shared cache helper functions for the multi-media platform.

Provides common caching patterns used across games and books apps
to reduce code duplication.
"""

from datetime import datetime

from django.core.cache import cache
from django.db.models import Max, Min


def get_year_bounds(
    model_class, year_field, cache_key, cache_timeout, default_min=1970
):
    """
    Return cached global min/max years for a model.

    Args:
        model_class: Django model class to query
        year_field: Name of the year field on the model
        cache_key: Unique cache key for this model's year stats
        cache_timeout: Cache timeout in seconds
        default_min: Default minimum year if no data exists

    Returns:
        Tuple of (min_year, max_year)
    """
    year_stats = cache.get(cache_key)
    if year_stats is None:
        year_stats = model_class.objects.aggregate(
            min_year=Min(year_field),
            max_year=Max(year_field),
        )
        cache.set(cache_key, year_stats, cache_timeout)
    min_year = year_stats["min_year"] or default_min
    max_year = year_stats["max_year"] or datetime.today().year
    return min_year, max_year
