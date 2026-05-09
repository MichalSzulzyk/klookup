from __future__ import annotations

import io
from PIL import Image

TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
TARGET_RATIO = TARGET_WIDTH / TARGET_HEIGHT


def _center_crop_to_16_9(image: Image.Image) -> Image.Image:
    width, height = image.size
    ratio = width / height
    if abs(ratio - TARGET_RATIO) < 1e-6:
        return image

    if ratio > TARGET_RATIO:
        new_width = int(height * TARGET_RATIO)
        left = (width - new_width) // 2
        return image.crop((left, 0, left + new_width, height))

    new_height = int(width / TARGET_RATIO)
    top = (height - new_height) // 2
    return image.crop((0, top, width, top + new_height))


def validate_to_jpeg_1920x1080(image_bytes: bytes) -> tuple[bytes, tuple[int, int]]:
    with Image.open(io.BytesIO(image_bytes)) as img:
        original_size = img.size
        if img.mode not in ("RGB", "RGBA", "L"):
            img = img.convert("RGB")
        cropped = _center_crop_to_16_9(img)
        resized = cropped.resize((TARGET_WIDTH, TARGET_HEIGHT), Image.Resampling.LANCZOS)
        rgb = resized.convert("RGB")

        out = io.BytesIO()
        rgb.save(out, format="JPEG", quality=92, optimize=True, progressive=True)
        jpeg_bytes = out.getvalue()

    with Image.open(io.BytesIO(jpeg_bytes)) as check:
        if check.format != "JPEG" or check.size != (TARGET_WIDTH, TARGET_HEIGHT):
            raise ValueError("Output validation failed: expected JPEG 1920x1080")

    return jpeg_bytes, original_size
