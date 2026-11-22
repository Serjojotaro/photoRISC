from __future__ import annotations

import json
from pathlib import Path

from app import db
from app.config import Settings
from app.effects import get_effect
from app.imaging import load_image, write_image

def _output_location(
    settings: Settings,
    job: dict,
) -> tuple[Path, str, int | None, int | None]:
    job_id = job["id"]
    if job["kind"] == "preview":
        return (
            settings.previews_dir / f"{job_id}.jpg",
            "jpeg",
            settings.preview_quality,
            settings.preview_max_size,
        )
    if job["kind"] == "render":
        return settings.renders_dir / f"{job_id}.png", "png", None, None
    if job["kind"] == "export":
        output_format = job["output_format"] or "jpeg"
        extension = "jpg" if output_format == "jpeg" else "png"
        return (
            settings.exports_dir / f"{job_id}.{extension}",
            output_format,
            job["output_quality"],
            None,
        )
    raise ValueError(f"Unsupported job kind: {job['kind']}")


def process_render_job(settings: Settings, job: dict) -> None:
    asset = db.get_asset(settings, job["asset_id"])
    if asset is None:
        return
    recipe = json.loads(job["recipe_snapshot"]) if job["recipe_snapshot"] else None
    if not recipe:
        raise ValueError("Render job has no recipe snapshot")

    destination, output_format, quality, max_size = _output_location(settings, job)
    source = db.project_path(settings, asset["relative_path"])
    try:
        array, icc_profile = load_image(source, max_size=max_size)
        for operation in recipe["operations"]:
            if not operation.get("enabled", True):
                continue
            effect = get_effect(operation["type"])
            if effect is None:
                raise ValueError(f"Unknown effect: {operation['type']}")
            array = effect.apply(array, operation["params"], operation.get("seed"))

        write_image(
            settings,
            array,
            destination,
            output_format=output_format,
            quality=quality,
            icc_profile=icc_profile,
        )
        relative_path = destination.relative_to(settings.project_root).as_posix()
        completed = db.complete_job(
            settings,
            job_id=job["id"],
            output_relative_path=relative_path,
        )
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    if not completed:
        destination.unlink(missing_ok=True)
