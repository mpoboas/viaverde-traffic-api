# 🚗 ViaVerde Traffic API

[![Python Version](https://img.shields.io/pypi/pyversions/viaverde-traffic)](https://pypi.org/project/viaverde-traffic/)
[![PyPI Version](https://img.shields.io/pypi/v/viaverde-traffic)](https://pypi.org/project/viaverde-traffic/)
[![License](https://img.shields.io/github/license/mpoboas/viaverde-traffic-api)](LICENSE)

A Python library to access Portuguese highway traffic camera images from the [Via Verde](https://www.viaverde.pt) website.

## ✨ Features

- 📷 **Get camera images** - Download traffic camera snapshots as bytes, PIL Images, or save directly to files
- 📍 **List all cameras** - Get metadata for all available traffic cameras including GPS coordinates
- 🔍 **Search cameras** - Find cameras by name or highway
- 🌐 **Session management** - Handles cookies and authentication automatically
- ⚡ **Simple API** - Easy to use with sensible defaults

## 📦 Installation

```bash
pip install viaverde-traffic
```

### With Pillow support (for PIL Image objects)

```bash
pip install viaverde-traffic[pil]
```

### For development

```bash
pip install viaverde-traffic[dev]
```

## 🚀 Quick Start

```python
from viaverde_traffic import ViaVerdeTrafficAPI

# Initialize the API client
api = ViaVerdeTrafficAPI()

# Get list of all available cameras
cameras = api.get_all_cameras()
print(f"Found {len(cameras)} cameras")

# Get camera image and save to file
api.save_camera_image(camera_id=29, filepath="camera_29.jpg")

# Get camera image as bytes
image_bytes = api.get_camera_image(camera_id=29)

# Get camera image as PIL Image (requires Pillow)
img = api.get_camera_image_pil(camera_id=29)
img.show()
```

## 📖 API Reference

### `ViaVerdeTrafficAPI`

The main client class for interacting with the Via Verde traffic API.

#### Constructor

```python
api = ViaVerdeTrafficAPI(
    language="PT",      # Language code (default: "PT")
    timeout=10,         # Request timeout in seconds (default: 10)
    user_agent=None,    # Custom User-Agent string (optional)
)
```

#### Methods

##### `get_all_cameras()`

Get a list of all available cameras with metadata.

```python
cameras = api.get_all_cameras()
for cam in cameras:
    print(f"{cam['nomeAe']}: {cam['nomeCamara']} (ID: {cam['idCamara']})")
```

Returns a list of dictionaries with:
- `idCamara` - Camera ID
- `nomeCamara` - Camera name
- `idAe` - Highway ID
- `nomeAe` - Highway name
- `Latitude` - GPS latitude
- `Longitude` - GPS longitude
- `imageUrl` - Direct URL to the camera's latest snapshot

> **Note:** The Via Verde API paginates this endpoint (100 cameras per page)
> and does not support paging through the rest, so `get_all_cameras()`
> returns the first page only. This matches the Via Verde website itself,
> which has the same limitation.

##### `get_camera_image(camera_id)`

Get camera image as bytes.

```python
image_bytes = api.get_camera_image(camera_id=29)
with open("camera.jpg", "wb") as f:
    f.write(image_bytes)
```

##### `get_camera_image_pil(camera_id)`

Get camera image as a PIL Image object. Requires Pillow.

```python
img = api.get_camera_image_pil(camera_id=29)
print(f"Image size: {img.size}")
img.show()
```

##### `save_camera_image(camera_id, filepath)`

Save camera image directly to a file.

```python
api.save_camera_image(camera_id=29, filepath="camera_29.jpg")
```

##### `find_cameras(search)`

Search for cameras by name or highway.

```python
a1_cameras = api.find_cameras("A1")
print(f"Found {len(a1_cameras)} cameras on A1")
```

##### `get_camera_by_id(camera_id)`

Get a specific camera's metadata by ID.

```python
camera = api.get_camera_by_id(29)
if camera:
    print(f"Camera: {camera['nomeCamara']}")
```

##### `get_camera_url(camera_id)`

Get the direct, publicly-accessible URL for a camera image (no session or cookies required).

```python
url = api.get_camera_url(camera_id=29)
```

## ⚠️ Exception Handling

The library provides custom exceptions for better error handling:

```python
from viaverde_traffic import (
    ViaVerdeTrafficAPI,
    ViaVerdeError,
    ViaVerdeConnectionError,
    ViaVerdeAPIError,
    ViaVerdeImageError,
)

api = ViaVerdeTrafficAPI()

try:
    cameras = api.get_all_cameras()
except ViaVerdeConnectionError as e:
    print(f"Connection error: {e}")
except ViaVerdeAPIError as e:
    print(f"API error: {e}")
except ViaVerdeError as e:
    print(f"General error: {e}")
```

### Exception Hierarchy

- `ViaVerdeError` - Base exception for all errors
  - `ViaVerdeConnectionError` - Network/connection errors
  - `ViaVerdeAPIError` - API response errors
  - `ViaVerdeImageError` - Image processing errors

## 📝 Examples

### Download all cameras on a highway

```python
from viaverde_traffic import ViaVerdeTrafficAPI

api = ViaVerdeTrafficAPI()

# Find all cameras on A1
a1_cameras = api.find_cameras("A1")

for camera in a1_cameras:
    cam_id = camera['idCamara']
    name = camera['nomeCamara'].replace(" ", "_")
    filename = f"a1_{cam_id}_{name}.jpg"
    
    api.save_camera_image(cam_id, filename)
    print(f"Saved: {filename}")
```

### Create a traffic monitor dashboard

```python
from viaverde_traffic import ViaVerdeTrafficAPI
import time

api = ViaVerdeTrafficAPI()

# Monitor specific cameras every 5 minutes
camera_ids = [29, 30, 31]

while True:
    for cam_id in camera_ids:
        timestamp = int(time.time())
        filename = f"camera_{cam_id}_{timestamp}.jpg"
        api.save_camera_image(cam_id, filename)
        print(f"Captured: {filename}")
    
    time.sleep(300)  # Wait 5 minutes
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/mpoboas/viaverde-traffic-api.git
cd viaverde-traffic-api

# Install in development mode
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black viaverde_traffic/
ruff check viaverde_traffic/ --fix

# Type checking
mypy viaverde_traffic/
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This library is an unofficial wrapper for the public Via Verde traffic information website. It is not affiliated with, endorsed by, or connected to Via Verde or Brisa Auto-Estradas de Portugal. Use responsibly and in accordance with Via Verde's terms of service.
