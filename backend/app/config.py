from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 50_000_000


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    return float(raw) if raw else default


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    data_dir: Path
    database_path: Path
    version_file: Path
    build_info_file: Path
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS
    thumbnail_max_size: int = 512
    thumbnail_quality: int = 85
    preview_max_size: int = 1200
    preview_quality: int = 88
    worker_poll_interval: float = 0.5

    @property
    def originals_dir(self) -> Path:
        return self.data_dir / "originals"

    @property
    def thumbnails_dir(self) -> Path:
        return self.data_dir / "thumbnails"

    @property
    def temp_dir(self) -> Path:
        return self.data_dir / "temp"

    @property
    def previews_dir(self) -> Path:
        return self.data_dir / "previews"

    @property
    def renders_dir(self) -> Path:
        return self.data_dir / "renders"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_directories(self) -> None:
        for directory in (
            self.data_dir,
            self.originals_dir,
            self.thumbnails_dir,
            self.temp_dir,
            self.previews_dir,
            self.renders_dir,
            self.exports_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> "Settings":
        project_root = Path(
            os.getenv(
                "PROJECT_ROOT",
                str(Path(__file__).resolve().parents[2]),
            )
        ).resolve()
        data_value = Path(os.getenv("DATA_DIR", "data"))
        data_dir = data_value if data_value.is_absolute() else project_root / data_value
        database_value = Path(os.getenv("DATABASE_PATH", "data/photoRISC.sqlite3"))
        database_path = (
            database_value
            if database_value.is_absolute()
            else project_root / database_value
        )
        return cls(
            project_root=project_root,
            data_dir=data_dir.resolve(),
            database_path=database_path.resolve(),
            version_file=project_root / "VERSION",
            build_info_file=project_root / "build-info.json",
            max_upload_bytes=_env_int(
                "MAX_UPLOAD_BYTES",
                DEFAULT_MAX_UPLOAD_BYTES,
            ),
            max_image_pixels=_env_int(
                "MAX_IMAGE_PIXELS",
                DEFAULT_MAX_IMAGE_PIXELS,
            ),
            thumbnail_max_size=_env_int("THUMBNAIL_MAX_SIZE", 512),
            thumbnail_quality=_env_int("THUMBNAIL_QUALITY", 85),
            preview_max_size=_env_int("PREVIEW_MAX_SIZE", 1200),
            preview_quality=_env_int("PREVIEW_QUALITY", 88),
            worker_poll_interval=_env_float("WORKER_POLL_INTERVAL", 0.5),
        )
