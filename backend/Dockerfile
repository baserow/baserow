# syntax=docker/dockerfile:1.4

# =============================================================================
# Builder for su-exec (replaces gosu, smaller footprint)
# Pinned to v0.2 (commit 212b75144bbc) with SHA256 verification
# =============================================================================
FROM debian:bookworm-slim AS su-exec-builder

ENV SU_EXEC_VERSION=212b75144bbc06722fbd7661f651390dc47a43d1 \
    SU_EXEC_SHA256=d6c40440609a23483f12eb6295b5191e94baf08298a856bab6e15b10c3b82891

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl build-essential && \
    curl -L -o /usr/local/bin/su-exec.c "https://github.com/ncopa/su-exec/raw/${SU_EXEC_VERSION}/su-exec.c" && \
    echo "${SU_EXEC_SHA256}  /usr/local/bin/su-exec.c" | sha256sum -c - && \
    gcc -Wall -Werror -static -o /usr/local/bin/su-exec /usr/local/bin/su-exec.c && \
    chmod 0755 /usr/local/bin/su-exec

# =============================================================================
# OS packages stage - fully cached (no UID/GID dependency)
# =============================================================================
FROM debian:bookworm-slim AS builder-packages

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Build dependencies - this layer is always cached
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    python3.11 \
    python3.11-dev \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Create fixed user for builds (never changes, always cached)
RUN groupadd -g 9999 baserow && \
    useradd --shell /bin/bash -u 9999 -g 9999 -o -c "" -m baserow

# =============================================================================
# Builder stage - compiles dependencies with fixed UID
# =============================================================================
FROM builder-packages AS builder

# Create baserow directory structure
RUN mkdir -p /baserow && chown 9999:9999 /baserow

# uv configuration
ENV UV_PYTHON_PREFERENCE=only-system \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_FROZEN=1 \
    UV_REQUIRE_HASHES=1 \
    UV_VERIFY_HASHES=1 \
    UV_PROJECT_ENVIRONMENT=/baserow/venv \
    UV_CACHE_DIR=/tmp/baserow_uv_cache

USER 9999:9999

# Create venv
RUN uv venv --python python3.11 /baserow/venv

# Copy source code (needed for editable installs of local packages)
COPY --chown=9999:9999 ./LICENSE /baserow/LICENSE
COPY --chown=9999:9999 ./backend /baserow/backend
COPY --chown=9999:9999 ./premium/backend /baserow/premium/backend
COPY --chown=9999:9999 ./enterprise/backend /baserow/enterprise/backend

# Install all dependencies including editable local packages
# hadolint ignore=DL3042
RUN --mount=type=cache,mode=777,target=$UV_CACHE_DIR,uid=9999,gid=9999 \
    cd /baserow/backend && uv sync --frozen --no-dev \
    && find /baserow/venv -type f \( -name "*.c" -o -name "*.h" \) -not -path "*/autobahn/*" -delete \
    && rm -rf /baserow/backend/tests /baserow/premium/backend/tests /baserow/enterprise/backend/tests \
    && rm -rf /baserow/backend/templates \
    # Strip test/doc directories from site-packages (keep django/drf tests - used at runtime)
    # Keep botocore/docs and boto3/docs - they're imported at runtime
    && (find /baserow/venv/lib -type d \( -name "test" -o -name "tests" \) \
        -not -path "*/django/*" -not -path "*/rest_framework/*" -prune -exec rm -rf {} \; || true) \
    && (find /baserow/venv/lib -type d \( -name "doc" -o -name "docs" -o -name "example" -o -name "examples" \) \
        -not -path "*/botocore/*" -not -path "*/boto3/*" -prune -exec rm -rf {} \; || true)

# Fix entrypoint script
RUN dos2unix /baserow/backend/docker/docker-entrypoint.sh && \
    chmod a+x /baserow/backend/docker/docker-entrypoint.sh

# =============================================================================
# Builder with dev dependencies
# =============================================================================
FROM builder AS builder-dev

# hadolint ignore=DL3042
RUN --mount=type=cache,mode=777,target=$UV_CACHE_DIR,uid=9999,gid=9999 \
    cd /baserow/backend && uv sync --frozen

# =============================================================================
# Runtime packages stage - fully cached (no UID/GID dependency)
# =============================================================================
FROM debian:bookworm-slim AS runtime-packages

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Runtime dependencies only - this layer is always cached
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    tini \
    postgresql-client-15 \
    gettext \
    python3.11 \
    xmlsec1 \
    && apt-get autoclean \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*

# Copy su-exec from builder (replaces gosu)
COPY --link --from=su-exec-builder /usr/local/bin/su-exec /usr/local/bin/su-exec

# Create fixed user for runtime (never changes, always cached)
RUN groupadd -g 9999 baserow && \
    useradd --shell /bin/bash -u 9999 -g 9999 -o -c "" -m baserow

# =============================================================================
# Production runtime - minimal image with fixed UID
# =============================================================================
FROM runtime-packages AS production

ENV DOCKER_USER=baserow
ENV BASEROW_IMAGE_TYPE="backend"

# In slim docker images, mime.types is removed and we need it for mimetypes guessing
COPY --chown=9999:9999 ./backend/docker/mime.types /etc/

USER 9999:9999

# Copy venv and source from builder
COPY --link --chown=9999:9999 --from=builder /baserow/LICENSE /baserow/LICENSE
COPY --link --chown=9999:9999 --from=builder /baserow/venv /baserow/venv
COPY --link --chown=9999:9999 --from=builder /baserow/backend /baserow/backend
COPY --link --chown=9999:9999 --from=builder /baserow/premium/backend /baserow/premium/backend
COPY --link --chown=9999:9999 --from=builder /baserow/enterprise/backend /baserow/enterprise/backend
COPY --link --chown=9999:9999 ./docs /baserow/docs
COPY --link --chown=9999:9999 ./deploy/plugins/*.sh /baserow/plugins/
COPY --link --chown=9999:9999 ./backend/templates /baserow/backend/templates

ENV PATH="/baserow/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

WORKDIR /baserow/backend

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh"]

# =============================================================================
# Production target (build with --target prod, tag as :latest)
# =============================================================================
FROM production AS prod

ENV DJANGO_SETTINGS_MODULE='baserow.config.settings.base'
CMD ["gunicorn"]

# =============================================================================
# CI Target - lightweight image for tests and linting
# =============================================================================
FROM runtime-packages AS ci

# Install uv (needed for justfile recipes)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# In slim docker images, mime.types is removed and we need it for mimetypes guessing
COPY ./backend/docker/mime.types /etc/

ENV DOCKER_USER=baserow
ENV BASEROW_IMAGE_TYPE="backend"
ENV PATH="/baserow/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE='baserow.config.settings.test'
ENV UV_PROJECT_ENVIRONMENT=/baserow/venv

# Copy venv from builder-dev (has test dependencies)
COPY --link --chown=9999:9999 --from=builder-dev /baserow/venv /baserow/venv

# Install just command runner (after venv is copied)
RUN uv pip install rust-just --python /baserow/venv/bin/python && \
    ln -s /baserow/venv/bin/just /usr/local/bin/just

USER 9999:9999

# Copy source, tests, and plugins (no docs)
COPY --link --chown=9999:9999 --from=builder /baserow/LICENSE /baserow/LICENSE
COPY --link --chown=9999:9999 --from=builder /baserow/backend /baserow/backend
COPY --link --chown=9999:9999 --from=builder /baserow/premium/backend /baserow/premium/backend
COPY --link --chown=9999:9999 --from=builder /baserow/enterprise/backend /baserow/enterprise/backend
COPY --link --chown=9999:9999 ./tests /baserow/tests
COPY --link --chown=9999:9999 ./backend/tests /baserow/backend/tests
COPY --link --chown=9999:9999 ./premium/backend/tests /baserow/premium/backend/tests
COPY --link --chown=9999:9999 ./enterprise/backend/tests /baserow/enterprise/backend/tests
COPY --link --chown=9999:9999 ./deploy/plugins/*.sh /baserow/plugins/
# Templates needed for E2E tests (running gunicorn)
COPY --link --chown=9999:9999 ./backend/templates /baserow/backend/templates

WORKDIR /baserow/backend

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh"]

# =============================================================================
# Dev packages stage - fully cached (no UID/GID dependency)
# =============================================================================
FROM runtime-packages AS dev-packages

# Add dev tools - this layer is always cached
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    graphviz \
    procps \
    python3.11-dev \
    tmux \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install uv for dev (useful for adding packages on the fly)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# =============================================================================
# Development (build with --target dev, tag as :dev)
# Starts as root, entrypoint switches to host user via su-exec
# =============================================================================
FROM dev-packages AS dev

ENV DOCKER_USER=baserow
ENV BASEROW_IMAGE_TYPE="backend"
ENV UV_PYTHON_PREFERENCE=only-system
ENV UV_PROJECT_ENVIRONMENT=/baserow/venv
# Disable hash verification for faster dev builds (production still verifies)
ENV UV_REQUIRE_HASHES=0
ENV UV_VERIFY_HASHES=0

# In slim docker images, mime.types is removed and we need it for mimetypes guessing
COPY ./backend/docker/mime.types /etc/

# Copy venv and source from builder-dev (owned by 9999, will be accessible after su-exec)
COPY --link --from=builder /baserow/LICENSE /baserow/LICENSE
COPY --link --from=builder-dev /baserow/venv /baserow/venv

# Install just command runner (after venv is copied)
RUN uv pip install rust-just --python /baserow/venv/bin/python && \
    ln -s /baserow/venv/bin/just /usr/local/bin/just
COPY --link --from=builder /baserow/backend /baserow/backend
COPY --link --from=builder /baserow/premium/backend /baserow/premium/backend
COPY --link --from=builder /baserow/enterprise/backend /baserow/enterprise/backend
COPY --link ./docs /baserow/docs
COPY --link ./deploy/plugins/*.sh /baserow/plugins/
COPY --link ./backend/templates /baserow/backend/templates

# Copy tests
COPY --link ./tests /baserow/tests/
COPY --link ./backend/tests /baserow/backend/tests/
COPY --link ./premium/backend/tests /baserow/premium/backend/tests/
COPY --link ./enterprise/backend/tests /baserow/enterprise/backend/tests/

# Make venv and writable dirs accessible by any UID (dev only - allows running as host user)
# This avoids slow chown at startup and permission issues with bind mounts
# Also make /etc/passwd writable so entrypoint can add user entry (fixes "I have no name!")
RUN chmod -R a+rwX /baserow/venv && \
    chmod -R a+rwX /baserow/backend && \
    chmod -R a+rwX /baserow/premium && \
    chmod -R a+rwX /baserow/enterprise && \
    mkdir -p /baserow/media /baserow/plugins /baserow/.cache && \
    chmod -R a+rwX /baserow/media /baserow/plugins /baserow/.cache && \
    chmod a+rw /etc/passwd

ENV PATH="/baserow/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE='baserow.config.settings.dev'

WORKDIR /baserow/backend

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh"]
CMD ["django-dev"]
