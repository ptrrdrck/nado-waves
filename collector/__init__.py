"""NDBC observation collector.

This package shipped before any app code (the predecessor project's build
order rule). The NDBC
real-time service retains only 45 days, so every day this is not running is a
day of history that cannot be recovered later.
"""

__all__ = ["ndbc", "archive", "stations"]
