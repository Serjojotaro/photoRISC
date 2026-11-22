from __future__ import annotations

import secrets
import uuid
from typing import Any

from pydantic import ValidationError

from app import db
from app.config import Settings
from app.effects import get_effect
from app.errors import APIError
from app.schemas import OperationInput


MAX_OPERATIONS = 30


def _invalid(detail: str) -> APIError:
    return APIError(
        status_code=422,
        code="invalid_recipe",
        title="Некорректный рецепт",
        detail=detail,
    )


def normalize_operations(operations: list[OperationInput]) -> list[dict[str, Any]]:
    if len(operations) > MAX_OPERATIONS:
        raise _invalid(f"В рецепте допустимо не более {MAX_OPERATIONS} операций.")
    normalized: list[dict[str, Any]] = []
    operation_ids: set[str] = set()
    for operation in operations:
        effect = get_effect(operation.type)
        if effect is None:
            raise _invalid(f"Эффект «{operation.type}» не найден.")
        try:
            params = effect.validate_params(operation.params)
        except ValidationError as exc:
            field = exc.errors()[0].get("loc", ("params",))
            field_name = ".".join(str(item) for item in field)
            raise _invalid(f"Проверьте параметр {field_name} эффекта «{effect.display_name}».") from exc
        operation_id = operation.id or str(uuid.uuid4())
        if operation_id in operation_ids:
            raise _invalid("Идентификаторы операций должны быть уникальны.")
        operation_ids.add(operation_id)
        if effect.uses_seed:
            seed = (
                operation.seed
                if operation.seed is not None
                else secrets.randbelow(2_147_483_648)
            )
        else:
            seed = None
        normalized.append(
            {
                "id": operation_id,
                "type": effect.effect_id,
                "enabled": operation.enabled,
                "params": params,
                "seed": seed,
            }
        )
    return normalized


def create_recipe(
    settings: Settings,
    asset_id: str,
    *,
    name: str,
    operations: list[OperationInput],
) -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise _invalid("Название рецепта не может быть пустым.")
    if db.get_asset(settings, asset_id) is None:
        raise APIError(
            status_code=404,
            code="asset_not_found",
            title="Изображение не найдено",
            detail="Исходное изображение отсутствует.",
        )
    document = {
        "schema_version": 1,
        "recipe_id": str(uuid.uuid4()),
        "source_asset_id": asset_id,
        "name": clean_name,
        "revision": 1,
        "operations": normalize_operations(operations),
    }
    return db.create_recipe(settings, document)


def update_recipe(
    settings: Settings,
    recipe_id: str,
    *,
    name: str,
    operations: list[OperationInput],
    revision: int,
) -> dict:
    clean_name = name.strip()
    if not clean_name:
        raise _invalid("Название рецепта не может быть пустым.")
    existing = db.get_recipe(settings, recipe_id)
    if existing is None:
        raise APIError(
            status_code=404,
            code="recipe_not_found",
            title="Рецепт не найден",
            detail="Запрошенный рецепт отсутствует.",
        )
    document = {
        **existing,
        "name": clean_name,
        "operations": normalize_operations(operations),
    }
    try:
        updated = db.update_recipe(settings, recipe_id, document, revision)
    except db.RecipeRevisionConflict as exc:
        raise APIError(
            status_code=409,
            code="recipe_revision_conflict",
            title="Рецепт уже изменён",
            detail="Перезагрузите рецепт и повторите сохранение.",
        ) from exc
    if updated is None:
        raise APIError(
            status_code=404,
            code="recipe_not_found",
            title="Рецепт не найден",
            detail="Запрошенный рецепт отсутствует.",
        )
    return updated


def recipe_snapshot_for_request(
    settings: Settings,
    *,
    recipe_id: str | None,
    asset_id: str | None,
    operations: list[OperationInput] | None,
    revision: int | None,
) -> tuple[dict, dict]:
    if recipe_id:
        recipe = db.get_recipe(settings, recipe_id)
        if recipe is None:
            raise APIError(
                status_code=404,
                code="recipe_not_found",
                title="Рецепт не найден",
                detail="Запрошенный рецепт отсутствует.",
            )
        asset = db.get_asset(settings, recipe["source_asset_id"])
        if asset is None:
            raise APIError(
                status_code=404,
                code="asset_not_found",
                title="Изображение не найдено",
                detail="Исходное изображение рецепта отсутствует.",
            )
        return recipe, asset

    if not asset_id or operations is None:
        raise _invalid("Нужно передать recipe_id либо asset_id и operations.")
    asset = db.get_asset(settings, asset_id)
    if asset is None:
        raise APIError(
            status_code=404,
            code="asset_not_found",
            title="Изображение не найдено",
            detail="Исходное изображение отсутствует.",
        )
    snapshot = {
        "schema_version": 1,
        "recipe_id": None,
        "source_asset_id": asset_id,
        "name": "Предпросмотр",
        "revision": revision or 0,
        "operations": normalize_operations(operations),
    }
    return snapshot, asset
