"""
Custom exceptions for the ViaVerde Traffic API.
"""


class ViaVerdeError(Exception):
    """Base exception for all ViaVerde API errors."""

    pass


class ViaVerdeConnectionError(ViaVerdeError):
    """Raised when there's a connection error to the ViaVerde API."""

    pass


class ViaVerdeAPIError(ViaVerdeError):
    """Raised when the ViaVerde API returns an error."""

    pass


class ViaVerdeImageError(ViaVerdeError):
    """Raised when there's an error processing a camera image."""

    pass
