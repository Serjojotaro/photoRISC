from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache

from app.config import Settings


VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{5}$")


@dataclass(frozen=True, slots=True)
class BuildInfo:
    version: str
    build_sha: str
    build_timestamp: str

    @property
    def display(self) -> str:
        return f"{self.version} {self.build_sha} {self.build_timestamp}"


def _read_version(settings: Settings) -> str:
    try:
        version = settings.version_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise RuntimeError(f"Version file is missing: {settings.version_file}") from exc
    if not VERSION_PATTERN.fullmatch(version):
        raise RuntimeError("VERSION must use MAJOR.MINOR.PATCH")
    return version


def _git_sha(settings: Settings) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=5", "HEAD"],
            cwd=settings.project_root,
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError("Cannot determine Git build SHA") from exc
    return result.stdout.strip()


def _validate_timestamp(value: str) -> str:
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RuntimeError("BUILD_TIMESTAMP must be ISO 8601") from exc
    return value


@lru_cache(maxsize=8)
def load_build_info(settings: Settings) -> BuildInfo:
    version = _read_version(settings)
    sha = os.getenv("BUILD_SHA", "").strip()
    timestamp = os.getenv("BUILD_TIMESTAMP", "").strip()

    if not sha or not timestamp:
        try:
            payload = json.loads(settings.build_info_file.read_text(encoding="utf-8"))
            sha = sha or str(payload.get("build_sha", "")).strip()
            timestamp = timestamp or str(payload.get("build_timestamp", "")).strip()
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    sha = sha or _git_sha(settings)
    timestamp = timestamp or datetime.now(UTC).isoformat(timespec="seconds").replace(
        "+00:00",
        "Z",
    )

    if not SHA_PATTERN.fullmatch(sha):
        raise RuntimeError("Build SHA must contain exactly five lowercase hex characters")
    timestamp = _validate_timestamp(timestamp)
    return BuildInfo(version=version, build_sha=sha, build_timestamp=timestamp)
