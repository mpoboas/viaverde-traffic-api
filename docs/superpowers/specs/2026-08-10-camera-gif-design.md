# Design: `get_camera_gif` — animated GIF of a camera's recent distinct snapshots

## Context

`viaverde_traffic` is a Python client library (not an HTTP service) wrapping
Via Verde's traffic camera S3 snapshots. Each camera exposes a single static
URL (`CAM_{id}.png`) that always reflects the latest frame — there is no
history, versioning, or timestamp exposed by the upstream API. Cameras update
at irregular intervals (roughly every ~15 minutes on average, per the
maintainer, but with no guarantee).

The goal is a new public method that produces an animated GIF built from the
last few *visually distinct* snapshots of a camera, suitable for showing
"what's changed recently" at a glance.

## Requirements

- New method on `ViaVerdeTrafficAPI` (in `viaverde_traffic/api.py`) —
  no new service, no persistent storage, no background thread.
- Because the upstream has no history, the method must poll the camera over
  real time, detect when the image has visually changed, and collect up to 4
  distinct frames.
- The call blocks until either 4 distinct frames are collected or a maximum
  wait time elapses — whichever comes first. On timeout, it returns a GIF
  built from whatever frames were collected so far (even just 1).
- "Visually changed" must tolerate minor recompression/encoding noise from
  the upstream S3 asset — a byte-for-byte diff would false-positive on
  reprocessed-but-unchanged frames.
- No new hard dependency: reuse Pillow (already an optional extra used by
  `get_camera_image_pil`).

## API

```python
def get_camera_gif(
    self,
    camera_id: int,
    max_wait: float = 2700,       # 45 minutes
    poll_interval: float = 180,   # 3 minutes
    hash_threshold: int = 5,      # Hamming distance to call two frames "different"
) -> bytes:
    ...
```

Returns: GIF image data as `bytes` (mirrors `get_camera_image`'s `bytes`
return convention). A `save_camera_gif(camera_id, filepath, **kwargs)`
convenience wrapper follows the existing `save_camera_image` pattern.

### Behavior

1. Fetch the current frame via the existing `get_camera_image_pil`. Compute
   its perceptual hash (see below). This is frame #1, always kept.
2. Loop: sleep `poll_interval` seconds, fetch again, compute its hash.
   - Compare the new hash against the *last kept* frame's hash (Hamming
     distance). If the distance exceeds `hash_threshold`, keep this frame as
     the new "last kept" and append it to the collected list.
   - If a poll attempt raises `ViaVerdeConnectionError`/`ViaVerdeAPIError`
     (transient network issue), skip this attempt and continue polling —
     a single hiccup must not abort a 45-minute wait.
   - Stop the loop as soon as 4 frames are collected, or once elapsed time
     (measured via `time.monotonic`) reaches `max_wait`.
3. Build the GIF from the collected frames (1–4) with Pillow:
   `frames[0].save(buffer, format="GIF", save_all=True,
   append_images=frames[1:], duration=1000, loop=0)`.
4. Return the buffer's bytes.

### Perceptual hash (no new dependency)

Implemented as a small private helper using only Pillow:
- Convert to grayscale, resize to a small fixed size (e.g. 9x8) with
  `Image.resize`.
- Compute a **difference hash (dHash)**: for each row, compare adjacent
  pixel brightness (`pixel[x] > pixel[x+1]`) to produce a bit; pack the bits
  into an integer.
- Compare two hashes via Hamming distance (`bin(h1 ^ h2).count("1")`).

This is a well-known, dependency-free technique (no `imagehash` package
needed) and is robust to minor recompression noise while remaining sensitive
to real scene changes.

## Error handling

- `ImportError` if Pillow is not installed — same message pattern as
  `get_camera_image_pil`.
- `ViaVerdeImageError` if `camera_id` doesn't resolve to any image at all
  (first fetch fails with 403) — propagated from `get_camera_image`,
  consistent with existing methods.
- Transient per-poll network errors (`ViaVerdeConnectionError`,
  `ViaVerdeAPIError`) after the first successful fetch are swallowed and
  polling continues; they are not swallowed on the *first* fetch, since
  without at least one frame there's nothing to build a GIF from.

## Testing

Unit tests in `tests/test_api.py`, mocking `get_camera_image_pil` and time:

- 4 distinct frames arrive before `max_wait` → loop stops early, GIF has 4
  frames.
- Camera never changes → loop runs until `max_wait`, GIF has exactly 1
  frame.
- Some frames repeat (near-identical hash) between real changes → repeats
  are correctly skipped, only distinct frames kept.
- A transient `ViaVerdeConnectionError` on one poll attempt does not abort
  the loop; polling resumes on the next interval.
- `time.sleep`/`time.monotonic` are mocked/patched so tests run instantly
  rather than waiting real minutes.
- dHash helper: unit-tested directly with two clearly different images and
  two near-identical images (e.g. same image re-saved at different JPEG
  quality) to confirm the threshold behaves as expected.

## Out of scope

- Any HTTP server/route exposing this over the network — this is purely a
  library method. A future thin HTTP wrapper could call this method
  directly, but building one is not part of this change.
- Persistent caching of frames across separate `get_camera_gif` calls or
  process restarts.
