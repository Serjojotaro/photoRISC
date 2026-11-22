from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.exceptions import RequestValidationError

from app import db
from app.config import Settings
from app.effects import list_effects
from app.errors import APIError
from app.recipes import create_recipe, recipe_snapshot_for_request, update_recipe
from app.schemas import (
    AssetListResponse,
    AssetResponse,
    EffectListResponse,
    EffectResponse,
    ExportRequest,
    ExportResponse,
    HealthResponse,
    JobResponse,
    RecipeCreate,
    RecipeDocument,
    RecipeListResponse,
    RecipeUpdate,
    RenderRequest,
    RenderResponse,
    VersionResponse,
)
from app.storage import store_upload


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _effect_response(effect) -> EffectResponse:
    return EffectResponse(
        id=effect.effect_id,
        display_name=effect.display_name,
        description=effect.description,
        category=effect.category,
        implementation_version=effect.implementation_version,
        uses_seed=effect.uses_seed,
        default_params=effect.default_params(),
        params_schema=effect.params_schema(),
    )


def _asset_response(request: Request, asset: dict) -> AssetResponse:
    asset_id = asset["id"]
    thumbnail_ready = asset["thumbnail_status"] == "ready"
    return AssetResponse(
        id=asset_id,
        display_name=asset["display_name"],
        mime_type=asset["mime_type"],
        size_bytes=asset["size_bytes"],
        width=asset["width"],
        height=asset["height"],
        sha256=asset["sha256"],
        created_at=asset["created_at"],
        thumbnail_status=asset["thumbnail_status"],
        thumbnail_url=(
            str(request.url_for("get_thumbnail", asset_id=asset_id))
            if thumbnail_ready
            else None
        ),
        original_url=str(
            request.url_for("get_original", asset_id=asset_id)
        ),
    )


def _job_error(job: dict) -> dict | None:
    if job["status"] != "failed":
        return None
    return {
        "code": job.get("error_code") or "render_failed",
        "message": "Не удалось обработать изображение.",
    }


def _render_response(request: Request, job: dict) -> RenderResponse:
    complete = job["status"] == "completed" and job.get("output_path")
    return RenderResponse(
        render_id=job["id"],
        job_id=job["id"],
        status=job["status"],
        mode="preview" if job["kind"] == "preview" else "full",
        content_url=(
            str(request.url_for("get_render_content", render_id=job["id"]))
            if complete
            else None
        ),
        error=_job_error(job),
    )


def _export_response(request: Request, job: dict) -> ExportResponse:
    path = (
        db.project_path(_settings(request), job["output_path"])
        if job.get("output_path")
        else None
    )
    return ExportResponse(
        export_id=job["id"],
        job_id=job["id"],
        status=job["status"],
        format=job.get("output_format") or "jpeg",
        size_bytes=path.stat().st_size if path and path.is_file() else None,
        download_url=(
            str(request.url_for("get_export_content", export_id=job["id"]))
            if path and path.is_file() and job["status"] == "completed"
            else None
        ),
        error=_job_error(job),
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/version", response_model=VersionResponse)
def version(request: Request) -> VersionResponse:
    build = request.app.state.build_info
    return VersionResponse(
        version=build.version,
        build_sha=build.build_sha,
        build_timestamp=build.build_timestamp,
        display=build.display,
    )


@router.get("/effects", response_model=EffectListResponse)
def get_effects() -> EffectListResponse:
    return EffectListResponse(
        items=[_effect_response(effect) for effect in list_effects()]
    )


@router.get("/effects/{effect_id}", response_model=EffectResponse)
def get_effect_definition(effect_id: str) -> EffectResponse:
    effect = next(
        (item for item in list_effects() if item.effect_id == effect_id),
        None,
    )
    if effect is None:
        raise APIError(
            status_code=404,
            code="unknown_effect",
            title="Эффект не найден",
            detail="Запрошенный эффект не зарегистрирован.",
        )
    return _effect_response(effect)


@router.post("/assets", response_model=AssetResponse, status_code=201)
async def upload_asset(
    request: Request,
    file: Annotated[UploadFile, File(...)],
) -> AssetResponse:
    settings = _settings(request)
    stored = await store_upload(file, settings)
    asset = db.get_asset(settings, stored.id)
    if asset is None:
        raise RuntimeError("Uploaded asset was not persisted")
    return _asset_response(request, asset)


@router.get("/assets", response_model=AssetListResponse)
def get_assets(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AssetListResponse:
    assets, total = db.list_assets(_settings(request), limit=limit, offset=offset)
    return AssetListResponse(
        items=[_asset_response(request, asset) for asset in assets],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/assets/{asset_id}", response_model=AssetResponse)
def get_asset(request: Request, asset_id: str) -> AssetResponse:
    asset = db.get_asset(_settings(request), asset_id)
    if asset is None:
        raise APIError(
            status_code=404,
            code="asset_not_found",
            title="Изображение не найдено",
            detail="Запрошенное изображение отсутствует в библиотеке.",
        )
    return _asset_response(request, asset)


@router.get("/assets/{asset_id}/original", name="get_original")
def get_original(request: Request, asset_id: str) -> FileResponse:
    settings = _settings(request)
    asset = db.get_asset(settings, asset_id)
    if asset is None:
        raise APIError(
            status_code=404,
            code="asset_not_found",
            title="Изображение не найдено",
            detail="Запрошенное изображение отсутствует в библиотеке.",
        )
    path = db.project_path(settings, asset["relative_path"])
    if not path.is_file():
        raise APIError(
            status_code=410,
            code="original_missing",
            title="Оригинал недоступен",
            detail="Файл оригинала отсутствует на диске.",
        )
    return FileResponse(
        path,
        media_type="image/jpeg",
        filename=f"{asset_id}.jpg",
        content_disposition_type="inline",
    )


@router.get("/assets/{asset_id}/thumbnail", name="get_thumbnail")
def get_thumbnail(request: Request, asset_id: str) -> FileResponse:
    settings = _settings(request)
    asset = db.get_asset(settings, asset_id)
    if asset is None:
        raise APIError(
            status_code=404,
            code="asset_not_found",
            title="Изображение не найдено",
            detail="Запрошенное изображение отсутствует в библиотеке.",
        )
    if asset["thumbnail_status"] == "pending":
        raise APIError(
            status_code=409,
            code="thumbnail_not_ready",
            title="Превью готовится",
            detail="Миниатюра изображения ещё не создана.",
        )
    if not asset.get("thumbnail_relative_path"):
        raise APIError(
            status_code=422,
            code="thumbnail_failed",
            title="Превью недоступно",
            detail="Не удалось создать миниатюру изображения.",
        )
    path = db.project_path(settings, asset["thumbnail_relative_path"])
    if not path.is_file():
        raise APIError(
            status_code=410,
            code="thumbnail_missing",
            title="Превью недоступно",
            detail="Файл миниатюры отсутствует на диске.",
        )
    return FileResponse(
        path,
        media_type="image/jpeg",
        filename=f"{asset_id}-thumbnail.jpg",
        content_disposition_type="inline",
    )


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(request: Request, asset_id: str) -> Response:
    settings = _settings(request)
    deleted = db.delete_asset(settings, asset_id)
    if deleted is None:
        raise APIError(
            status_code=404,
            code="asset_not_found",
            title="Изображение не найдено",
            detail="Запрошенное изображение отсутствует в библиотеке.",
        )
    db.remove_asset_files(settings, deleted)
    return Response(status_code=204)


@router.get(
    "/assets/{asset_id}/recipes",
    response_model=RecipeListResponse,
)
def get_recipes(request: Request, asset_id: str) -> RecipeListResponse:
    if db.get_asset(_settings(request), asset_id) is None:
        raise APIError(
            status_code=404,
            code="asset_not_found",
            title="Изображение не найдено",
            detail="Исходное изображение отсутствует.",
        )
    return RecipeListResponse(
        items=[
            RecipeDocument.model_validate(recipe)
            for recipe in db.list_recipes(_settings(request), asset_id)
        ]
    )


@router.post(
    "/assets/{asset_id}/recipes",
    response_model=RecipeDocument,
    status_code=201,
)
def post_recipe(
    request: Request,
    asset_id: str,
    payload: RecipeCreate,
) -> RecipeDocument:
    recipe = create_recipe(
        _settings(request),
        asset_id,
        name=payload.name,
        operations=payload.operations,
    )
    return RecipeDocument.model_validate(recipe)


@router.get("/recipes/{recipe_id}", response_model=RecipeDocument)
def get_recipe(request: Request, recipe_id: str) -> RecipeDocument:
    recipe = db.get_recipe(_settings(request), recipe_id)
    if recipe is None:
        raise APIError(
            status_code=404,
            code="recipe_not_found",
            title="Рецепт не найден",
            detail="Запрошенный рецепт отсутствует.",
        )
    return RecipeDocument.model_validate(recipe)


@router.put("/recipes/{recipe_id}", response_model=RecipeDocument)
def put_recipe(
    request: Request,
    recipe_id: str,
    payload: RecipeUpdate,
) -> RecipeDocument:
    recipe = update_recipe(
        _settings(request),
        recipe_id,
        name=payload.name,
        operations=payload.operations,
        revision=payload.revision,
    )
    return RecipeDocument.model_validate(recipe)


@router.delete("/recipes/{recipe_id}", status_code=204)
def remove_recipe(request: Request, recipe_id: str) -> Response:
    if not db.delete_recipe(_settings(request), recipe_id):
        raise APIError(
            status_code=404,
            code="recipe_not_found",
            title="Рецепт не найден",
            detail="Запрошенный рецепт отсутствует.",
        )
    return Response(status_code=204)


@router.post("/renders", response_model=RenderResponse, status_code=202)
def create_render(request: Request, payload: RenderRequest) -> RenderResponse:
    settings = _settings(request)
    recipe, asset = recipe_snapshot_for_request(
        settings,
        recipe_id=payload.recipe_id,
        asset_id=payload.asset_id,
        operations=payload.operations,
        revision=payload.recipe_revision,
    )
    job_id = str(uuid.uuid4())
    kind = "preview" if payload.mode == "preview" else "render"
    if kind == "preview":
        db.discard_queued_previews(settings, asset["id"])
    db.create_job(
        settings,
        job_id=job_id,
        kind=kind,
        asset_id=asset["id"],
        recipe_id=recipe.get("recipe_id"),
        recipe_revision=recipe.get("revision"),
        recipe_snapshot=recipe,
    )
    job = db.get_job(settings, job_id)
    if job is None:
        raise RuntimeError("Render job was not persisted")
    return _render_response(request, job)


@router.get("/renders/{render_id}", response_model=RenderResponse)
def get_render(request: Request, render_id: str) -> RenderResponse:
    job = db.get_job(_settings(request), render_id)
    if job is None or job["kind"] not in {"preview", "render"}:
        raise APIError(
            status_code=404,
            code="job_not_found",
            title="Рендер не найден",
            detail="Запрошенный рендер отсутствует.",
        )
    return _render_response(request, job)


@router.get("/renders/{render_id}/content", name="get_render_content")
def get_render_content(request: Request, render_id: str) -> FileResponse:
    job = db.get_job(_settings(request), render_id)
    if job is None or job["kind"] not in {"preview", "render"}:
        raise APIError(
            status_code=404,
            code="job_not_found",
            title="Рендер не найден",
            detail="Запрошенный рендер отсутствует.",
        )
    if job["status"] != "completed" or not job.get("output_path"):
        raise APIError(
            status_code=409,
            code="render_not_ready",
            title="Рендер ещё не готов",
            detail="Результат обработки пока недоступен.",
        )
    path = db.project_path(_settings(request), job["output_path"])
    if not path.is_file():
        raise APIError(
            status_code=410,
            code="render_missing",
            title="Файл рендера недоступен",
            detail="Результат обработки отсутствует на диске.",
        )
    return FileResponse(
        path,
        media_type="image/jpeg" if path.suffix == ".jpg" else "image/png",
        filename=path.name,
        content_disposition_type="inline",
    )


@router.post("/exports", response_model=ExportResponse, status_code=202)
def create_export(request: Request, payload: ExportRequest) -> ExportResponse:
    settings = _settings(request)
    recipe = db.get_recipe(settings, payload.recipe_id)
    if recipe is None:
        raise APIError(
            status_code=404,
            code="recipe_not_found",
            title="Рецепт не найден",
            detail="Для экспорта сначала сохраните рецепт.",
        )
    asset = db.get_asset(settings, recipe["source_asset_id"])
    if asset is None:
        raise APIError(
            status_code=404,
            code="asset_not_found",
            title="Изображение не найдено",
            detail="Исходное изображение отсутствует.",
        )
    quality = 92 if payload.format == "jpeg" and payload.quality is None else payload.quality
    if payload.format == "png":
        quality = None
    job_id = str(uuid.uuid4())
    db.create_job(
        settings,
        job_id=job_id,
        kind="export",
        asset_id=asset["id"],
        recipe_id=recipe["recipe_id"],
        recipe_revision=recipe["revision"],
        recipe_snapshot=recipe,
        output_format=payload.format,
        output_quality=quality,
    )
    job = db.get_job(settings, job_id)
    if job is None:
        raise RuntimeError("Export job was not persisted")
    return _export_response(request, job)


@router.get("/exports/{export_id}", response_model=ExportResponse)
def get_export(request: Request, export_id: str) -> ExportResponse:
    job = db.get_job(_settings(request), export_id)
    if job is None or job["kind"] != "export":
        raise APIError(
            status_code=404,
            code="job_not_found",
            title="Экспорт не найден",
            detail="Запрошенный экспорт отсутствует.",
        )
    return _export_response(request, job)


@router.get("/exports/{export_id}/content", name="get_export_content")
def get_export_content(request: Request, export_id: str) -> FileResponse:
    job = db.get_job(_settings(request), export_id)
    if job is None or job["kind"] != "export":
        raise APIError(
            status_code=404,
            code="job_not_found",
            title="Экспорт не найден",
            detail="Запрошенный экспорт отсутствует.",
        )
    if job["status"] != "completed" or not job.get("output_path"):
        raise APIError(
            status_code=409,
            code="export_not_ready",
            title="Экспорт ещё не готов",
            detail="Результат пока недоступен.",
        )
    path = db.project_path(_settings(request), job["output_path"])
    if not path.is_file():
        raise APIError(
            status_code=410,
            code="export_missing",
            title="Файл экспорта недоступен",
            detail="Результат отсутствует на диске.",
        )
    media_type = "image/jpeg" if path.suffix == ".jpg" else "image/png"
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        content_disposition_type="attachment",
    )


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(request: Request, job_id: str) -> JobResponse:
    job = db.get_job(_settings(request), job_id)
    if job is None:
        raise APIError(
            status_code=404,
            code="job_not_found",
            title="Задание не найдено",
            detail="Запрошенное задание отсутствует.",
        )
    return JobResponse(
        **job,
        output_url=(
            str(request.url_for("get_render_content", render_id=job_id))
            if job["kind"] in {"preview", "render"} and job.get("output_path")
            else str(request.url_for("get_export_content", export_id=job_id))
            if job["kind"] == "export" and job.get("output_path")
            else None
        ),
        error=_job_error(job),
    )


def register_exception_handlers(app) -> None:
    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "type": f"https://photoRISC.local/errors/{exc.code}",
                "title": exc.title,
                "status": exc.status_code,
                "detail": exc.detail,
                "code": exc.code,
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        logger.info("Request validation failed: %s", exc.errors())
        return JSONResponse(
            status_code=422,
            content={
                "type": "https://photoRISC.local/errors/invalid_request",
                "title": "Некорректный запрос",
                "status": 422,
                "detail": "Проверьте переданные параметры.",
                "code": "invalid_request",
                "request_id": getattr(request.state, "request_id", ""),
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        logger.exception(
            "Unhandled API error: request_id=%s",
            getattr(request.state, "request_id", ""),
        )
        return JSONResponse(
            status_code=500,
            content={
                "type": "https://photoRISC.local/errors/internal_error",
                "title": "Внутренняя ошибка",
                "status": 500,
                "detail": "Не удалось выполнить запрос.",
                "code": "internal_error",
                "request_id": getattr(request.state, "request_id", ""),
            },
        )
