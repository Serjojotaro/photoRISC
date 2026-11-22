from __future__ import annotations

import io
import logging
import os
import uuid
from pathlib import Path

from PIL import Image, ImageCms, ImageOps

from app import db
from app.config import Settings


logger = logging.getLogger(__name__)


def _normalize_to_srgb(opened: Image.Image) -> tuple[Image.Image, bytes | None]:
    source = ImageOps.exif_transpose(opened)
    icc_profile = opened.info.get("icc_profile")
    if icc_profile:
        try:
            source_profile = ImageCms.ImageCmsProfile(
                io.BytesIO(icc_profile)
            )
            srgb_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
            normalized = ImageCms.profileToProfile(
                source,
                source_profile,
                srgb_profile,
                outputMode="RGB",
            )
            return normalized, srgb_profile.tobytes()
        except (OSError, ImageCms.PyCMSError, ValueError):
            logger.warning("ICC profile could not be applied; using Pillow conversion")
    return source.convert("RGB"), None


def _render_to_temp(settings: Settings, source: Path, destination: Path) -> None:
    temp_path = settings.temp_dir / f"thumbnail-{uuid.uuid4()}.jpg"
    try:
        with Image.open(source) as opened:
            image, output_profile = _normalize_to_srgb(opened)
            image.thumbnail(
                (settings.thumbnail_max_size, settings.thumbnail_max_size),
                Image.Resampling.LANCZOS,
            )
            save_options = {
                "format": "JPEG",
                "quality": settings.thumbnail_quality,
                "optimize": True,
            }
            if output_profile:
                save_options["icc_profile"] = output_profile
            image.save(temp_path, **save_options)
        os.replace(temp_path, destination)
    finally:
        temp_path.unlink(missing_ok=True)


def process_thumbnail_job(settings: Settings, job: dict) -> None:
    asset = db.get_asset(settings, job["asset_id"])
    if asset is None:
        return

    source = db.project_path(settings, asset["relative_path"])
    destination = settings.thumbnails_dir / f"{asset['id']}.jpg"
    relative_thumbnail = destination.relative_to(settings.project_root).as_posix()
    try:
        _render_to_temp(settings, source, destination)
        if not db.complete_thumbnail_job(
            settings,
            job_id=job["id"],
            asset_id=asset["id"],
            thumbnail_relative_path=relative_thumbnail,
        ):
            destination.unlink(missing_ok=True)
    except Exception:
        logger.exception(
            "Thumbnail job failed: job_id=%s asset_id=%s",
            job["id"],
            asset["id"],
        )
        destination.unlink(missing_ok=True)
        db.fail_job(
            settings,
            job_id=job["id"],
            asset_id=asset["id"],
            error_code="thumbnail_failed",
        )
