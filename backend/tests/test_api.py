from __future__ import annotations

import hashlib
import io
from dataclasses import replace

from fastapi.testclient import TestClient
from PIL import Image

from app import db
from app.config import Settings
from app.main import create_app
from app.worker import process_next_job
from tests.conftest import make_jpeg


def upload(client: TestClient, content: bytes, name: str = "photo.jpg"):
    return client.post(
        "/api/v1/assets",
        files={"file": (name, content, "image/jpeg")},
    )


def test_health_and_version(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.headers["cache-control"] == "no-store"
    assert health.json() == {"status": "ok"}

    version = client.get("/api/v1/version")
    assert version.status_code == 200
    assert version.json() == {
        "version": "0.1.0",
        "build_sha": "abc12",
        "build_timestamp": "2026-11-22T18:30:00Z",
        "display": "0.1.0 abc12 2026-11-22T18:30:00Z",
    }


def test_upload_thumbnail_and_original(
    client: TestClient,
    settings: Settings,
    jpeg_bytes: bytes,
) -> None:
    response = upload(client, jpeg_bytes)
    assert response.status_code == 201, response.text
    asset = response.json()
    assert asset["display_name"] == "photo.jpg"
    assert asset["thumbnail_status"] == "pending"
    assert asset["thumbnail_url"] is None
    assert asset["width"] == 1200
    assert asset["height"] == 800
    assert asset["sha256"] == hashlib.sha256(jpeg_bytes).hexdigest()

    original = client.get(asset["original_url"])
    assert original.status_code == 200
    assert original.content == jpeg_bytes

    pending_thumbnail = client.get(f"/api/v1/assets/{asset['id']}/thumbnail")
    assert pending_thumbnail.status_code == 409
    assert pending_thumbnail.json()["code"] == "thumbnail_not_ready"

    assert process_next_job(settings) is True
    detail = client.get(f"/api/v1/assets/{asset['id']}")
    assert detail.status_code == 200
    ready_asset = detail.json()
    assert ready_asset["thumbnail_status"] == "ready"
    assert ready_asset["thumbnail_url"].endswith("/thumbnail")

    thumbnail = client.get(ready_asset["thumbnail_url"])
    assert thumbnail.status_code == 200
    assert thumbnail.headers["content-type"] == "image/jpeg"
    assert client.get(asset["original_url"]).content == jpeg_bytes

    listing = client.get("/api/v1/assets")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == asset["id"]


def test_rejects_non_jpeg_with_jpeg_extension(
    client: TestClient,
) -> None:
    png_like = b"\x89PNG\r\n\x1a\nnot-a-real-jpeg"
    response = upload(client, png_like)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_image"
    assert client.get("/api/v1/assets").json()["total"] == 0


def test_detects_jpeg_content_regardless_of_extension(
    client: TestClient,
    jpeg_bytes: bytes,
) -> None:
    response = upload(client, jpeg_bytes, "photo.txt")
    assert response.status_code == 201
    assert response.json()["mime_type"] == "image/jpeg"


def test_repeated_upload_creates_distinct_assets(
    client: TestClient,
    jpeg_bytes: bytes,
) -> None:
    first = upload(client, jpeg_bytes)
    second = upload(client, jpeg_bytes)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert client.get("/api/v1/assets").json()["total"] == 2


def test_rejects_upload_over_size_limit(
    settings: Settings,
    build_info,
    jpeg_bytes: bytes,
) -> None:
    limited = replace(settings, max_upload_bytes=128)
    app = create_app(limited, build_info)
    with TestClient(app) as client:
        response = upload(client, jpeg_bytes)
    assert response.status_code == 413
    assert response.json()["code"] == "file_too_large"
    assert db.list_assets(limited, limit=50, offset=0)[1] == 0


def test_rejects_image_over_pixel_limit(
    settings: Settings,
    build_info,
) -> None:
    limited = replace(settings, max_image_pixels=100)
    app = create_app(limited, build_info)
    with TestClient(app) as client:
        response = upload(client, make_jpeg((200, 100)))
    assert response.status_code == 422
    assert response.json()["code"] == "image_too_large"


def test_asset_persists_after_app_restart(
    app,
    jpeg_bytes: bytes,
) -> None:
    with TestClient(app) as first_client:
        asset_id = upload(first_client, jpeg_bytes).json()["id"]
    with TestClient(app) as second_client:
        listing = second_client.get("/api/v1/assets")
    assert listing.status_code == 200
    assert listing.json()["items"][0]["id"] == asset_id


def test_delete_asset_removes_database_and_files(
    client: TestClient,
    settings: Settings,
    jpeg_bytes: bytes,
) -> None:
    asset = upload(client, jpeg_bytes).json()
    assert process_next_job(settings) is True
    original_path = settings.project_root / (
        db.get_asset(settings, asset["id"])["relative_path"]
    )
    thumbnail_path = settings.thumbnails_dir / f"{asset['id']}.jpg"
    assert original_path.is_file()
    assert thumbnail_path.is_file()

    response = client.delete(f"/api/v1/assets/{asset['id']}")
    assert response.status_code == 204
    assert db.get_asset(settings, asset["id"]) is None
    assert not original_path.exists()
    assert not thumbnail_path.exists()


def test_delete_asset_does_not_remove_other_assets(
    client: TestClient,
    settings: Settings,
    jpeg_bytes: bytes,
) -> None:
    first = upload(client, jpeg_bytes, "first.jpg").json()
    second = upload(client, jpeg_bytes, "second.jpg").json()
    assert process_next_job(settings) is True
    assert process_next_job(settings) is True

    response = client.delete(f"/api/v1/assets/{first['id']}")
    assert response.status_code == 204
    remaining = client.get("/api/v1/assets").json()
    assert remaining["total"] == 1
    assert remaining["items"][0]["id"] == second["id"]
    assert client.get(f"/api/v1/assets/{second['id']}/original").status_code == 200
    assert client.get(f"/api/v1/assets/{second['id']}/thumbnail").status_code == 200


def test_running_job_is_requeued(
    client: TestClient,
    settings: Settings,
    jpeg_bytes: bytes,
) -> None:
    asset = upload(client, jpeg_bytes).json()
    job = db.claim_next_job(settings)
    assert job is not None
    assert job["status"] == "running"

    assert db.recover_interrupted_jobs(settings) == 1
    recovered = db.get_job(settings, job["id"])
    assert recovered["status"] == "queued"

    assert process_next_job(settings) is True
    assert client.get(f"/api/v1/assets/{asset['id']}").json()[
        "thumbnail_status"
    ] == "ready"


def test_orientation_is_applied_to_reported_dimensions_and_thumbnail(
    client: TestClient,
    settings: Settings,
) -> None:
    source = make_jpeg((300, 200), orientation=6)
    asset = upload(client, source).json()
    assert asset["width"] == 200
    assert asset["height"] == 300
    assert process_next_job(settings) is True

    thumbnail = client.get(f"/api/v1/assets/{asset['id']}/thumbnail")
    assert thumbnail.status_code == 200
    with Image.open(io.BytesIO(thumbnail.content)) as image:
        assert image.size == (200, 300)


def test_cmyk_jpeg_thumbnail_is_normalized_to_rgb(
    client: TestClient,
    settings: Settings,
) -> None:
    source = make_jpeg((320, 240), (0, 120, 110, 0), mode="CMYK")
    asset = upload(client, source).json()
    assert process_next_job(settings) is True

    thumbnail = client.get(f"/api/v1/assets/{asset['id']}/thumbnail")
    assert thumbnail.status_code == 200
    with Image.open(io.BytesIO(thumbnail.content)) as image:
        assert image.mode == "RGB"


def test_recipe_crud_and_revision_conflict(
    client: TestClient,
    jpeg_bytes: bytes,
) -> None:
    asset = upload(client, jpeg_bytes).json()
    effects = client.get("/api/v1/effects")
    assert effects.status_code == 200
    assert len(effects.json()["items"]) == 17
    noise = client.get("/api/v1/effects/noise")
    assert noise.status_code == 200
    assert noise.json()["uses_seed"] is True
    assert client.get("/api/v1/effects/missing").status_code == 404

    create_response = client.post(
        f"/api/v1/assets/{asset['id']}/recipes",
        json={
            "schema_version": 1,
            "name": "Основной",
            "operations": [
                {
                    "id": "op-1",
                    "type": "noise",
                    "enabled": True,
                    "params": {"sigma": 20, "monochrome": False},
                    "seed": None,
                },
                {
                    "id": "op-2",
                    "type": "scanlines",
                    "enabled": False,
                    "params": {
                        "spacing": 4,
                        "thickness": 1,
                        "intensity": 0.4,
                        "orientation": "horizontal",
                    },
                    "seed": 999,
                },
            ],
        },
    )
    assert create_response.status_code == 201, create_response.text
    recipe = create_response.json()
    assert recipe["revision"] == 1
    assert recipe["operations"][0]["seed"] is not None
    assert recipe["operations"][1]["seed"] is None

    update_payload = {
        "schema_version": 1,
        "name": "Обновлённый",
        "revision": 1,
        "operations": recipe["operations"],
    }
    updated = client.put(
        f"/api/v1/recipes/{recipe['recipe_id']}",
        json=update_payload,
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert updated.json()["name"] == "Обновлённый"

    conflict = client.put(
        f"/api/v1/recipes/{recipe['recipe_id']}",
        json=update_payload,
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "recipe_revision_conflict"


def test_inline_preview_render_and_export(
    client: TestClient,
    settings: Settings,
    jpeg_bytes: bytes,
) -> None:
    asset = upload(client, jpeg_bytes).json()
    assert process_next_job(settings) is True
    operations = [
        {
            "id": "op-1",
            "type": "rgb_split",
            "enabled": True,
            "params": {
                "red_offset_x": 4,
                "red_offset_y": 0,
                "green_offset_x": 0,
                "green_offset_y": 0,
                "blue_offset_x": -4,
                "blue_offset_y": 0,
            },
            "seed": None,
        }
    ]
    preview = client.post(
        "/api/v1/renders",
        json={
            "asset_id": asset["id"],
            "mode": "preview",
            "recipe_revision": 0,
            "operations": operations,
        },
    )
    assert preview.status_code == 202, preview.text
    assert process_next_job(settings) is True
    preview_status = client.get(f"/api/v1/renders/{preview.json()['render_id']}")
    assert preview_status.status_code == 200
    assert preview_status.json()["status"] == "completed"
    preview_content = client.get(preview_status.json()["content_url"])
    assert preview_content.status_code == 200
    with Image.open(io.BytesIO(preview_content.content)) as image:
        assert max(image.size) <= settings.preview_max_size

    recipe = client.post(
        f"/api/v1/assets/{asset['id']}/recipes",
        json={
            "schema_version": 1,
            "name": "Экспорт",
            "operations": operations,
        },
    ).json()

    for output_format, quality in (("jpeg", 81), ("png", None)):
        export = client.post(
            "/api/v1/exports",
            json={
                "recipe_id": recipe["recipe_id"],
                "format": output_format,
                "quality": quality,
            },
        )
        assert export.status_code == 202, export.text
        export_id = export.json()["export_id"]
        assert process_next_job(settings) is True
        status = client.get(f"/api/v1/exports/{export_id}")
        assert status.status_code == 200
        assert status.json()["status"] == "completed"
        download = client.get(status.json()["download_url"])
        assert download.status_code == 200
        expected_type = "image/jpeg" if output_format == "jpeg" else "image/png"
        assert download.headers["content-type"] == expected_type
        with Image.open(io.BytesIO(download.content)) as image:
            assert image.size == (1200, 800)

    assert client.get(asset["original_url"]).content == jpeg_bytes
    export_job = db.get_job(settings, export_id)
    export_path = settings.project_root / export_job["output_path"]
    assert export_path.is_file()
    assert client.delete(f"/api/v1/assets/{asset['id']}").status_code == 204
    assert not export_path.exists()
