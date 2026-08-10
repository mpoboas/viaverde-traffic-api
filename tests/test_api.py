"""
Tests for the ViaVerde Traffic API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json

from viaverde_traffic import ViaVerdeTrafficAPI
from viaverde_traffic.exceptions import (
    ViaVerdeAPIError,
    ViaVerdeConnectionError,
    ViaVerdeImageError,
)


class TestViaVerdeTrafficAPI:
    """Tests for the ViaVerdeTrafficAPI class."""

    def test_init_default_values(self):
        """Test that API initializes with default values."""
        api = ViaVerdeTrafficAPI()
        assert api.language == "PT"
        assert api.timeout == 10
        assert not api._initialized

    def test_init_custom_values(self):
        """Test that API initializes with custom values."""
        api = ViaVerdeTrafficAPI(language="EN", timeout=30)
        assert api.language == "EN"
        assert api.timeout == 30

    def test_repr(self):
        """Test string representation."""
        api = ViaVerdeTrafficAPI()
        assert repr(api) == "ViaVerdeTrafficAPI(language='PT')"

    @patch("viaverde_traffic.api.requests.Session")
    def test_ensure_initialized_success(self, mock_session_class):
        """Test successful session initialization."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()
        api._ensure_initialized()

        assert api._initialized
        mock_session.get.assert_called_once()

    @patch("viaverde_traffic.api.requests.Session")
    def test_ensure_initialized_connection_error(self, mock_session_class):
        """Test connection error during initialization."""
        import requests

        mock_session = Mock()
        mock_session.get.side_effect = requests.exceptions.ConnectionError("Network error")
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()

        with pytest.raises(ViaVerdeConnectionError):
            api._ensure_initialized()

    @patch("viaverde_traffic.api.requests.Session")
    def test_get_all_cameras_success(self, mock_session_class):
        """Test successful camera list retrieval."""
        mock_response_json = {
            "Items": [
                {
                    "id": 1,
                    "name": "Camera 1",
                    "type": "CAMERA",
                    "roadId": 1,
                    "roadName": "A1",
                    "coordinates": {"latitude": 38.1, "longitude": -9.1},
                    "imageUrl": "https://s3.eu-west-1.amazonaws.com/brisa-vvservices-prod-images/CAM_1.png",
                },
                {
                    "id": 2,
                    "name": "Camera 2",
                    "type": "CAMERA",
                    "roadId": 2,
                    "roadName": "A2",
                    "coordinates": {"latitude": 38.2, "longitude": -9.2},
                    "imageUrl": "https://s3.eu-west-1.amazonaws.com/brisa-vvservices-prod-images/CAM_2.png",
                },
            ],
            "Page": 1,
            "PageSize": 100,
            "TotalCount": 2,
        }

        mock_session = Mock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = mock_response_json
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()
        api._initialized = True

        cameras = api.get_all_cameras()

        assert len(cameras) == 2
        assert cameras[0] == {
            "idCamara": 1,
            "nomeCamara": "Camera 1",
            "idAe": 1,
            "nomeAe": "A1",
            "Latitude": 38.1,
            "Longitude": -9.1,
            "imageUrl": "https://s3.eu-west-1.amazonaws.com/brisa-vvservices-prod-images/CAM_1.png",
        }

    @patch("viaverde_traffic.api.requests.Session")
    def test_get_camera_image_success(self, mock_session_class):
        """Test successful camera image retrieval."""
        mock_image_data = b"\x89PNG\r\n\x1a\n..."

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.content = mock_image_data
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()

        image = api.get_camera_image(camera_id=29)

        assert image == mock_image_data
        mock_session.get.assert_called_once_with(
            "https://s3.eu-west-1.amazonaws.com/brisa-vvservices-prod-images/CAM_29.png",
            timeout=api.timeout,
        )

    @patch("viaverde_traffic.api.requests.Session")
    def test_get_camera_image_not_found(self, mock_session_class):
        """Test camera image retrieval for a camera that does not exist."""
        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 403
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()

        with pytest.raises(ViaVerdeImageError):
            api.get_camera_image(camera_id=999999)

    @patch("viaverde_traffic.api.requests.Session")
    def test_save_camera_image_success(self, mock_session_class, tmp_path):
        """Test successful camera image save."""
        mock_image_data = b"\x89PNG\r\n\x1a\n..."

        mock_session = Mock()
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_response.content = mock_image_data
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()

        filepath = tmp_path / "test_image.jpg"
        result = api.save_camera_image(camera_id=29, filepath=str(filepath))

        assert result is True
        assert filepath.exists()
        assert filepath.read_bytes() == mock_image_data

    def test_find_cameras(self):
        """Test camera search functionality."""
        cameras = [
            {"idCamara": 1, "nomeCamara": "Porto Norte", "nomeAe": "A1"},
            {"idCamara": 2, "nomeCamara": "Lisboa Sul", "nomeAe": "A2"},
            {"idCamara": 3, "nomeCamara": "Coimbra", "nomeAe": "A1"},
        ]

        api = ViaVerdeTrafficAPI()

        # Search by highway
        a1_cams = api.find_cameras("A1", cameras=cameras)
        assert len(a1_cams) == 2

        # Search by name
        porto_cams = api.find_cameras("Porto", cameras=cameras)
        assert len(porto_cams) == 1
        assert porto_cams[0]["nomeCamara"] == "Porto Norte"

        # Case insensitive search
        lisboa_cams = api.find_cameras("LISBOA", cameras=cameras)
        assert len(lisboa_cams) == 1

    def test_get_camera_by_id(self):
        """Test getting camera by ID."""
        cameras = [
            {"idCamara": 1, "nomeCamara": "Camera 1"},
            {"idCamara": 2, "nomeCamara": "Camera 2"},
        ]

        api = ViaVerdeTrafficAPI()

        # Found
        cam = api.get_camera_by_id(1, cameras=cameras)
        assert cam is not None
        assert cam["nomeCamara"] == "Camera 1"

        # Not found
        cam = api.get_camera_by_id(999, cameras=cameras)
        assert cam is None

    def test_get_camera_url(self):
        """Test camera URL generation."""
        api = ViaVerdeTrafficAPI()
        url = api.get_camera_url(camera_id=29)

        assert url == (
            "https://s3.eu-west-1.amazonaws.com/brisa-vvservices-prod-images/CAM_29.png"
        )


class TestPerceptualHash:
    """Tests for the dHash-based perceptual image comparison helpers."""

    @pytest.fixture(autouse=True)
    def _require_pil(self):
        pytest.importorskip("PIL")

    @staticmethod
    def _ascending_gradient_image():
        from PIL import Image

        width, height = 9, 8
        pixels = [
            int(255 * x / (width - 1))
            for _y in range(height)
            for x in range(width)
        ]
        img = Image.new("L", (width, height))
        img.putdata(pixels)
        return img.convert("RGB")

    @staticmethod
    def _descending_gradient_image():
        from PIL import Image

        width, height = 9, 8
        pixels = [
            255 - int(255 * x / (width - 1))
            for _y in range(height)
            for x in range(width)
        ]
        img = Image.new("L", (width, height))
        img.putdata(pixels)
        return img.convert("RGB")

    @staticmethod
    def _ascending_gradient_with_single_pixel_noise():
        """Same as the ascending gradient but with one interior pixel
        nudged down slightly, flipping exactly one comparison bit."""
        from PIL import Image

        width, height = 9, 8
        pixels = [
            int(255 * x / (width - 1))
            for _y in range(height)
            for x in range(width)
        ]
        # Row 3, column 4: make it dip below column 3's value.
        noisy_index = 3 * width + 4
        pixels[noisy_index] = pixels[3 * width + 3] - 1
        img = Image.new("L", (width, height))
        img.putdata(pixels)
        return img.convert("RGB")

    def test_hash_is_identical_for_identical_images(self):
        img = self._ascending_gradient_image()
        h1 = ViaVerdeTrafficAPI._compute_image_hash(img)
        h2 = ViaVerdeTrafficAPI._compute_image_hash(img)
        assert h1 == h2

    def test_hash_distance_is_large_for_clearly_different_images(self):
        ascending = self._ascending_gradient_image()
        descending = self._descending_gradient_image()

        h1 = ViaVerdeTrafficAPI._compute_image_hash(ascending)
        h2 = ViaVerdeTrafficAPI._compute_image_hash(descending)
        distance = ViaVerdeTrafficAPI._hamming_distance(h1, h2)

        assert distance > 5

    def test_hash_distance_is_small_for_minor_noise(self):
        clean = self._ascending_gradient_image()
        noisy = self._ascending_gradient_with_single_pixel_noise()

        h1 = ViaVerdeTrafficAPI._compute_image_hash(clean)
        h2 = ViaVerdeTrafficAPI._compute_image_hash(noisy)
        distance = ViaVerdeTrafficAPI._hamming_distance(h1, h2)

        assert distance <= 5

    def test_hamming_distance_of_identical_hashes_is_zero(self):
        assert ViaVerdeTrafficAPI._hamming_distance(0b1010, 0b1010) == 0

    def test_hamming_distance_counts_differing_bits(self):
        assert ViaVerdeTrafficAPI._hamming_distance(0b1111, 0b0000) == 4


class TestExceptions:
    """Tests for custom exceptions."""

    def test_exception_hierarchy(self):
        """Test that all exceptions inherit from ViaVerdeError."""
        from viaverde_traffic.exceptions import ViaVerdeError

        assert issubclass(ViaVerdeConnectionError, ViaVerdeError)
        assert issubclass(ViaVerdeAPIError, ViaVerdeError)
        assert issubclass(ViaVerdeImageError, ViaVerdeError)

    def test_exception_messages(self):
        """Test exception messages."""
        error = ViaVerdeConnectionError("Connection failed")
        assert str(error) == "Connection failed"

        error = ViaVerdeAPIError("API error")
        assert str(error) == "API error"

        error = ViaVerdeImageError("Image error")
        assert str(error) == "Image error"
