FROM python:3.12-slim AS metadata

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /source
COPY .git .git
COPY VERSION VERSION
RUN SHA="$(git rev-parse --short=5 HEAD)" \
    && TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    && printf '{"build_sha":"%s","build_timestamp":"%s"}\n' "$SHA" "$TIMESTAMP" \
       > /build-info.json

FROM node:22-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine AS frontend

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /frontend/dist /usr/share/nginx/html

FROM python:3.12-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/backend \
    DATA_DIR=/app/data

WORKDIR /app
COPY backend/requirements.lock /app/backend/requirements.lock
RUN pip install --no-cache-dir -r /app/backend/requirements.lock

COPY backend /app/backend
COPY VERSION /app/VERSION
COPY --from=metadata /build-info.json /app/build-info.json

WORKDIR /app/backend
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
