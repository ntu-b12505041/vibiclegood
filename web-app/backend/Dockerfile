FROM ghcr.io/astral-sh/uv:0.11.29 AS uv
FROM python:3.13.14-slim-bookworm AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_PYTHON_DOWNLOADS=never UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.13.14-slim-bookworm
WORKDIR /app
RUN groupadd -g 10001 vibicle && useradd --no-create-home -u 10001 -g 10001 vibicle \
    && mkdir -p /data/images && chown 10001:10001 /data/images
COPY --from=build /app/.venv /app/.venv
COPY alembic.ini ./
COPY alembic ./alembic
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["python", "-m", "uvicorn", "vibicle_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--timeout-keep-alive", "5"]
