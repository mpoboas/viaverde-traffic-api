# Camera GIF Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `get_camera_gif` method (and a `save_camera_gif` convenience wrapper) to `ViaVerdeTrafficAPI` that polls a camera until it collects up to 4 visually distinct frames, then returns them as an animated GIF.

**Architecture:** Everything lives in the existing `viaverde_traffic/api.py` (single-class module, following the codebase's current flat-file convention — no new files). A dependency-free perceptual hash (dHash) built on Pillow decides whether a newly-fetched frame is "different enough" from the last kept frame. The method blocks, sleeping `poll_interval` seconds between fetches, until either 4 distinct frames are collected or `max_wait` seconds elapse, then returns whatever frames it has as GIF bytes.

**Tech Stack:** Python 3.8+, Pillow (existing optional `pil` extra), pytest + unittest.mock (existing test stack).

## Global Constraints

- No new dependencies — perceptual hashing must be implemented with Pillow alone (spec: "no new hard dependency").
- `get_camera_gif` default `max_wait=2700` (45 min), default `poll_interval=180` (3 min), default `hash_threshold=5` (spec API section).
- A transient `ViaVerdeConnectionError`/`ViaVerdeAPIError` on a *poll* (not the first fetch) must not abort the loop — it is skipped and polling continues (spec: Error handling).
- On timeout, return a GIF built from whatever frames were collected, even if only 1 (spec: Requirements).
- `ImportError` if Pillow is not installed, matching the exact message pattern already used by `get_camera_image_pil` (spec: Error handling).
- Follow existing code style: `black` (line-length 88), `ruff`, `mypy` with `disallow_untyped_defs = true` — every new function needs full type hints.

---

### Task 1: CI Pillow install + perceptual hash helpers

**Files:**
- Modify: `.github/workflows/ci.yml:27` (install `pil` extra so PIL-dependent tests actually run in CI — currently only `.[dev]` is installed, so `get_camera_image_pil` and the new hash helpers would silently never run in CI)
- Modify: `viaverde_traffic/api.py` (add two static helpers near `_normalize_camera`, after line 188)
- Test: `tests/test_api.py` (new `TestPerceptualHash` class)

**Interfaces:**
- Produces: `ViaVerdeTrafficAPI._compute_image_hash(image: "Image.Image", hash_size: int = 8) -> int` — a dHash of the image, as an int.
- Produces: `ViaVerdeTrafficAPI._hamming_distance(hash1: int, hash2: int) -> int` — bit difference count between two hashes.

- [ ] **Step 1: Update CI to install Pillow so PIL-gated tests run**

In `.github/workflows/ci.yml`, change line 27 from:

```yaml
          pip install -e ".[dev]"
```

to:

```yaml
          pip install -e ".[dev,pil]"
```

- [ ] **Step 2: Write the failing tests for the hash helpers**

Add to `tests/test_api.py` (new top-level class, after `TestViaVerdeTrafficAPI`, before `class TestExceptions:`):

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_api.py::TestPerceptualHash -v`
Expected: FAIL with `AttributeError: type object 'ViaVerdeTrafficAPI' has no attribute '_compute_image_hash'`

- [ ] **Step 4: Implement the hash helpers**

In `viaverde_traffic/api.py`, add these two static methods immediately after `_normalize_camera` (after line 188, before `def get_camera_image`):

```python
    @staticmethod
    def _compute_image_hash(image: "Image.Image", hash_size: int = 8) -> int:
        """Compute a difference hash (dHash) for perceptual comparison."""
        resized = image.convert("L").resize(
            (hash_size + 1, hash_size), Image.LANCZOS
        )
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_api.py::TestPerceptualHash -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml viaverde_traffic/api.py tests/test_api.py
git commit -m "feat: add dHash-based perceptual image comparison helpers"
```

---

### Task 2: `get_camera_gif` method

**Files:**
- Modify: `viaverde_traffic/api.py` (add method after `save_camera_image`, i.e. after line 300)
- Test: `tests/test_api.py` (new `TestGetCameraGif` class)

**Interfaces:**
- Consumes: `ViaVerdeTrafficAPI._compute_image_hash(image, hash_size=8) -> int` and `ViaVerdeTrafficAPI._hamming_distance(hash1, hash2) -> int` from Task 1.
- Consumes: existing `get_camera_image_pil(camera_id) -> Optional[Image.Image]` (raises `ImportError`, `ViaVerdeConnectionError`, `ViaVerdeAPIError`, `ViaVerdeImageError`).
- Produces: `ViaVerdeTrafficAPI.get_camera_gif(self, camera_id: int, max_wait: float = 2700, poll_interval: float = 180, hash_threshold: int = 5) -> bytes`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api.py` (new top-level class, after `TestViaVerdeTrafficAPI`, before `TestPerceptualHash`):

```python
class TestGetCameraGif:
    """Tests for get_camera_gif's polling/dedup/GIF-assembly behavior."""

    @pytest.fixture(autouse=True)
    def _require_pil(self):
        pytest.importorskip("PIL")

    @staticmethod
    def _solid_image(value):
        from PIL import Image

        return Image.new("RGB", (9, 8), color=(value, value, value))

    @staticmethod
    def _gradient_image(reverse=False):
        from PIL import Image

        width, height = 9, 8
        pixels = [
            (255 - int(255 * x / (width - 1)))
            if reverse
            else int(255 * x / (width - 1))
            for _y in range(height)
            for x in range(width)
        ]
        img = Image.new("L", (width, height))
        img.putdata(pixels)
        return img.convert("RGB")

    @patch("viaverde_traffic.api.time.sleep")
    @patch("viaverde_traffic.api.time.monotonic")
    @patch.object(ViaVerdeTrafficAPI, "get_camera_image_pil")
    def test_collects_four_distinct_frames_then_stops(
        self, mock_get_pil, mock_monotonic, mock_sleep
    ):
        ascending = self._gradient_image(reverse=False)
        descending = self._gradient_image(reverse=True)
        mock_get_pil.side_effect = [ascending, descending, ascending, descending]
        mock_monotonic.side_effect = [0, 10, 20, 30, 40, 50, 60]

        api = ViaVerdeTrafficAPI()
        gif_bytes = api.get_camera_gif(camera_id=29, max_wait=2700, poll_interval=180)

        assert gif_bytes[:3] == b"GIF"
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(gif_bytes))
        assert img.n_frames == 4
        assert mock_get_pil.call_count == 4

    @patch("viaverde_traffic.api.time.sleep")
    @patch("viaverde_traffic.api.time.monotonic")
    @patch.object(ViaVerdeTrafficAPI, "get_camera_image_pil")
    def test_returns_single_frame_when_camera_never_changes(
        self, mock_get_pil, mock_monotonic, mock_sleep
    ):
        same_image = self._solid_image(128)
        mock_get_pil.side_effect = [same_image, same_image]
        # start=0; iter1: check(10)<100, sleep, check(20)<100 -> fetch (identical, dropped)
        # iter2: check(30)<100, sleep, check(100)>=100 -> break
        mock_monotonic.side_effect = [0, 10, 20, 30, 100]

        api = ViaVerdeTrafficAPI()
        gif_bytes = api.get_camera_gif(camera_id=29, max_wait=100, poll_interval=10)

        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(gif_bytes))
        assert getattr(img, "n_frames", 1) == 1
        assert mock_get_pil.call_count == 2

    @patch("viaverde_traffic.api.time.sleep")
    @patch("viaverde_traffic.api.time.monotonic")
    @patch.object(ViaVerdeTrafficAPI, "get_camera_image_pil")
    def test_transient_poll_error_does_not_abort_loop(
        self, mock_get_pil, mock_monotonic, mock_sleep
    ):
        ascending = self._gradient_image(reverse=False)
        descending = self._gradient_image(reverse=True)
        mock_get_pil.side_effect = [
            ascending,
            ViaVerdeConnectionError("network hiccup"),
            descending,
        ]
        # start=0; iter1: check(10)<100, sleep, check(20)<100 -> fetch raises, continue
        # iter2: check(30)<100, sleep, check(40)<100 -> fetch returns descending (distinct)
        # iter3: check(100)>=100 -> break
        mock_monotonic.side_effect = [0, 10, 20, 30, 40, 100]

        api = ViaVerdeTrafficAPI()
        gif_bytes = api.get_camera_gif(camera_id=29, max_wait=100, poll_interval=10)

        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(gif_bytes))
        assert img.n_frames == 2
        assert mock_get_pil.call_count == 3

    def test_raises_import_error_when_pil_unavailable(self):
        api = ViaVerdeTrafficAPI()
        with patch("viaverde_traffic.api.PIL_AVAILABLE", False):
            with pytest.raises(ImportError):
                api.get_camera_gif(camera_id=29)

    @patch("viaverde_traffic.api.time.sleep")
    @patch("viaverde_traffic.api.time.monotonic")
    @patch.object(ViaVerdeTrafficAPI, "get_camera_image_pil")
    def test_skips_repeated_frames_before_a_real_change(
        self, mock_get_pil, mock_monotonic, mock_sleep
    ):
        ascending = self._gradient_image(reverse=False)
        descending = self._gradient_image(reverse=True)
        # Camera returns the same frame twice (no real change), then changes.
        mock_get_pil.side_effect = [ascending, ascending, ascending, descending]
        # start=0; 3 poll iterations each doing 2 monotonic checks (all <2700),
        # then a final check (2700) breaks the loop even though only 2 of the
        # possible 4 frames were ever collected.
        mock_monotonic.side_effect = [0, 10, 20, 30, 40, 50, 60, 2700]

        api = ViaVerdeTrafficAPI()
        gif_bytes = api.get_camera_gif(camera_id=29, max_wait=2700, poll_interval=180)

        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(gif_bytes))
        # Only the initial frame and the one real change should be kept,
        # even though get_camera_image_pil was polled 4 times total.
        assert img.n_frames == 2
        assert mock_get_pil.call_count == 4
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::TestGetCameraGif -v`
Expected: FAIL with `AttributeError: 'ViaVerdeTrafficAPI' object has no attribute 'get_camera_gif'`

- [ ] **Step 3: Implement `get_camera_gif`**

In `viaverde_traffic/api.py`, add this method immediately after `save_camera_image` (after line 300, before `def get_camera_url`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py::TestGetCameraGif -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add viaverde_traffic/api.py tests/test_api.py
git commit -m "feat: add get_camera_gif method with change-detection polling"
```

---

### Task 3: `save_camera_gif` convenience wrapper

**Files:**
- Modify: `viaverde_traffic/api.py` (add method immediately after `get_camera_gif`)
- Test: `tests/test_api.py` (add tests to `TestGetCameraGif`)

**Interfaces:**
- Consumes: `ViaVerdeTrafficAPI.get_camera_gif(camera_id, max_wait=2700, poll_interval=180, hash_threshold=5) -> bytes` from Task 2.
- Produces: `ViaVerdeTrafficAPI.save_camera_gif(self, camera_id: int, filepath: str, max_wait: float = 2700, poll_interval: float = 180, hash_threshold: int = 5) -> bool`.

- [ ] **Step 1: Write the failing tests**

Add to `TestGetCameraGif` in `tests/test_api.py` (after `test_raises_import_error_when_pil_unavailable`):

```python
    @patch.object(ViaVerdeTrafficAPI, "get_camera_gif")
    def test_save_camera_gif_writes_bytes_to_file(self, mock_get_gif, tmp_path):
        mock_get_gif.return_value = b"GIF89a...fake gif bytes..."

        api = ViaVerdeTrafficAPI()
        filepath = tmp_path / "camera_29.gif"
        result = api.save_camera_gif(camera_id=29, filepath=str(filepath))

        assert result is True
        assert filepath.exists()
        assert filepath.read_bytes() == b"GIF89a...fake gif bytes..."
        mock_get_gif.assert_called_once_with(
            29, max_wait=2700, poll_interval=180, hash_threshold=5
        )

    @patch.object(ViaVerdeTrafficAPI, "get_camera_gif")
    def test_save_camera_gif_forwards_custom_kwargs(self, mock_get_gif, tmp_path):
        mock_get_gif.return_value = b"GIF89a..."

        api = ViaVerdeTrafficAPI()
        filepath = tmp_path / "camera_29.gif"
        api.save_camera_gif(
            camera_id=29,
            filepath=str(filepath),
            max_wait=60,
            poll_interval=5,
            hash_threshold=10,
        )

        mock_get_gif.assert_called_once_with(
            29, max_wait=60, poll_interval=5, hash_threshold=10
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api.py::TestGetCameraGif -v -k save_camera_gif`
Expected: FAIL with `AttributeError: 'ViaVerdeTrafficAPI' object has no attribute 'save_camera_gif'`

- [ ] **Step 3: Implement `save_camera_gif`**

In `viaverde_traffic/api.py`, add this method immediately after `get_camera_gif`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_api.py::TestGetCameraGif -v`
Expected: PASS (6 tests total in this class)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add viaverde_traffic/api.py tests/test_api.py
git commit -m "feat: add save_camera_gif convenience wrapper"
```

---

### Task 4: Documentation

**Files:**
- Modify: `README.md:126` (insert new API reference entries between `save_camera_image` and `find_cameras`)
- Modify: `README.md:56` (add a GIF example to the "With Pillow support" quick-start block)

**Interfaces:**
- Consumes: `get_camera_gif(camera_id, max_wait=2700, poll_interval=180, hash_threshold=5) -> bytes` and `save_camera_gif(camera_id, filepath, max_wait=2700, poll_interval=180, hash_threshold=5) -> bool` from Tasks 2–3. No new interfaces produced.

- [ ] **Step 1: Add the quick-start example**

In `README.md`, find this block (around line 53-55):

```python
# Get camera image as PIL Image (requires Pillow)
img = api.get_camera_image_pil(camera_id=29)
```

Add immediately after it:

```python

# Get an animated GIF of the camera's last few distinct snapshots
# (blocks, polling every 3 min, for up to 45 min — requires Pillow)
gif_bytes = api.get_camera_gif(camera_id=29)
```

- [ ] **Step 2: Add the API reference entries**

In `README.md`, insert this block between the end of the `save_camera_image` section (line 126) and the start of `##### find_cameras(search)` (line 128):

```markdown

##### `get_camera_gif(camera_id, max_wait=2700, poll_interval=180, hash_threshold=5)`

Poll a camera and return an animated GIF of its last up-to-4 visually
distinct snapshots. Since Via Verde only exposes each camera's latest
image (no history), this blocks — polling every `poll_interval` seconds —
until either 4 distinct frames are collected or `max_wait` seconds elapse,
whichever comes first. On timeout it returns whatever frames it collected,
even a single frame. Requires Pillow.

```python
gif_bytes = api.get_camera_gif(camera_id=29)
with open("camera_29.gif", "wb") as f:
    f.write(gif_bytes)
```

##### `save_camera_gif(camera_id, filepath, max_wait=2700, poll_interval=180, hash_threshold=5)`

Same as `get_camera_gif()`, but saves the result directly to a file.

```python
api.save_camera_gif(camera_id=29, filepath="camera_29.gif")
```
```

- [ ] **Step 3: Verify the README renders correctly**

Run: `grep -n "get_camera_gif\|save_camera_gif" README.md`
Expected: Entries appear in both the quick-start block and the API reference section, with no broken markdown (matching heading level `#####` and fenced code blocks used by neighboring entries).

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs: document get_camera_gif and save_camera_gif"
```
