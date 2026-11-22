# PhotoRISC

Локальный веб-редактор для неразрушающей glitch-обработки фотографий.

Реализованы:

- библиотека JPEG с неизменяемыми оригиналами;
- рецепты с версиями, включением и порядком операций;
- 17 эффектов, включая pixel sorting, displacement, bit plane, posterize, color quantization, VHS/CRT, interlacing, feedback, dithering и фото-имитацию datamosh;
- быстрый preview на уменьшенной копии;
- undo/redo в текущей сессии;
- экспорт полного размера в JPEG и PNG;
- русскоязычный desktop-first интерфейс;
- версия сборки и её Git-хэш в footer.

## Требования

- для обычного запуска: Docker с Docker Compose;
- для локальной разработки: Python 3.12+ и Node.js 22+.

## Docker

После запуска Docker Desktop:

```bash
docker compose up -d --build
```

Приложение будет доступно по адресу `http://127.0.0.1`. Порт можно изменить через `PHOTORISC_PORT` в `.env`.

Данные сохраняются в `data/` и переживают перезапуск контейнеров.

## Локальная разработка

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend\requirements.lock
.\.venv\Scripts\python scripts\generate_build_info.py
Set-Location backend
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

В отдельном терминале:

```powershell
Set-Location backend
..\.venv\Scripts\python -m app.worker
```

Frontend:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Vite откроет интерфейс на `http://127.0.0.1:5173` и проксирует `/api` на backend.

## Проверки

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest

Set-Location ..\frontend
npm test
npm run build
```

OpenAPI-схема доступна по адресу `http://127.0.0.1:8000/api/openapi.json` при локальном запуске и `http://127.0.0.1/api/openapi.json` через Docker. Пользовательский контракт описан в `../docs/API.md`.

## Конфигурация

- `PHOTORISC_PORT` — локальный HTTP-порт, по умолчанию 80;
- `DATA_DIR` — каталог данных backend;
- `DATABASE_PATH` — путь к SQLite;
- `MAX_UPLOAD_BYTES` — лимит файла, по умолчанию 50 МиБ;
- `MAX_IMAGE_PIXELS` — лимит изображения, по умолчанию 50 000 000;
- `PREVIEW_MAX_SIZE` — длинная сторона preview, по умолчанию 1200 px;
- `BUILD_SHA` и `BUILD_TIMESTAMP` — build metadata при внешнем запуске.

## Ограничения

- только JPEG на входе;
- до 50 МБ и 50 мегапикселей;
- сервис доступен только на `127.0.0.1`;
- пользовательские данные хранятся в `data/`;
- версия `0.1.0` — этап расширенных эффектов; сборки различаются Git-хэшем и timestamp.
