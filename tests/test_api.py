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
        mock_cameras = [
            {"idCamara": 1, "nomeCamara": "Camera 1", "nomeAe": "A1"},
            {"idCamara": 2, "nomeCamara": "Camera 2", "nomeAe": "A2"},
        ]

        mock_session = Mock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.json.return_value = mock_cameras
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()
        api._initialized = True

        cameras = api.get_all_cameras()

        assert cameras == mock_cameras
        assert len(cameras) == 2

    @patch("viaverde_traffic.api.requests.Session")
    def test_get_camera_image_success(self, mock_session_class):
        """Test successful camera image retrieval."""
        mock_image_data = b"\x89PNG\r\n\x1a\n..."

        mock_session = Mock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.content = mock_image_data
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()
        api._initialized = True

        image = api.get_camera_image(camera_id=29)

        assert image == mock_image_data

    @patch("viaverde_traffic.api.requests.Session")
    def test_get_camera_image_base64_json(self, mock_session_class):
        """Test camera image retrieval with base64 JSON response."""
        import base64

        mock_image_data = b"test image data"
        mock_json_response = {"image": base64.b64encode(mock_image_data).decode()}

        mock_session = Mock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = mock_json_response
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()
        api._initialized = True

        image = api.get_camera_image(camera_id=29)

        assert image == mock_image_data

    @patch("viaverde_traffic.api.requests.Session")
    def test_save_camera_image_success(self, mock_session_class, tmp_path):
        """Test successful camera image save."""
        mock_image_data = b"\x89PNG\r\n\x1a\n..."

        mock_session = Mock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_response.headers = {"Content-Type": "image/jpeg"}
        mock_response.content = mock_image_data
        mock_session.get.return_value = mock_response
        mock_session.headers = {}
        mock_session_class.return_value = mock_session

        api = ViaVerdeTrafficAPI()
        api._initialized = True

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

        assert "cameraimage" in url
        assert "lang=PT" in url


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
