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

## Docker на Linux

Рекомендуемый вариант для сервера или виртуальной машины.

Нужны Docker Engine и плагин Docker Compose. Для Ubuntu/Debian пример установки:

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
newgrp docker
docker version
docker compose version
```

Для других дистрибутивов установите Docker Engine и Compose plugin штатным пакетным менеджером и проверьте обе команды выше.

Если `apt update` завершается ошибкой `file:/cdrom ... Release file`, на сервере остался неактивный CD-ROM source. В `/etc/apt/sources.list` закомментируйте строку `file:///cdrom`:

```bash
sudo sed -i 's|^deb .*file:///cdrom.*$|# CD-ROM repository disabled|' /etc/apt/sources.list
sudo apt update
```

Запуск PhotoRISC:

```bash
git clone git@github.com:Serjojotaro/photoRISC.git
cd photoRISC
cp .env.example .env
docker compose up -d --build
curl http://127.0.0.1/api/v1/health
```

Если репозиторий уже склонирован, обновление выполняется так:

```bash
cd photoRISC
git pull
docker compose up -d --build
```

Данные находятся в `data/` и сохраняются при пересборке и перезапуске контейнеров. Состояние сервисов и логи:

```bash
docker compose ps
docker compose logs --tail=100 api worker web
```

По умолчанию PhotoRISC слушает только `127.0.0.1` на Linux-хосте. Для безопасного доступа с другого компьютера используйте SSH-туннель:

```bash
ssh -L 8080:127.0.0.1:80 пользователь@linux-host
```

После подключения откройте `http://127.0.0.1:8080` на своём компьютере. Прямая публикация сервиса в LAN не рекомендуется: в текущей версии нет аутентификации.

Если порт 80 уже занят системным Nginx или другим сервисом:

```bash
ss -ltnp | grep ':80 '
```

Укажите свободный порт в `.env`, например `PHOTORISC_PORT=8080`, перезапустите Compose и используйте соответствующий SSH-туннель:

```bash
docker compose up -d
ssh -L 18080:127.0.0.1:8080 пользователь@linux-host
```

## Docker на Windows

После запуска Docker Desktop:

```bash
docker compose up -d --build
```

Приложение будет доступно по адресу `http://127.0.0.1`. Порт можно изменить через `PHOTORISC_PORT` в `.env`; данные сохраняются в `data/`.

## Локальная разработка

### Linux

Установите Python 3.12+, Node.js 22+, npm и Git. Затем:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.lock
python scripts/generate_build_info.py
```

Backend запускается в отдельном терминале:

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Worker — во втором терминале:

```bash
cd backend
../.venv/bin/python -m app.worker
```

Frontend — в третьем:

```bash
cd frontend
npm ci
npm run dev
```

### Windows

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

### Linux

```bash
cd backend
../.venv/bin/python -m pytest

cd ../frontend
npm ci
npm test
npm run build
```

### Windows

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
- версия `0.1.2` — этап расширенных эффектов с адаптивным preview для горизонтальных и вертикальных фотографий; сборки различаются Git-хэшем и timestamp.
