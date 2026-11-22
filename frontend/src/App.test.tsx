import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const version = {
  version: "0.0.1",
  build_sha: "abc12",
  build_timestamp: "2026-11-22T18:30:00Z",
  display: "0.0.1 abc12 2026-11-22T18:30:00Z",
};

const pendingAsset = {
  id: "asset-1",
  display_name: "forest.jpg",
  mime_type: "image/jpeg",
  size_bytes: 2048,
  width: 1200,
  height: 800,
  sha256: "hash",
  created_at: "2026-11-22T18:30:00Z",
  thumbnail_status: "pending",
  thumbnail_url: null,
  original_url: "/api/v1/assets/asset-1/original",
};

function jsonResponse(payload: unknown, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(payload), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("App", () => {
  it("shows the library and build version", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/version")) {
          return jsonResponse(version);
        }
        return jsonResponse({
          items: [pendingAsset],
          total: 1,
          limit: 50,
          offset: 0,
        });
      }),
    );

    render(<App />);

    expect(await screen.findByText("forest.jpg")).toBeInTheDocument();
    expect(screen.getByText("Готовим превью")).toBeInTheDocument();
    expect(
      screen.getByText("0.0.1 abc12 2026-11-22T18:30:00Z"),
    ).toBeInTheDocument();
  });

  it("uploads a selected JPEG", async () => {
    let uploaded = false;
    const fetchMock = vi.fn(
      (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/version")) {
          return jsonResponse(version);
        }
        if (init?.method === "POST") {
          uploaded = true;
          return jsonResponse(pendingAsset, 201);
        }
        return jsonResponse({
          items: [],
          total: 0,
          limit: 50,
          offset: 0,
        });
      },
    );
    vi.stubGlobal("fetch", fetchMock);

    const { container } = render(<App />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));

    const input = container.querySelector(
      'input[type="file"]',
    ) as HTMLInputElement;
    const file = new File(["jpeg"], "forest.jpg", { type: "image/jpeg" });
    await userEvent.upload(input, file);

    await waitFor(() => expect(uploaded).toBe(true));
    expect(await screen.findByText("forest.jpg")).toBeInTheDocument();
  });

  it("shows a safe fallback when version request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL) => {
        const url = String(input);
        if (url.endsWith("/version")) {
          return Promise.resolve(new Response("{}", { status: 500 }));
        }
        return jsonResponse({
          items: [],
          total: 0,
          limit: 50,
          offset: 0,
        });
      }),
    );

    render(<App />);
    expect(await screen.findByText("Версия недоступна")).toBeInTheDocument();
  });

  it("opens the editor, adds an effect and saves a recipe", async () => {
    const readyAsset = {
      ...pendingAsset,
      thumbnail_status: "ready",
      thumbnail_url: "/api/v1/assets/asset-1/thumbnail",
    };
    const noiseEffect = {
      id: "noise",
      display_name: "Шум",
      description: "Добавляет шум.",
      category: "digital",
      implementation_version: 1,
      uses_seed: true,
      default_params: { sigma: 18, monochrome: false },
      params_schema: {
        type: "object",
        properties: {
          sigma: {
            type: "number",
            title: "Сила шума",
            minimum: 0,
            maximum: 120,
          },
          monochrome: {
            type: "boolean",
            title: "Монохромный",
          },
        },
      },
    };
    const requestCapture: { body: Record<string, unknown> | null } = {
      body: null,
    };

    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        if (url.endsWith("/version")) {
          return jsonResponse(version);
        }
        if (url.endsWith("/effects")) {
          return jsonResponse({ items: [noiseEffect] });
        }
        if (url.endsWith("/recipes") && init?.method === "POST") {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          requestCapture.body = body;
          return jsonResponse(
            {
              schema_version: 1,
              recipe_id: "recipe-1",
              source_asset_id: readyAsset.id,
              name: "Мой рецепт",
              revision: 1,
              operations: body.operations,
            },
            201,
          );
        }
        if (url.endsWith("/recipes")) {
          return jsonResponse({ items: [] });
        }
        if (url.endsWith("/renders")) {
          return jsonResponse(
            {
              render_id: "render-1",
              job_id: "render-1",
              status: "completed",
              mode: "preview",
              content_url: "/api/v1/renders/render-1/content",
              error: null,
            },
            202,
          );
        }
        return jsonResponse({
          items: [readyAsset],
          total: 1,
          limit: 50,
          offset: 0,
        });
      }),
    );

    render(<App />);
    await userEvent.click(
      await screen.findByRole("button", { name: "Открыть редактор" }),
    );
    await userEvent.click(await screen.findByRole("button", { name: /Шум/ }));
    expect(screen.getByText("Сила шума")).toBeInTheDocument();

    await userEvent.click(screen.getByTitle("Отменить"));
    expect(screen.queryByText("Сила шума")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTitle("Повторить"));
    expect(screen.getByText("Сила шума")).toBeInTheDocument();

    await userEvent.click(
      screen.getByRole("button", { name: "Сохранить рецепт" }),
    );
    await waitFor(() => expect(requestCapture.body).not.toBeNull());
    expect(requestCapture.body?.operations).toHaveLength(1);
  });
});
