import { useEffect, useMemo, useRef, useState } from "react";

import {
  APIError,
  createExport,
  createPreview,
  createRecipe,
  getEffects,
  getExport,
  getRecipes,
  getRender,
  updateRecipe,
} from "./api";
import ParamControl from "./ParamControl";
import type {
  Asset,
  EffectDefinition,
  ExportJob,
  Operation,
  RecipeDocument,
} from "./types";
import styles from "./Editor.module.css";

const CATEGORY_NAMES: Record<string, string> = {
  color: "Цвет",
  digital: "Цифровые следы",
  distortion: "Искажение",
  compression: "Сжатие",
  analog: "Аналоговое видео",
  datamosh: "Датамош",
};

function newSeed(): number {
  if (typeof crypto !== "undefined" && "getRandomValues" in crypto) {
    return crypto.getRandomValues(new Uint32Array(1))[0] % 2_147_483_648;
  }
  return Math.floor(Math.random() * 2_147_483_648);
}

function newOperation(effect: EffectDefinition): Operation {
  return {
    id: crypto.randomUUID(),
    type: effect.id,
    enabled: true,
    params: { ...effect.default_params },
    seed: effect.uses_seed ? newSeed() : null,
  };
}

function cloneOperations(operations: Operation[]): Operation[] {
  return operations.map((operation) => ({
    ...operation,
    params: { ...operation.params },
  }));
}

async function wait(ms: number): Promise<void> {
  await new Promise((resolve) => window.setTimeout(resolve, ms));
}

interface Props {
  asset: Asset;
  onBack: () => void;
}

export default function Editor({ asset, onBack }: Props) {
  const [effects, setEffects] = useState<EffectDefinition[]>([]);
  const [recipes, setRecipes] = useState<RecipeDocument[]>([]);
  const [recipeId, setRecipeId] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [recipeName, setRecipeName] = useState("Мой рецепт");
  const [operations, setOperations] = useState<Operation[]>([]);
  const [selectedOperationId, setSelectedOperationId] = useState<string | null>(
    null,
  );
  const [undoStack, setUndoStack] = useState<Operation[][]>([]);
  const [redoStack, setRedoStack] = useState<Operation[][]>([]);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewPending, setPreviewPending] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exportFormat, setExportFormat] = useState<"jpeg" | "png">("jpeg");
  const [exportQuality, setExportQuality] = useState(90);
  const [exportJob, setExportJob] = useState<ExportJob | null>(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const initialized = useRef(false);

  const effectMap = useMemo(
    () => new Map(effects.map((effect) => [effect.id, effect])),
    [effects],
  );
  const selectedOperation =
    operations.find((operation) => operation.id === selectedOperationId) ?? null;
  const selectedEffect = selectedOperation
    ? effectMap.get(selectedOperation.type) ?? null
    : null;

  useEffect(() => {
    let cancelled = false;
    Promise.all([getEffects(), getRecipes(asset.id)])
      .then(([availableEffects, savedRecipes]) => {
        if (cancelled) {
          return;
        }
        setEffects(availableEffects);
        setRecipes(savedRecipes);
        if (savedRecipes.length > 0) {
          const recipe = savedRecipes[0];
          setRecipeId(recipe.recipe_id);
          setRevision(recipe.revision);
          setRecipeName(recipe.name);
          setOperations(cloneOperations(recipe.operations));
          setSelectedOperationId(recipe.operations[0]?.id ?? null);
        }
        initialized.current = true;
      })
      .catch((cause) => {
        setError(
          cause instanceof Error
            ? cause.message
            : "Не удалось открыть редактор.",
        );
      });
    return () => {
      cancelled = true;
    };
  }, [asset.id]);

  useEffect(() => {
    if (!initialized.current) {
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setPreviewPending(true);
      setError(null);
      try {
        let render = await createPreview(asset.id, operations, revision);
        for (let attempt = 0; attempt < 80 && !cancelled; attempt += 1) {
          if (render.status === "completed" && render.content_url) {
            setPreviewUrl(`${render.content_url}?r=${render.render_id}`);
            return;
          }
          if (render.status === "failed") {
            throw new APIError(render.error?.message || "Ошибка предпросмотра.");
          }
          await wait(350);
          render = await getRender(render.render_id);
        }
        if (!cancelled) {
          throw new APIError("Предпросмотр выполняется слишком долго.");
        }
      } catch (cause) {
        if (!cancelled) {
          setError(
            cause instanceof Error
              ? cause.message
              : "Не удалось построить предпросмотр.",
          );
        }
      } finally {
        if (!cancelled) {
          setPreviewPending(false);
        }
      }
    }, 350);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [asset.id, operations, revision]);

  function commit(next: Operation[]) {
    setUndoStack((current) => [...current.slice(-39), operations]);
    setRedoStack([]);
    setOperations(next);
  }

  function undo() {
    const previous = undoStack.at(-1);
    if (!previous) {
      return;
    }
    setRedoStack((current) => [operations, ...current]);
    setUndoStack((current) => current.slice(0, -1));
    setOperations(cloneOperations(previous));
  }

  function redo() {
    const next = redoStack[0];
    if (!next) {
      return;
    }
    setUndoStack((current) => [...current, operations]);
    setRedoStack((current) => current.slice(1));
    setOperations(cloneOperations(next));
  }

  function addEffect(effect: EffectDefinition) {
    const operation = newOperation(effect);
    commit([...operations, operation]);
    setSelectedOperationId(operation.id);
  }

  function patchOperation(
    operationId: string,
    patch: Partial<Operation>,
    withHistory = true,
  ) {
    const next = operations.map((operation) =>
      operation.id === operationId ? { ...operation, ...patch } : operation,
    );
    if (withHistory) {
      commit(next);
    } else {
      setOperations(next);
    }
  }

  function updateParam(name: string, value: unknown) {
    if (!selectedOperation) {
      return;
    }
    const nextParams = { ...selectedOperation.params, [name]: value };
    patchOperation(selectedOperation.id, {
      params: nextParams,
    });
  }

  function removeOperation(operationId: string) {
    commit(operations.filter((operation) => operation.id !== operationId));
    if (selectedOperationId === operationId) {
      const fallback = operations.find((operation) => operation.id !== operationId);
      setSelectedOperationId(fallback?.id ?? null);
    }
  }

  function duplicateOperation(operationId: string) {
    const source = operations.find((operation) => operation.id === operationId);
    if (!source) {
      return;
    }
    const copy: Operation = {
      ...source,
      id: crypto.randomUUID(),
      params: { ...source.params },
      seed: source.seed === null ? null : newSeed(),
    };
    commit([...operations, copy]);
    setSelectedOperationId(copy.id);
  }

  function moveOperation(operationId: string, direction: -1 | 1) {
    const index = operations.findIndex((operation) => operation.id === operationId);
    const target = index + direction;
    if (index < 0 || target < 0 || target >= operations.length) {
      return;
    }
    const next = [...operations];
    [next[index], next[target]] = [next[target], next[index]];
    commit(next);
  }

  function dropOperation(targetId: string) {
    if (!draggingId || draggingId === targetId) {
      return;
    }
    const sourceIndex = operations.findIndex(
      (operation) => operation.id === draggingId,
    );
    const targetIndex = operations.findIndex(
      (operation) => operation.id === targetId,
    );
    const next = [...operations];
    const [moved] = next.splice(sourceIndex, 1);
    next.splice(targetIndex, 0, moved);
    setDraggingId(null);
    commit(next);
  }

  function selectRecipe(id: string) {
    if (!id) {
      setRecipeId(null);
      setRevision(0);
      setRecipeName("Мой рецепт");
      setOperations([]);
      setSelectedOperationId(null);
      setUndoStack([]);
      setRedoStack([]);
      return;
    }
    const recipe = recipes.find((item) => item.recipe_id === id);
    if (!recipe) {
      return;
    }
    setRecipeId(recipe.recipe_id);
    setRevision(recipe.revision);
    setRecipeName(recipe.name);
    setOperations(cloneOperations(recipe.operations));
    setSelectedOperationId(recipe.operations[0]?.id ?? null);
    setUndoStack([]);
    setRedoStack([]);
  }

  async function saveRecipe(): Promise<RecipeDocument | null> {
    setSaving(true);
    setError(null);
    try {
      const current = recipeId
        ? recipes.find((recipe) => recipe.recipe_id === recipeId)
        : null;
      const saved = current
        ? await updateRecipe(current, recipeName.trim(), operations)
        : await createRecipe(asset.id, recipeName.trim(), operations);
      setRecipeId(saved.recipe_id);
      setRevision(saved.revision);
      setRecipeName(saved.name);
      setRecipes((items) => [
        saved,
        ...items.filter((item) => item.recipe_id !== saved.recipe_id),
      ]);
      return saved;
    } catch (cause) {
      setError(
        cause instanceof APIError
          ? cause.message
          : "Не удалось сохранить рецепт.",
      );
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function exportImage() {
    setExporting(true);
    setExportJob(null);
    setError(null);
    try {
      const saved = await saveRecipe();
      if (!saved) {
        return;
      }
      let job = await createExport(
        saved.recipe_id,
        exportFormat,
        exportFormat === "jpeg" ? exportQuality : null,
      );
      setExportJob(job);
      for (let attempt = 0; attempt < 240; attempt += 1) {
        if (job.status === "completed" || job.status === "failed") {
          setExportJob(job);
          if (job.status === "failed") {
            throw new APIError(job.error?.message || "Ошибка экспорта.");
          }
          return;
        }
        await wait(500);
        job = await getExport(job.export_id);
        setExportJob(job);
      }
      throw new APIError("Экспорт выполняется слишком долго.");
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Не удалось экспортировать.",
      );
    } finally {
      setExporting(false);
    }
  }

  return (
    <main className={styles.editor}>
      <div className={styles.topbar}>
        <button className={styles.backButton} type="button" onClick={onBack}>
          ← Библиотека
        </button>
        <div className={styles.titleBlock}>
          <p>Редактор рецепта</p>
          <h1>{asset.display_name}</h1>
        </div>
        <button
          className={styles.saveButton}
          type="button"
          disabled={saving}
          onClick={() => void saveRecipe()}
        >
          {saving ? "Сохраняем…" : "Сохранить рецепт"}
        </button>
      </div>

      {error && (
        <div className={styles.error} role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)}>
            Закрыть
          </button>
        </div>
      )}

      <div className={styles.workspace}>
        <aside className={styles.effectsPanel}>
          <div className={styles.panelHeading}>
            <span>01</span>
            <h2>Эффекты</h2>
          </div>
          {Object.entries(
            effects.reduce<Record<string, EffectDefinition[]>>(
              (groups, effect) => {
                (groups[effect.category] ||= []).push(effect);
                return groups;
              },
              {},
            ),
          ).map(([category, categoryEffects]) => (
            <section className={styles.effectGroup} key={category}>
              <h3>{CATEGORY_NAMES[category] || category}</h3>
              {categoryEffects.map((effect) => (
                <button
                  className={styles.effectButton}
                  type="button"
                  key={effect.id}
                  onClick={() => addEffect(effect)}
                >
                  <span>{effect.display_name}</span>
                  <small>{effect.description}</small>
                </button>
              ))}
            </section>
          ))}
        </aside>

        <section className={styles.previewPanel}>
          <div className={styles.previewHeading}>
            <div>
              <span>02</span>
              <h2>Предпросмотр</h2>
            </div>
            <span className={styles.previewStatus}>
              {previewPending ? "Обработка…" : "Актуально"}
            </span>
          </div>
          <div className={styles.previewCanvas}>
            <img
              src={previewUrl || asset.original_url}
              alt={`Предпросмотр ${asset.display_name}`}
            />
            {previewPending && <div className={styles.previewLoader} />}
          </div>
          <div className={styles.recipeBar}>
            <select
              value={recipeId || ""}
              onChange={(event) => selectRecipe(event.target.value)}
              aria-label="Сохранённый рецепт"
            >
              <option value="">Новый рецепт</option>
              {recipes.map((recipe) => (
                <option key={recipe.recipe_id} value={recipe.recipe_id}>
                  {recipe.name}
                </option>
              ))}
            </select>
            <input
              value={recipeName}
              maxLength={120}
              onChange={(event) => setRecipeName(event.target.value)}
              aria-label="Название рецепта"
            />
          </div>
        </section>

        <aside className={styles.operationsPanel}>
          <div className={styles.panelHeading}>
            <span>03</span>
            <h2>Цепочка</h2>
            <div className={styles.historyButtons}>
              <button
                type="button"
                disabled={undoStack.length === 0}
                onClick={undo}
                title="Отменить"
              >
                ↶
              </button>
              <button
                type="button"
                disabled={redoStack.length === 0}
                onClick={redo}
                title="Повторить"
              >
                ↷
              </button>
            </div>
          </div>

          <div className={styles.operationList}>
            {operations.length === 0 ? (
              <p className={styles.emptyOperations}>
                Добавьте эффект, чтобы начать цепочку.
              </p>
            ) : (
              operations.map((operation, index) => {
                const effect = effectMap.get(operation.type);
                return (
                  <div
                    className={`${styles.operation} ${
                      selectedOperationId === operation.id
                        ? styles.operationSelected
                        : ""
                    }`}
                    key={operation.id}
                    draggable
                    onDragStart={() => setDraggingId(operation.id)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={() => dropOperation(operation.id)}
                    onClick={() => setSelectedOperationId(operation.id)}
                  >
                    <button
                      className={styles.dragHandle}
                      type="button"
                      aria-label="Переместить эффект"
                    >
                      ⠿
                    </button>
                    <button
                      className={`${styles.toggle} ${
                        operation.enabled ? styles.toggleOn : ""
                      }`}
                      type="button"
                      aria-label={
                        operation.enabled ? "Отключить эффект" : "Включить эффект"
                      }
                      onClick={(event) => {
                        event.stopPropagation();
                        patchOperation(operation.id, {
                          enabled: !operation.enabled,
                        });
                      }}
                    />
                    <div className={styles.operationName}>
                      <strong>{effect?.display_name || operation.type}</strong>
                      <span>{(index + 1).toString().padStart(2, "0")}</span>
                    </div>
                    <div className={styles.operationActions}>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          moveOperation(operation.id, -1);
                        }}
                        aria-label="Выше"
                      >
                        ↑
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          moveOperation(operation.id, 1);
                        }}
                        aria-label="Ниже"
                      >
                        ↓
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          duplicateOperation(operation.id);
                        }}
                        aria-label="Дублировать"
                      >
                        ⧉
                      </button>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          removeOperation(operation.id);
                        }}
                        aria-label="Удалить"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </div>

          {selectedOperation && selectedEffect && (
            <div className={styles.params}>
              <div className={styles.paramsHeading}>
                <h3>{selectedEffect.display_name}</h3>
                <p>{selectedEffect.description}</p>
              </div>
              {Object.entries(selectedEffect.params_schema.properties).map(
                ([name, schema]) => (
                  <ParamControl
                    key={name}
                    name={name}
                    schema={schema}
                    value={selectedOperation.params[name]}
                    onChange={(value) => updateParam(name, value)}
                  />
                ),
              )}
              {selectedOperation.seed !== null && (
                <div className={styles.seedRow}>
                  <span>Seed</span>
                  <code>{selectedOperation.seed}</code>
                  <button
                    type="button"
                    onClick={() =>
                      patchOperation(selectedOperation.id, {
                        seed: newSeed(),
                      })
                    }
                  >
                    Новый
                  </button>
                </div>
              )}
            </div>
          )}

          <section className={styles.exportPanel}>
            <h3>Экспорт</h3>
            <div className={styles.segmented}>
              <button
                className={exportFormat === "jpeg" ? styles.segmentActive : ""}
                type="button"
                onClick={() => setExportFormat("jpeg")}
              >
                JPEG
              </button>
              <button
                className={exportFormat === "png" ? styles.segmentActive : ""}
                type="button"
                onClick={() => setExportFormat("png")}
              >
                PNG
              </button>
            </div>
            {exportFormat === "jpeg" && (
              <label className={styles.quality}>
                <span>Качество JPEG</span>
                <output>{exportQuality}</output>
                <input
                  type="range"
                  min="1"
                  max="100"
                  value={exportQuality}
                  onChange={(event) =>
                    setExportQuality(Number(event.target.value))
                  }
                />
              </label>
            )}
            <button
              className={styles.exportButton}
              type="button"
              disabled={exporting}
              onClick={() => void exportImage()}
            >
              {exporting ? "Рендерим полный размер…" : "Экспортировать"}
            </button>
            {exportJob?.download_url && (
              <a
                className={styles.downloadLink}
                href={exportJob.download_url}
              >
                Скачать {exportJob.format.toUpperCase()}
              </a>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
