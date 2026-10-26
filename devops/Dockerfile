# syntax=docker/dockerfile:1
# Stages: base -> builder (deps de runtime) -> test (pytest) | runtime (imagen mínima para ACR)
# Contexto = raíz del repo; las exclusiones están en devops/Dockerfile.dockerignore.
#   docker build -f devops/Dockerfile --target test -t agent:test .
#   docker build -f devops/Dockerfile --target runtime -t agent:local .

ARG PYTHON_IMAGE=python:3.12-alpine

FROM ${PYTHON_IMAGE} AS base
# uv desde PyPI (no desde ghcr.io): una fuente menos a habilitar en redes corporativas
RUN pip install --no-cache-dir --disable-pip-version-check uv==0.11.28
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app


FROM base AS builder
# capa de dependencias: solo se reconstruye si cambian pyproject.toml o uv.lock
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable


FROM builder AS test
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable
COPY tests ./tests
COPY dev ./dev
CMD ["pytest", "-q", "-p", "no:cacheprovider"]


FROM ${PYTHON_IMAGE} AS runtime
RUN addgroup -S app && adduser -S -G app app
WORKDIR /app
# solo el virtualenv: sin uv, sin código fuente, sin tests ni dev
COPY --from=builder --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s \
    CMD wget -qO- http://127.0.0.1:8000/health || exit 1
CMD ["uvicorn", "agent.infrastructure.bootstrap:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
