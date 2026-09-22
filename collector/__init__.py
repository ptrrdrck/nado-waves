"""NDBC observation collector.

Build order rule (CLAUDE.md): this package ships before any app code. The NDBC
real-time service retains only 45 days, so every day this is not running is a
day of history that cannot be recovered later.
"""

__all__ = ["ndbc", "archive", "stations"]
