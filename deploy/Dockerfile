# Hivemind for Railway: one container; Flask serves the API and the built frontend on $PORT.
# Build context is the repository root (see railway.json).

FROM node:22-slim AS web
WORKDIR /src
COPY locales ./locales
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN npm ci --prefix frontend
COPY frontend ./frontend
# Same-origin API calls, and the public-site touches (quota note, source link)
ENV VITE_API_BASE_URL=/ VITE_PUBLIC=1
RUN npm run build --prefix frontend

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
# CPU-only torch. The lockfile's Linux torch pulls about 3 GB of CUDA libraries that a
# CPU container never uses; everything else installs exactly as locked.
RUN uv export --frozen --no-dev --no-hashes --no-emit-project -o /tmp/req.txt \
 && grep -vE '^(nvidia-|triton==|torch==)' /tmp/req.txt > /tmp/req-cpu.txt \
 && TORCH="$(grep -E '^torch==' /tmp/req.txt | sed -E 's/^torch==([^ ;]+).*/\1/')" \
 && uv venv .venv \
 && uv pip install --python .venv "torch==${TORCH}" --index-url https://download.pytorch.org/whl/cpu \
 && uv pip install --python .venv -r /tmp/req-cpu.txt \
 && rm -rf /root/.cache

WORKDIR /app
COPY . .
COPY --from=web /src/frontend/dist ./frontend/dist
# AGPL-3.0 section 13: the running site offers its own source (served at /source.tar.gz).
RUN tar czf /opt/hivemind-source.tar.gz \
      --exclude=./frontend/dist --exclude=./backend/.venv --exclude=./backend/uploads \
      --exclude=./node_modules --exclude=./frontend/node_modules -C /app .

ENV HIVEMIND_PUBLIC=1 \
    HIVEMIND_STATIC_DIR=/app/frontend/dist \
    HIVEMIND_SOURCE_ARCHIVE=/opt/hivemind-source.tar.gz \
    HIVEMIND_ENV_LIFETIME_MINUTES=20 \
    FLASK_HOST=0.0.0.0 \
    HF_HOME=/app/backend/uploads/.hf
WORKDIR /app/backend
CMD [".venv/bin/python", "run.py"]
