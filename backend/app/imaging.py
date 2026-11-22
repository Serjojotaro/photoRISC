from __future__ import annotations

import io
import os
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, ImageOps

from app.config import Settings


def _to_srgb(image: Image.Image) -> tuple[Image.Image, bytes]:
    oriented = ImageOps.exif_transpose(image)
    icc_profile = image.info.get("icc_profile")
    srgb_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    if icc_profile:
        try:
            normalized = ImageCms.profileToProfile(
                oriented,
                ImageCms.ImageCmsProfile(io.BytesIO(icc_profile)),
                srgb_profile,
                outputMode="RGB",
            )
            return normalized, srgb_profile.tobytes()
        except (OSError, ImageCms.PyCMSError, ValueError):
            pass
    if oriented.mode == "RGBA":
        return oriented, srgb_profile.tobytes()
    return oriented.convert("RGB"), srgb_profile.tobytes()


def load_image(
    source: Path,
    *,
    max_size: int | None = None,
) -> tuple[np.ndarray, bytes]:
    with Image.open(source) as opened:
        image, profile = _to_srgb(opened)
        if max_size and max(image.size) > max_size:
            image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        array = np.array(image, dtype=np.uint8)
    return array, profile


def write_image(
    settings: Settings,
    array: np.ndarray,
    destination: Path,
    *,
    output_format: str,
    quality: int | None,
    icc_profile: bytes | None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = settings.temp_dir / f"output-{uuid.uuid4()}.tmp"
    save_options: dict = {}
    if icc_profile:
        save_options["icc_profile"] = icc_profile

    try:
        image = Image.fromarray(array)
        if output_format == "jpeg":
            if image.mode == "RGBA":
                image = image.convert("RGB")
            image.save(
                temp_path,
                format="JPEG",
                quality=quality or 90,
                optimize=True,
                **save_options,
            )
        elif output_format == "png":
            image.save(temp_path, format="PNG", optimize=True, **save_options)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
        os.replace(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)
