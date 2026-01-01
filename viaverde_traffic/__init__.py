"""
ViaVerde Traffic API - Python wrapper for Via Verde traffic cameras.

A simple Python library to access Portuguese highway traffic cameras
from the Via Verde website.

Example:
    >>> from viaverde_traffic import ViaVerdeTrafficAPI
    >>> api = ViaVerdeTrafficAPI()
    >>> cameras = api.get_all_cameras()
    >>> image = api.get_camera_image(camera_id=29)
"""

from .api import ViaVerdeTrafficAPI
from .exceptions import (
    ViaVerdeError,
    ViaVerdeAPIError,
    ViaVerdeConnectionError,
    ViaVerdeImageError,
)

__version__ = "0.1.0"
__author__ = "Miguel"
__all__ = [
    "ViaVerdeTrafficAPI",
    "ViaVerdeError",
    "ViaVerdeAPIError",
    "ViaVerdeConnectionError",
    "ViaVerdeImageError",
]
