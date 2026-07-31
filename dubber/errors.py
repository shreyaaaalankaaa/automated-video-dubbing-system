class DubberError(RuntimeError):
    """Base exception for actionable pipeline failures."""


class DependencyError(DubberError):
    """Raised when a required system or Python dependency is unavailable."""


class MediaError(DubberError):
    """Raised when FFmpeg or media processing fails."""


class DownloadError(DubberError):
    """Raised when source video retrieval fails."""
