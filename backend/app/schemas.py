from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: Literal["ok"]


class VersionResponse(BaseModel):
    version: str
    build_sha: str
    build_timestamp: str
    display: str


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    mime_type: str
    size_bytes: int
    width: int
    height: int
    sha256: str
    created_at: str
    thumbnail_status: Literal["pending", "ready", "failed"]
    thumbnail_url: str | None = None
    original_url: str


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
    limit: int
    offset: int


class JobResponse(BaseModel):
    id: str
    kind: str
    asset_id: str
    status: Literal["queued", "running", "completed", "failed"]
    error_code: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    output_url: str | None = None
    error: dict | None = None


class EffectResponse(BaseModel):
    id: str
    display_name: str
    description: str
    category: str
    implementation_version: int
    uses_seed: bool
    default_params: dict[str, Any]
    params_schema: dict[str, Any]


class EffectListResponse(BaseModel):
    items: list[EffectResponse]


class OperationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    type: str
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)


class RecipeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    name: str = Field(min_length=1, max_length=120)
    operations: list[OperationInput] = Field(default_factory=list, max_length=30)


class RecipeUpdate(RecipeCreate):
    revision: int = Field(ge=1)


class RecipeDocument(BaseModel):
    schema_version: Literal[1]
    recipe_id: str
    source_asset_id: str
    name: str
    revision: int
    operations: list[dict[str, Any]]


class RecipeListResponse(BaseModel):
    items: list[RecipeDocument]


class RenderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str | None = None
    asset_id: str | None = None
    mode: Literal["preview", "full"] = "preview"
    recipe_revision: int | None = Field(default=None, ge=0)
    operations: list[OperationInput] | None = Field(default=None, max_length=30)


class RenderResponse(BaseModel):
    render_id: str
    job_id: str
    status: str
    mode: str
    content_url: str | None = None
    error: dict | None = None


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    format: Literal["jpeg", "png"]
    quality: int | None = Field(default=None, ge=1, le=100)


class ExportResponse(BaseModel):
    export_id: str
    job_id: str
    status: str
    format: str
    size_bytes: int | None = None
    download_url: str | None = None
    error: dict | None = None
