FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM python:3.12-slim
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"
RUN groupadd --gid 10001 viesett && useradd --uid 10001 --gid 10001 --no-create-home viesett
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
COPY docs ./docs
RUN uv sync --frozen --no-dev && mkdir -p /app/.local/objects && chown -R 10001:10001 /app/.local
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "viesett.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]
