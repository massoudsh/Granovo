# syntax=docker/dockerfile:1

# Override to use a registry mirror, e.g.
#   docker build --build-arg PYTHON_IMAGE=mirror.example.com/library/python:3.12-slim .
ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt


FROM ${PYTHON_IMAGE} AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    GRANOVO_HOST=0.0.0.0 \
    GRANOVO_PORT=8000 \
    GRANOVO_DATA_DIR=/app/data

RUN groupadd --system --gid 10001 granovo \
    && useradd --system --uid 10001 --gid granovo --home-dir /app --shell /usr/sbin/nologin granovo

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY --chown=granovo:granovo backend ./backend
COPY --chown=granovo:granovo landing ./landing
COPY --chown=granovo:granovo docker/entrypoint.sh /usr/local/bin/granovo-entrypoint
RUN chmod 0555 /usr/local/bin/granovo-entrypoint \
    && mkdir -p /app/data \
    && chown granovo:granovo /app/data

USER granovo
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status == 200 else 1)"]

ENTRYPOINT ["granovo-entrypoint"]
CMD ["python", "-m", "backend"]
