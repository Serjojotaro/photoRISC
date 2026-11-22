from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from app import db
from app.config import Settings
from app.errors import APIError


CHUNK_SIZE = 1024 * 1024
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True, slots=True)
class StoredAsset:
    id: str
    job_id: str
    display_name: str
    relative_path: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    orientation: int
    has_icc_profile: bool


def _safe_display_name(filename: str | None) -> str:
    candidate = Path((filename or "photo.jpg").replace("\\", "/")).name
    candidate = CONTROL_CHARACTERS.sub("", candidate).strip()
    if not candidate:
        candidate = "photo.jpg"
    return candidate[:255]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _inspect_jpeg(path: Path, settings: Settings) -> tuple[int, int, int, bool]:
    try:
        with Image.open(path) as image:
            if image.format != "JPEG":
                raise APIError(
                    status_code=415,
                    code="invalid_image",
                    title="Неподдерживаемый формат",
                    detail="В первом релизе можно загружать только JPEG.",
                )
            width, height = image.size
            if width <= 0 or height <= 0:
                raise ValueError("Invalid image dimensions")
            if width * height > settings.max_image_pixels:
                raise APIError(
                    status_code=422,
                    code="image_too_large",
                    title="Слишком большое изображение",
                    detail=(
                        f"Максимальный размер изображения — "
                        f"{settings.max_image_pixels} пикселей."
                    ),
                )
            orientation = int(image.getexif().get(274, 1))
            has_icc_profile = bool(image.info.get("icc_profile"))
            image.verify()
    except APIError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise APIError(
            status_code=422,
            code="invalid_image",
            title="Некорректное изображение",
            detail="Файл повреждён или не является JPEG.",
        ) from exc

    if orientation in {5, 6, 7, 8}:
        width, height = height, width
    return width, height, orientation, has_icc_profile


async def store_upload(upload: UploadFile, settings: Settings) -> StoredAsset:
    settings.ensure_directories()
    asset_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    temp_path = settings.temp_dir / f"upload-{asset_id}.tmp"
    destination_dir = settings.originals_dir / asset_id
    destination = destination_dir / "original.jpg"
    size = 0

    try:
        with temp_path.open("wb") as output:
            while chunk := await upload.read(CHUNK_SIZE):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    limit_mb = settings.max_upload_bytes // (1024 * 1024)
                    raise APIError(
                        status_code=413,
                        code="file_too_large",
                        title="Файл слишком большой",
                        detail=f"Максимальный размер файла — {limit_mb} МБ.",
                    )
                output.write(chunk)
        if size == 0:
            raise APIError(
                status_code=422,
                code="invalid_image",
                title="Пустой файл",
                detail="Загруженный файл не содержит данных.",
            )

        width, height, orientation, has_icc_profile = _inspect_jpeg(
            temp_path,
            settings,
        )
        checksum = _sha256(temp_path)
        destination_dir.mkdir(parents=True, exist_ok=False)
        temp_path.replace(destination)
        relative_path = destination.relative_to(settings.project_root).as_posix()
        display_name = _safe_display_name(upload.filename)

        db.insert_asset_with_thumbnail_job(
            settings,
            asset_id=asset_id,
            job_id=job_id,
            display_name=display_name,
            relative_path=relative_path,
            sha256=checksum,
            size_bytes=size,
            width=width,
            height=height,
            orientation=orientation,
            has_icc_profile=has_icc_profile,
        )
    except Exception:
        if destination.exists():
            destination.unlink(missing_ok=True)
        if destination_dir.exists():
            try:
                destination_dir.rmdir()
            except OSError:
                pass
        raise
    finally:
        temp_path.unlink(missing_ok=True)
        await upload.close()

    return StoredAsset(
        id=asset_id,
        job_id=job_id,
        display_name=display_name,
        relative_path=relative_path,
        sha256=checksum,
        size_bytes=size,
        width=width,
        height=height,
        orientation=orientation,
        has_icc_profile=has_icc_profile,
    )
