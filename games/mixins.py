"""Reusable view mixins for the games application.

These mixins are re-exported from core for backward compatibility.
New code should import directly from core.mixins.
"""

# Re-export from core for backward compatibility
from core.mixins import HTMXPartialMixin, RobustPaginationMixin

__all__ = ["RobustPaginationMixin", "HTMXPartialMixin"]
