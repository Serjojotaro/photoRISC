import type {
  Asset,
  AssetList,
  BuildVersion,
  EffectDefinition,
  ExportJob,
  Operation,
  RecipeDocument,
  RenderJob,
} from "./types";

const API_ROOT = "/api/v1";

export class APIError extends Error {
  constructor(
    message: string,
    readonly code?: string,
  ) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, init);
  if (!response.ok) {
    let message = "Не удалось выполнить запрос.";
    let code: string | undefined;
    try {
      const problem = await response.json();
      message = problem.detail || problem.title || message;
      code = problem.code;
    } catch {
      // The fallback message remains user-safe when the server returns no JSON.
    }
    throw new APIError(message, code);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return response.json() as Promise<T>;
}

export function getVersion(): Promise<BuildVersion> {
  return request<BuildVersion>("/version");
}

export function getAssets(offset = 0): Promise<AssetList> {
  return request<AssetList>(`/assets?limit=50&offset=${offset}`);
}

export async function uploadAsset(file: File): Promise<Asset> {
  const form = new FormData();
  form.append("file", file);
  return request<Asset>("/assets", {
    method: "POST",
    body: form,
  });
}

export function deleteAsset(assetId: string): Promise<void> {
  return request<void>(`/assets/${encodeURIComponent(assetId)}`, {
    method: "DELETE",
  });
}

export async function getEffects(): Promise<EffectDefinition[]> {
  const response = await request<{ items: EffectDefinition[] }>("/effects");
  return response.items;
}

export async function getRecipes(assetId: string): Promise<RecipeDocument[]> {
  const response = await request<{ items: RecipeDocument[] }>(
    `/assets/${encodeURIComponent(assetId)}/recipes`,
  );
  return response.items;
}

export function createRecipe(
  assetId: string,
  name: string,
  operations: Operation[],
): Promise<RecipeDocument> {
  return request<RecipeDocument>(
    `/assets/${encodeURIComponent(assetId)}/recipes`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schema_version: 1, name, operations }),
    },
  );
}

export function updateRecipe(
  recipe: RecipeDocument,
  name: string,
  operations: Operation[],
): Promise<RecipeDocument> {
  return request<RecipeDocument>(
    `/recipes/${encodeURIComponent(recipe.recipe_id)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        schema_version: 1,
        name,
        revision: recipe.revision,
        operations,
      }),
    },
  );
}

export function createPreview(
  assetId: string,
  operations: Operation[],
  revision: number,
): Promise<RenderJob> {
  return request<RenderJob>("/renders", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      asset_id: assetId,
      mode: "preview",
      recipe_revision: revision,
      operations,
    }),
  });
}

export function getRender(renderId: string): Promise<RenderJob> {
  return request<RenderJob>(`/renders/${encodeURIComponent(renderId)}`);
}

export function createExport(
  recipeId: string,
  format: "jpeg" | "png",
  quality: number | null,
): Promise<ExportJob> {
  return request<ExportJob>("/exports", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ recipe_id: recipeId, format, quality }),
  });
}

export function getExport(exportId: string): Promise<ExportJob> {
  return request<ExportJob>(`/exports/${encodeURIComponent(exportId)}`);
}
