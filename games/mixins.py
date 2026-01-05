"""Reusable view mixins for the games application.

DEPRECATED: This module exists only for backward compatibility.
Import directly from core.mixins instead:

    from core.mixins import HTMXPartialMixin, RobustPaginationMixin

This file will be removed in a future release.
"""

import warnings

from core.mixins import (
    HTMXPartialMixin as _HTMXPartialMixin,
    RobustPaginationMixin as _RobustPaginationMixin,
)


class RobustPaginationMixin(_RobustPaginationMixin):
    """DEPRECATED: Import from core.mixins instead."""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "games.mixins.RobustPaginationMixin is deprecated. "
            "Import from core.mixins instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


class HTMXPartialMixin(_HTMXPartialMixin):
    """DEPRECATED: Import from core.mixins instead."""

    def __init__(self, *args, **kwargs):
        warnings.warn(
            "games.mixins.HTMXPartialMixin is deprecated. "
            "Import from core.mixins instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)


__all__ = ["RobustPaginationMixin", "HTMXPartialMixin"]
