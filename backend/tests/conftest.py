from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.build_info import BuildInfo
from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    project_root = tmp_path / "photoRISC"
    project_root.mkdir()
    (project_root / "VERSION").write_text("0.1.2\n", encoding="utf-8")
    return Settings(
        project_root=project_root,
        data_dir=project_root / "data",
        database_path=project_root / "data" / "photoRISC.sqlite3",
        version_file=project_root / "VERSION",
        build_info_file=project_root / "build-info.json",
        max_upload_bytes=2 * 1024 * 1024,
        max_image_pixels=1_000_000,
    )


@pytest.fixture
def build_info() -> BuildInfo:
    return BuildInfo(
        version="0.1.2",
        build_sha="abc12",
        build_timestamp="2026-11-22T18:30:00Z",
    )


@pytest.fixture
def app(settings: Settings, build_info: BuildInfo):
    return create_app(settings, build_info)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def make_jpeg(
    size: tuple[int, int] = (1200, 800),
    color: tuple[int, ...] = (200, 60, 30),
    *,
    mode: str = "RGB",
    orientation: int | None = None,
) -> bytes:
    output = io.BytesIO()
    image = Image.new(mode, size, color)
    save_options = {"format": "JPEG", "quality": 90}
    if orientation is not None:
        exif = Image.Exif()
        exif[274] = orientation
        save_options["exif"] = exif
    image.save(output, **save_options)
    return output.getvalue()


@pytest.fixture
def jpeg_bytes() -> bytes:
    return make_jpeg()
