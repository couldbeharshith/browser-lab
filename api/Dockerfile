FROM python:3.13-slim AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv UV_HTTP_TIMEOUT=180 UV_LINK_MODE=copy uv sync --locked --only-group api

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=dependencies /app/.venv .venv
COPY api/main.py api/dashboard.html api/shop.html ./
COPY api/examples ./examples
COPY api/shop-assets ./shop-assets

USER 1000:1000
EXPOSE 8000
CMD [".venv/bin/python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
