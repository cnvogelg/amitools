class IconError(Exception):
    """Base exception for icon library errors."""


class IconFormatError(IconError):
    """Raised when an icon file cannot be parsed or is malformed."""


class IconIOError(IconError):
    """Raised when reading or writing an icon file fails."""


class IconFieldError(IconError):
    """Raised when a requested icon field is unknown or unavailable."""


class IconOperationError(IconError):
    """Raised when an icon operation cannot be completed."""
