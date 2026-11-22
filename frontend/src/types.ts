export interface BuildVersion {
  version: string;
  build_sha: string;
  build_timestamp: string;
  display: string;
}

export type ThumbnailStatus = "pending" | "ready" | "failed";

export interface Asset {
  id: string;
  display_name: string;
  mime_type: string;
  size_bytes: number;
  width: number;
  height: number;
  sha256: string;
  created_at: string;
  thumbnail_status: ThumbnailStatus;
  thumbnail_url: string | null;
  original_url: string;
}

export interface AssetList {
  items: Asset[];
  total: number;
  limit: number;
  offset: number;
}

export interface APIProblem {
  title?: string;
  detail?: string;
  code?: string;
  status?: number;
  request_id?: string;
}

export interface ParameterSchema {
  type?: string;
  title?: string;
  description?: string;
  default?: unknown;
  minimum?: number;
  maximum?: number;
  enum?: string[];
}

export interface ParamsSchema {
  type: "object";
  properties: Record<string, ParameterSchema>;
  required?: string[];
}

export interface EffectDefinition {
  id: string;
  display_name: string;
  description: string;
  category: string;
  implementation_version: number;
  uses_seed: boolean;
  default_params: Record<string, unknown>;
  params_schema: ParamsSchema;
}

export interface Operation {
  id: string;
  type: string;
  enabled: boolean;
  params: Record<string, unknown>;
  seed: number | null;
}

export interface RecipeDocument {
  schema_version: 1;
  recipe_id: string;
  source_asset_id: string;
  name: string;
  revision: number;
  operations: Operation[];
}

export interface RenderJob {
  render_id: string;
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  mode: "preview" | "full";
  content_url: string | null;
  error: { code: string; message: string } | null;
}

export interface ExportJob {
  export_id: string;
  job_id: string;
  status: "queued" | "running" | "completed" | "failed";
  format: "jpeg" | "png";
  size_bytes: number | null;
  download_url: string | null;
  error: { code: string; message: string } | null;
}
