FROM python:3.13-slim AS dependencies
COPY --from=ghcr.io/astral-sh/uv:0.8.4 /uv /bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv UV_HTTP_TIMEOUT=180 UV_LINK_MODE=copy uv sync --locked --only-group worker
RUN PLAYWRIGHT_BROWSERS_PATH=/browsers PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=180000 \
    .venv/bin/playwright install --only-shell chromium

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/browsers HOME=/tmp
WORKDIR /app
COPY --from=dependencies /app/.venv .venv
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && rm -f /etc/apt/apt.conf.d/docker-clean \
    && printf 'Acquire::Retries "3";\nAcquire::https::Timeout "25";\n' > /etc/apt/apt.conf.d/80-browser-downloads \
    && .venv/bin/playwright install-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY --from=dependencies /browsers /browsers
COPY worker/run.py worker/demo.html ./

USER 1000:1000
ENTRYPOINT [".venv/bin/python", "run.py"]
