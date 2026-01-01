"""
ViaVerde Traffic API client.

This module provides a Python wrapper for accessing traffic camera images
from the Via Verde website.
"""

import base64
import json
import time
from io import BytesIO
from typing import Any, Dict, List, Optional, Union

import requests

from .exceptions import (
    ViaVerdeAPIError,
    ViaVerdeConnectionError,
    ViaVerdeImageError,
)

# Optional PIL support
try:
    from PIL import Image

    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None  # type: ignore


class ViaVerdeTrafficAPI:
    """
    API wrapper for Via Verde traffic cameras.

    This class provides methods to fetch camera images and metadata from
    the Portuguese Via Verde highway traffic system.

    Attributes:
        language: Language code for API requests (default: "PT")
        session: Requests session for HTTP calls

    Example:
        >>> api = ViaVerdeTrafficAPI()
        >>>
        >>> # Get camera image as bytes
        >>> image_data = api.get_camera_image(camera_id=29)
        >>>
        >>> # Get and save image
        >>> api.save_camera_image(camera_id=29, filepath="camera_29.jpg")
        >>>
        >>> # Get PIL Image object (requires Pillow)
        >>> img = api.get_camera_image_pil(camera_id=29)
        >>>
        >>> # Get list of all cameras
        >>> cameras = api.get_all_cameras()
    """

    BASE_URL = "https://www.viaverde.pt/DesktopModules/Traffic/Handlers/Api.ashx"
    MAIN_PAGE = "https://www.viaverde.pt/ferramentas/informacao-de-transito"

    def __init__(
        self,
        language: str = "PT",
        timeout: int = 10,
        user_agent: Optional[str] = None,
    ) -> None:
        """
        Initialize the API client.

        Args:
            language: Language code (default: "PT")
            timeout: Request timeout in seconds (default: 10)
            user_agent: Custom User-Agent string (optional)
        """
        self.language = language
        self.timeout = timeout
        self.session = requests.Session()

        # Set headers to mimic browser request
        default_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/143.0.0.0 Safari/537.36"
        )

        self.session.headers.update(
            {
                "User-Agent": user_agent or default_ua,
                "Accept": "*/*",
                "Accept-Language": "en-US,en-GB;q=0.9,en;q=0.8,pt;q=0.7",
                "Referer": self.MAIN_PAGE,
                "X-Requested-With": "XMLHttpRequest",
                "DNT": "1",
                "Sec-GPC": "1",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
            }
        )

        # Initialize session by visiting main page to get cookies
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Ensure session has required cookies by visiting main page."""
        if not self._initialized:
            try:
                response = self.session.get(self.MAIN_PAGE, timeout=self.timeout)
                response.raise_for_status()
                self._initialized = True
            except requests.exceptions.ConnectionError as e:
                raise ViaVerdeConnectionError(
                    f"Failed to connect to Via Verde: {e}"
                ) from e
            except requests.exceptions.RequestException as e:
                raise ViaVerdeAPIError(f"Failed to initialize session: {e}") from e

    def get_all_cameras(self) -> List[Dict[str, Any]]:
        """
        Get list of all available cameras.

        Returns:
            List of camera dictionaries with keys:
                - idCamara: Camera ID
                - nomeCamara: Camera name
                - idAe: Highway ID
                - nomeAe: Highway name
                - Latitude: GPS latitude
                - Longitude: GPS longitude

        Raises:
            ViaVerdeConnectionError: If connection to API fails
            ViaVerdeAPIError: If API returns an error

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> cameras = api.get_all_cameras()
            >>> for cam in cameras[:3]:
            ...     print(f"{cam['nomeAe']}: {cam['nomeCamara']}")
        """
        self._ensure_initialized()

        params = {
            "action": "cameras",
            "lang": self.language.lower() + "-" + self.language.upper(),
            "_": int(time.time() * 1000),
        }

        try:
            response = self.session.get(
                self.BASE_URL,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            raise ViaVerdeConnectionError(
                f"Failed to connect to Via Verde API: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ViaVerdeAPIError(f"Error fetching camera list: {e}") from e
        except json.JSONDecodeError as e:
            raise ViaVerdeAPIError(f"Error parsing camera list JSON: {e}") from e

    def get_camera_image(
        self,
        camera_id: int,
        moduleid: int = 0,
        tabid: int = 193,
    ) -> bytes:
        """
        Get camera image as bytes.

        Args:
            camera_id: The ID of the camera
            moduleid: Module ID for the API (default: 0)
            tabid: Tab ID for the API (default: 193)

        Returns:
            Image data as bytes

        Raises:
            ViaVerdeConnectionError: If connection to API fails
            ViaVerdeAPIError: If API returns an error
            ViaVerdeImageError: If image data cannot be decoded

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> image_bytes = api.get_camera_image(camera_id=29)
            >>> with open("camera.jpg", "wb") as f:
            ...     f.write(image_bytes)
        """
        self._ensure_initialized()

        params = {
            "lang": self.language,
            "action": "cameraimage",
            "ts": int(time.time() * 1000),
        }

        # These parameters are sent as headers
        headers = {
            "cameraid": str(camera_id),
            "moduleid": str(moduleid),
            "tabid": str(tabid),
        }

        try:
            response = self.session.get(
                self.BASE_URL,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()

            # The API might return base64-encoded data or JSON
            content_type = response.headers.get("Content-Type", "")

            # Try to parse as JSON first (might contain base64 image)
            if "text" in content_type or "json" in content_type:
                try:
                    # Check if it's JSON
                    data = response.json()
                    if isinstance(data, dict) and "image" in data:
                        return base64.b64decode(data["image"])
                    elif isinstance(data, dict) and "data" in data:
                        return base64.b64decode(data["data"])
                except (json.JSONDecodeError, ValueError):
                    # Not JSON, might be raw base64 string
                    try:
                        return base64.b64decode(response.text)
                    except Exception:
                        return response.content

            elif "image" in content_type:
                return response.content
            else:
                # Unknown format, try base64 decode
                try:
                    return base64.b64decode(response.text)
                except Exception:
                    return response.content

        except requests.exceptions.ConnectionError as e:
            raise ViaVerdeConnectionError(
                f"Failed to connect to Via Verde API: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ViaVerdeAPIError(f"Error fetching camera {camera_id}: {e}") from e

    def get_camera_image_pil(
        self,
        camera_id: int,
        **kwargs: Any,
    ) -> Optional["Image.Image"]:  # type: ignore
        """
        Get camera image as PIL Image object.

        Requires the Pillow library to be installed.

        Args:
            camera_id: The ID of the camera
            **kwargs: Additional parameters to pass to get_camera_image

        Returns:
            PIL Image object, or None if PIL is not available

        Raises:
            ViaVerdeConnectionError: If connection to API fails
            ViaVerdeAPIError: If API returns an error
            ViaVerdeImageError: If image data cannot be opened
            ImportError: If Pillow is not installed

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> img = api.get_camera_image_pil(camera_id=29)
            >>> img.show()
        """
        if not PIL_AVAILABLE:
            raise ImportError(
                "Pillow is required for get_camera_image_pil(). "
                "Install it with: pip install Pillow"
            )

        image_data = self.get_camera_image(camera_id, **kwargs)

        try:
            return Image.open(BytesIO(image_data))
        except Exception as e:
            raise ViaVerdeImageError(f"Error opening image: {e}") from e

    def save_camera_image(
        self,
        camera_id: int,
        filepath: str,
        **kwargs: Any,
    ) -> bool:
        """
        Save camera image to file.

        Args:
            camera_id: The ID of the camera
            filepath: Path where to save the image
            **kwargs: Additional parameters to pass to get_camera_image

        Returns:
            True if saved successfully

        Raises:
            ViaVerdeConnectionError: If connection to API fails
            ViaVerdeAPIError: If API returns an error
            ViaVerdeImageError: If image cannot be saved

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> api.save_camera_image(camera_id=29, filepath="camera_29.jpg")
            True
        """
        image_data = self.get_camera_image(camera_id, **kwargs)

        try:
            with open(filepath, "wb") as f:
                f.write(image_data)
            return True
        except Exception as e:
            raise ViaVerdeImageError(f"Error saving image: {e}") from e

    def get_camera_url(self, camera_id: int) -> str:
        """
        Get the direct URL for a camera image.

        Note: This URL requires cookies from an active session to work.

        Args:
            camera_id: The ID of the camera

        Returns:
            URL string

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> url = api.get_camera_url(camera_id=29)
        """
        params = {
            "lang": self.language,
            "action": "cameraimage",
            "ts": int(time.time() * 1000),
        }

        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.BASE_URL}?{param_str}"

    def find_cameras(
        self,
        search: str,
        cameras: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for cameras by name or highway.

        Args:
            search: Search term (case-insensitive)
            cameras: Optional list of cameras to search in.
                    If not provided, fetches from API.

        Returns:
            List of matching camera dictionaries

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> cameras = api.find_cameras("A1")
            >>> print(f"Found {len(cameras)} cameras on A1")
        """
        if cameras is None:
            cameras = self.get_all_cameras()

        search_lower = search.lower()
        return [
            cam
            for cam in cameras
            if search_lower in cam.get("nomeCamara", "").lower()
            or search_lower in cam.get("nomeAe", "").lower()
        ]

    def get_camera_by_id(
        self,
        camera_id: int,
        cameras: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get camera metadata by ID.

        Args:
            camera_id: The ID of the camera
            cameras: Optional list of cameras to search in.
                    If not provided, fetches from API.

        Returns:
            Camera dictionary or None if not found

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> camera = api.get_camera_by_id(29)
            >>> print(f"Camera: {camera['nomeCamara']}")
        """
        if cameras is None:
            cameras = self.get_all_cameras()

        for cam in cameras:
            if cam.get("idCamara") == camera_id:
                return cam
        return None

    def __repr__(self) -> str:
        """Return string representation of the API client."""
        return f"ViaVerdeTrafficAPI(language='{self.language}')"
