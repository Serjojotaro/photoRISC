import { useCallback, useEffect, useRef, useState } from "react";

import {
  APIError,
  deleteAsset,
  getAssets,
  getVersion,
  uploadAsset,
} from "./api";
import Editor from "./Editor";
import type { Asset, BuildVersion } from "./types";
import styles from "./App.module.css";

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(0)} КБ`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function AssetCard({
  asset,
  deleting,
  onDelete,
  onEdit,
}: {
  asset: Asset;
  deleting: boolean;
  onDelete: (asset: Asset) => void;
  onEdit: (asset: Asset) => void;
}) {
  return (
    <article className={styles.card}>
      <a
        className={styles.preview}
        href={asset.original_url}
        target="_blank"
        rel="noreferrer"
        aria-label={`Открыть оригинал ${asset.display_name}`}
      >
        {asset.thumbnail_status === "ready" && asset.thumbnail_url ? (
          <img src={asset.thumbnail_url} alt={asset.display_name} />
        ) : (
          <div
            className={
              asset.thumbnail_status === "failed"
                ? styles.previewFailed
                : styles.previewPending
            }
          >
            <span>
              {asset.thumbnail_status === "failed"
                ? "Превью недоступно"
                : "Готовим превью"}
            </span>
            {asset.thumbnail_status === "pending" && (
              <span className={styles.spinner} aria-hidden="true" />
            )}
          </div>
        )}
      </a>
      <div className={styles.cardBody}>
        <div className={styles.cardHeading}>
          <div>
            <h2 title={asset.display_name}>{asset.display_name}</h2>
            <p>
              {asset.width} × {asset.height} · {formatBytes(asset.size_bytes)}
            </p>
          </div>
          <button
            className={styles.iconButton}
            type="button"
            disabled={deleting}
            onClick={() => onDelete(asset)}
            aria-label={`Удалить ${asset.display_name}`}
            title="Удалить изображение"
          >
            ×
          </button>
        </div>
        <button
          className={styles.editButton}
          type="button"
          onClick={() => onEdit(asset)}
        >
          Открыть редактор
        </button>
      </div>
    </article>
  );
}

export default function App() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [selectedAsset, setSelectedAsset] = useState<Asset | null>(null);
  const [total, setTotal] = useState(0);
  const [version, setVersion] = useState<BuildVersion | null>(null);
  const [versionError, setVersionError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const loadAssets = useCallback(async (offset = 0, append = false) => {
    try {
      const result = await getAssets(offset);
      setTotal(result.total);
      setAssets((current) => {
        if (append) {
          const known = new Set(current.map((asset) => asset.id));
          return [
            ...current,
            ...result.items.filter((asset) => !known.has(asset.id)),
          ];
        }
        const firstPageIds = new Set(result.items.map((asset) => asset.id));
        return [
          ...result.items,
          ...current.slice(50).filter((asset) => !firstPageIds.has(asset.id)),
        ];
      });
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Не удалось загрузить библиотеку.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    getVersion()
      .then(setVersion)
      .catch(() => setVersionError(true));
    void loadAssets();
  }, [loadAssets]);

  useEffect(() => {
    if (!assets.some((asset) => asset.thumbnail_status === "pending")) {
      return;
    }
    const timer = window.setInterval(() => {
      void loadAssets();
    }, 1000);
    return () => window.clearInterval(timer);
  }, [assets, loadAssets]);

  async function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) {
      return;
    }
    setError(null);
    setUploading(true);
    try {
      const asset = await uploadAsset(file);
      setAssets((current) => [asset, ...current]);
      setTotal((current) => current + 1);
    } catch (cause) {
      setError(
        cause instanceof APIError ? cause.message : "Не удалось загрузить файл.",
      );
    } finally {
      setUploading(false);
      if (fileInput.current) {
        fileInput.current.value = "";
      }
    }
  }

  async function handleDelete(asset: Asset) {
    if (!window.confirm(`Удалить «${asset.display_name}» из библиотеки?`)) {
      return;
    }
    setError(null);
    setDeletingId(asset.id);
    try {
      await deleteAsset(asset.id);
      setAssets((current) => current.filter((item) => item.id !== asset.id));
      setTotal((current) => Math.max(0, current - 1));
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Не удалось удалить изображение.",
      );
    } finally {
      setDeletingId(null);
    }
  }

  async function loadMore() {
    setLoadingMore(true);
    setError(null);
    try {
      await loadAssets(assets.length, true);
    } finally {
      setLoadingMore(false);
    }
  }

  return (
    <div className={styles.app}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>PR</span>
          <div>
            <p className={styles.eyebrow}>Локальная glitch-лаборатория</p>
            <h1>PhotoRISC</h1>
          </div>
        </div>
        <span className={styles.localBadge}>Только этот компьютер</span>
      </header>

      {selectedAsset ? (
        <Editor asset={selectedAsset} onBack={() => setSelectedAsset(null)} />
      ) : (
      <main className={styles.main}>
        <section className={styles.intro}>
          <div>
            <p className={styles.kicker}>Библиотека</p>
            <h2>Ваши исходники. Без изменений.</h2>
            <p className={styles.lead}>
              Загрузите JPEG, чтобы подготовить его к экспериментальной
              обработке. Оригинал сохраняется отдельно и никогда не
              перезаписывается.
            </p>
          </div>
          <div className={styles.counter}>
            <strong>{total}</strong>
            <span>изображений</span>
          </div>
        </section>

        {error && (
          <div className={styles.error} role="alert">
            <span>{error}</span>
            <button type="button" onClick={() => setError(null)}>
              Закрыть
            </button>
          </div>
        )}

        <section
          className={`${styles.dropZone} ${dragging ? styles.dropZoneActive : ""}`}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragging(true);
          }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={(event) => {
            if (event.currentTarget === event.target) {
              setDragging(false);
            }
          }}
          onDrop={(event) => {
            event.preventDefault();
            setDragging(false);
            void handleFiles(event.dataTransfer.files);
          }}
        >
          <input
            ref={fileInput}
            type="file"
            accept=".jpg,.jpeg,image/jpeg"
            hidden
            onChange={(event) => void handleFiles(event.target.files)}
          />
          <div className={styles.dropIcon} aria-hidden="true">
            +
          </div>
          <div>
            <h3>{uploading ? "Загружаем JPEG…" : "Перетащите JPEG сюда"}</h3>
            <p>До 50 МБ и 50 мегапикселей</p>
          </div>
          <button
            className={styles.primaryButton}
            type="button"
            disabled={uploading}
            onClick={() => fileInput.current?.click()}
          >
            Выбрать файл
          </button>
        </section>

        <section aria-labelledby="library-heading">
          <div className={styles.sectionHeading}>
            <h2 id="library-heading">Загруженные изображения</h2>
            <span>Оригиналы защищены от перезаписи</span>
          </div>

          {loading ? (
            <div className={styles.empty}>Загружаем библиотеку…</div>
          ) : assets.length === 0 ? (
            <div className={styles.empty}>
              <span className={styles.emptyMark}>01</span>
              <h3>Библиотека пока пуста</h3>
              <p>Первый JPEG появится здесь сразу после загрузки.</p>
            </div>
          ) : (
            <>
              <div className={styles.grid}>
                {assets.map((asset) => (
                  <AssetCard
                    key={asset.id}
                    asset={asset}
                    deleting={deletingId === asset.id}
                    onDelete={(item) => void handleDelete(item)}
                  onEdit={setSelectedAsset}
                  />
                ))}
              </div>
              {assets.length < total && (
                <button
                  className={styles.loadMore}
                  type="button"
                  disabled={loadingMore}
                  onClick={() => void loadMore()}
                >
                  {loadingMore ? "Загружаем…" : "Показать ещё"}
                </button>
              )}
            </>
          )}
        </section>
      </main>
      )}

      <footer className={styles.footer}>
        <span>PhotoRISC · неразрушаемая обработка</span>
        <span className={styles.version} aria-label="Версия приложения">
          {version?.display ||
            (versionError
              ? "Версия недоступна"
              : "Определяем версию сборки…")}
        </span>
      </footer>
    </div>
  );
}
