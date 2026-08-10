"""
ViaVerde Traffic API client.

This module provides a Python wrapper for accessing traffic camera images
from the Via Verde website.
"""

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
    IMAGE_BASE_URL = "https://s3.eu-west-1.amazonaws.com/brisa-vvservices-prod-images"

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

        Note: The Via Verde API paginates this endpoint (currently 100 cameras
        per page) and ignores pagination query parameters, so only the first
        page is returned. This matches the behavior of the Via Verde website
        itself, which does not page through the remaining results either.

        Returns:
            List of camera dictionaries with keys:
                - idCamara: Camera ID
                - nomeCamara: Camera name
                - idAe: Highway ID
                - nomeAe: Highway name
                - Latitude: GPS latitude
                - Longitude: GPS longitude
                - imageUrl: Direct URL to the camera's latest snapshot

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
            data = response.json()
        except requests.exceptions.ConnectionError as e:
            raise ViaVerdeConnectionError(
                f"Failed to connect to Via Verde API: {e}"
            ) from e
        except requests.exceptions.RequestException as e:
            raise ViaVerdeAPIError(f"Error fetching camera list: {e}") from e
        except json.JSONDecodeError as e:
            raise ViaVerdeAPIError(f"Error parsing camera list JSON: {e}") from e

        items = data.get("Items", []) if isinstance(data, dict) else data
        return [self._normalize_camera(item) for item in items]

    @staticmethod
    def _normalize_camera(camera: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize a raw camera entry from the API into the public shape."""
        coordinates = camera.get("coordinates") or {}
        return {
            "idCamara": camera.get("id"),
            "nomeCamara": camera.get("name"),
            "idAe": camera.get("roadId"),
            "nomeAe": camera.get("roadName"),
            "Latitude": coordinates.get("latitude"),
            "Longitude": coordinates.get("longitude"),
            "imageUrl": camera.get("imageUrl"),
        }

    @staticmethod
    def _compute_image_hash(image: "Image.Image", hash_size: int = 8) -> int:
        """Compute a difference hash (dHash) for perceptual comparison."""
        resized = image.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
        pixels = list(resized.getdata())
        bits = 0
        for row in range(hash_size):
            row_start = row * (hash_size + 1)
            for col in range(hash_size):
                bits <<= 1
                if pixels[row_start + col] > pixels[row_start + col + 1]:
                    bits |= 1
        return bits

    @staticmethod
    def _hamming_distance(hash1: int, hash2: int) -> int:
        """Count differing bits between two hashes."""
        return bin(hash1 ^ hash2).count("1")

    def get_camera_image(self, camera_id: int) -> bytes:
        """
        Get camera image as bytes.

        Args:
            camera_id: The ID of the camera

        Returns:
            Image data as bytes

        Raises:
            ViaVerdeConnectionError: If connection to API fails
            ViaVerdeAPIError: If API returns an error
            ViaVerdeImageError: If the camera image cannot be found

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> image_bytes = api.get_camera_image(camera_id=29)
            >>> with open("camera.jpg", "wb") as f:
            ...     f.write(image_bytes)
        """
        try:
            response = self.session.get(
                self.get_camera_url(camera_id),
                timeout=self.timeout,
            )
            if response.status_code == 403:
                raise ViaVerdeImageError(f"No image found for camera {camera_id}")
            response.raise_for_status()
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
    ) -> Optional["Image.Image"]:  # type: ignore
        """
        Get camera image as PIL Image object.

        Requires the Pillow library to be installed.

        Args:
            camera_id: The ID of the camera

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

        image_data = self.get_camera_image(camera_id)

        try:
            return Image.open(BytesIO(image_data))
        except Exception as e:
            raise ViaVerdeImageError(f"Error opening image: {e}") from e

    def save_camera_image(
        self,
        camera_id: int,
        filepath: str,
    ) -> bool:
        """
        Save camera image to file.

        Args:
            camera_id: The ID of the camera
            filepath: Path where to save the image

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
        image_data = self.get_camera_image(camera_id)

        try:
            with open(filepath, "wb") as f:
                f.write(image_data)
            return True
        except Exception as e:
            raise ViaVerdeImageError(f"Error saving image: {e}") from e

    def get_camera_gif(
        self,
        camera_id: int,
        max_wait: float = 2700,
        poll_interval: float = 180,
        hash_threshold: int = 5,
    ) -> bytes:
        """
        Get an animated GIF of a camera's recent, visually distinct snapshots.

        Since the Via Verde API only exposes each camera's latest snapshot
        (no history), this polls the camera over real time, keeping a frame
        each time it changes enough to exceed ``hash_threshold``. It blocks
        until either 4 distinct frames are collected or ``max_wait`` seconds
        elapse, whichever comes first. On timeout, it returns whatever
        frames were collected, even if only 1.

        Requires the Pillow library to be installed.

        Args:
            camera_id: The ID of the camera
            max_wait: Maximum total seconds to wait for 4 distinct frames
                (default: 2700, i.e. 45 minutes)
            poll_interval: Seconds to sleep between polls (default: 180)
            hash_threshold: Minimum perceptual hash distance between two
                frames to consider them "different" (default: 5)

        Returns:
            GIF image data as bytes

        Raises:
            ViaVerdeConnectionError: If the first fetch's connection fails
            ViaVerdeAPIError: If the first fetch's API call fails
            ViaVerdeImageError: If the camera image cannot be found
            ImportError: If Pillow is not installed

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> gif_bytes = api.get_camera_gif(camera_id=29)
            >>> with open("camera_29.gif", "wb") as f:
            ...     f.write(gif_bytes)
        """
        if not PIL_AVAILABLE:
            raise ImportError(
                "Pillow is required for get_camera_gif(). "
                "Install it with: pip install Pillow"
            )

        first_frame = self.get_camera_image_pil(camera_id)
        frames = [first_frame]
        last_hash = self._compute_image_hash(first_frame)

        start = time.monotonic()
        while len(frames) < 4:
            if time.monotonic() - start >= max_wait:
                break
            time.sleep(poll_interval)
            if time.monotonic() - start >= max_wait:
                break
            try:
                frame = self.get_camera_image_pil(camera_id)
            except (ViaVerdeConnectionError, ViaVerdeAPIError):
                continue
            frame_hash = self._compute_image_hash(frame)
            if self._hamming_distance(frame_hash, last_hash) > hash_threshold:
                frames.append(frame)
                last_hash = frame_hash

        buffer = BytesIO()
        rgb_frames = [f.convert("RGB") for f in frames]
        rgb_frames[0].save(
            buffer,
            format="GIF",
            save_all=True,
            append_images=rgb_frames[1:],
            duration=1000,
            loop=0,
        )
        return buffer.getvalue()

    def save_camera_gif(
        self,
        camera_id: int,
        filepath: str,
        max_wait: float = 2700,
        poll_interval: float = 180,
        hash_threshold: int = 5,
    ) -> bool:
        """
        Get an animated GIF of a camera's recent snapshots and save it to file.

        See get_camera_gif() for details on how frames are collected.

        Args:
            camera_id: The ID of the camera
            filepath: Path where to save the GIF
            max_wait: Maximum total seconds to wait for 4 distinct frames
                (default: 2700, i.e. 45 minutes)
            poll_interval: Seconds to sleep between polls (default: 180)
            hash_threshold: Minimum perceptual hash distance between two
                frames to consider them "different" (default: 5)

        Returns:
            True if saved successfully

        Raises:
            ViaVerdeConnectionError: If the first fetch's connection fails
            ViaVerdeAPIError: If the first fetch's API call fails
            ViaVerdeImageError: If the camera image cannot be found or saved
            ImportError: If Pillow is not installed

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> api.save_camera_gif(camera_id=29, filepath="camera_29.gif")
            True
        """
        gif_data = self.get_camera_gif(
            camera_id,
            max_wait=max_wait,
            poll_interval=poll_interval,
            hash_threshold=hash_threshold,
        )

        try:
            with open(filepath, "wb") as f:
                f.write(gif_data)
            return True
        except Exception as e:
            raise ViaVerdeImageError(f"Error saving GIF: {e}") from e

    def get_camera_url(self, camera_id: int) -> str:
        """
        Get the direct URL for a camera image.

        This URL is publicly accessible and does not require an active
        session or cookies.

        Args:
            camera_id: The ID of the camera

        Returns:
            URL string

        Example:
            >>> api = ViaVerdeTrafficAPI()
            >>> url = api.get_camera_url(camera_id=29)
        """
        return f"{self.IMAGE_BASE_URL}/CAM_{camera_id}.png"

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
