# syntax=docker/dockerfile:1.4
ARG UID="9999"
ARG GID="9999"

# =============================================================================
# Builder for su-exec (replaces gosu, safer with smaller footprint)
# Pinned to v0.2 (commit 212b75144bbc) with SHA256 verification
# =============================================================================
FROM debian:trixie-slim AS tool-builder

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV SU_EXEC_VERSION=212b75144bbc06722fbd7661f651390dc47a43d1 \
    SU_EXEC_SHA256=d6c40440609a23483f12eb6295b5191e94baf08298a856bab6e15b10c3b82891

# hadolint ignore=DL3008
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends ca-certificates curl build-essential dos2unix tini && \
    curl -fsSL -o /usr/local/bin/su-exec.c "https://github.com/ncopa/su-exec/raw/${SU_EXEC_VERSION}/su-exec.c" && \
    echo "${SU_EXEC_SHA256}  /usr/local/bin/su-exec.c" | sha256sum -c - && \
    gcc -Wall -Werror -static -o /usr/local/bin/su-exec /usr/local/bin/su-exec.c && \
    chmod 0755 /usr/local/bin/su-exec


# =============================================================================
# Production base builder stage: builds runtime dependencies only
# =============================================================================
FROM python:3.14.3-slim-trixie AS builder-prod-base
ARG UID
ARG GID

# Runtime dependencies only - this layer is always cached
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev

ENV UV_PYTHON_DOWNLOADS=0 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/baserow/venv \
    UV_CACHE_DIR=/tmp/baserow_uv_cache \
    UV_VERBOSE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/baserow/venv/bin:$PATH" \
    PYTHONPATH="/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src"

# hadolint ignore=DL3022
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Create baserow directory structure (including subdirs for COPY targets)
RUN mkdir -p /baserow/ && chown -R $UID:$GID /baserow/
    
USER $UID:$GID
WORKDIR /baserow/backend

RUN --mount=type=cache,target=$UV_CACHE_DIR,sharing=locked,uid=$UID,gid=$GID \
    --mount=type=bind,source=LICENSE,target=/baserow/LICENSE \
    --mount=type=bind,source=backend/uv.lock,target=/baserow/backend/uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=/baserow/backend/pyproject.toml \
    --mount=type=bind,source=premium/LICENSE,target=/baserow/premium/LICENSE \
    --mount=type=bind,source=premium/backend/pyproject.toml,target=/baserow/premium/backend/pyproject.toml \
    --mount=type=bind,source=enterprise/LICENSE,target=/baserow/enterprise/LICENSE \
    --mount=type=bind,source=enterprise/backend/pyproject.toml,target=/baserow/enterprise/backend/pyproject.toml \
    uv sync --frozen --no-dev --no-install-workspace --no-install-project \
    && find /baserow/venv -type f \( -name "*.c" -o -name "*.h" \) -not -path "*/autobahn/*" -delete \
    # Strip test/doc directories from site-packages (keep django/drf tests - used at runtime)
    # Keep botocore/docs and boto3/docs - they're imported at runtime
    && (find /baserow/venv/lib -type d \( -name "test" -o -name "tests" \) \
        -not -path "*/django/*" -not -path "*/rest_framework/*" -prune -exec rm -rf {} \; || true) \
    && (find /baserow/venv/lib -type d \( -name "doc" -o -name "docs" -o -name "example" -o -name "examples" \) \
        -not -path "*/botocore/*" -not -path "*/boto3/*" -prune -exec rm -rf {} \; || true)


# =============================================================================
# CI Builder - includes dev dependencies for testing
# =============================================================================
FROM builder-prod-base AS builder-ci
ARG UID
ARG GID

USER $UID:$GID
WORKDIR /baserow/backend

COPY --chown=$UID:$GID LICENSE /baserow/LICENSE
COPY --chown=$UID:$GID premium/LICENSE /baserow/premium/LICENSE
COPY --chown=$UID:$GID enterprise/LICENSE /baserow/enterprise/LICENSE

# Install dev dependencies before copying source code to leverage caching
RUN --mount=type=cache,target=$UV_CACHE_DIR,sharing=locked,uid=$UID,gid=$GID \
    --mount=type=bind,source=backend/uv.lock,target=/baserow/backend/uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=/baserow/backend/pyproject.toml \
    --mount=type=bind,source=premium/backend/pyproject.toml,target=/baserow/premium/backend/pyproject.toml \
    --mount=type=bind,source=enterprise/backend/pyproject.toml,target=/baserow/enterprise/backend/pyproject.toml \
    uv sync --frozen --no-install-workspace --no-install-project \
    && find /baserow/venv -type f \( -name "*.c" -o -name "*.h" \) -not -path "*/autobahn/*" -delete \
    # Strip test/doc directories from site-packages (keep django/drf tests - used at runtime)
    # Keep botocore/docs and boto3/docs - they're imported at runtime
    && (find /baserow/venv/lib -type d \( -name "test" -o -name "tests" \) \
        -not -path "*/django/*" -not -path "*/rest_framework/*" -prune -exec rm -rf {} \; || true) \
    && (find /baserow/venv/lib -type d \( -name "doc" -o -name "docs" -o -name "example" -o -name "examples" \) \
        -not -path "*/botocore/*" -not -path "*/boto3/*" -prune -exec rm -rf {} \; || true)

COPY --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix

# Copy source code and tests

COPY --chown=$UID:$GID backend /baserow/backend
COPY --chown=$UID:$GID premium/backend /baserow/premium/backend
COPY --chown=$UID:$GID enterprise/backend /baserow/enterprise/backend

COPY --chown=$UID:$GID tests /baserow/tests

USER $UID:$GID
WORKDIR /baserow/backend

RUN dos2unix /baserow/backend/docker/docker-entrypoint.sh \
    && chmod a+x /baserow/backend/docker/docker-entrypoint.sh

# Install the project with premium and enterprise plugins
RUN --mount=type=cache,target=$UV_CACHE_DIR,sharing=locked,uid=$UID,gid=$GID \
    uv sync --frozen \
    && find /baserow/venv -type f \( -name "*.c" -o -name "*.h" \) -not -path "*/autobahn/*" -delete \
    # Strip test/doc directories from site-packages (keep django/drf tests - used at runtime)
    # Keep botocore/docs and boto3/docs - they're imported at runtime
    && (find /baserow/venv/lib -type d \( -name "test" -o -name "tests" \) \
        -not -path "*/django/*" -not -path "*/rest_framework/*" -prune -exec rm -rf {} \; || true) \
    && (find /baserow/venv/lib -type d \( -name "doc" -o -name "docs" -o -name "example" -o -name "examples" \) \
        -not -path "*/botocore/*" -not -path "*/boto3/*" -prune -exec rm -rf {} \; || true)

# =============================================================================
# Production builder stage - creates runtime packages only
# =============================================================================
FROM builder-prod-base AS builder-prod
ARG UID
ARG GID

COPY --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix

USER $UID:$GID
WORKDIR /baserow/backend

# Copy source code
COPY --chown=$UID:$GID LICENSE /baserow/LICENSE
COPY --chown=$UID:$GID backend /baserow/backend

COPY --chown=$UID:$GID premium/LICENSE /baserow/premium/LICENSE
COPY --chown=$UID:$GID premium/backend /baserow/premium/backend

COPY --chown=$UID:$GID enterprise/LICENSE /baserow/enterprise/LICENSE
COPY --chown=$UID:$GID enterprise/backend /baserow/enterprise/backend

RUN dos2unix /baserow/backend/docker/docker-entrypoint.sh \
    && chmod a+x /baserow/backend/docker/docker-entrypoint.sh

# Install the project with premium and enterprise workspaces
RUN --mount=type=cache,target=$UV_CACHE_DIR,sharing=locked,uid=$UID,gid=$GID \
    uv sync --frozen --no-dev \
    && find /baserow/venv -type f \( -name "*.c" -o -name "*.h" \) -not -path "*/autobahn/*" -delete \
    # Strip test/doc directories from site-packages (keep django/drf tests - used at runtime)
    # Keep botocore/docs and boto3/docs - they're imported at runtime
    && (find /baserow/venv/lib -type d \( -name "test" -o -name "tests" \) \
        -not -path "*/django/*" -not -path "*/rest_framework/*" -prune -exec rm -rf {} \; || true) \
    && (find /baserow/venv/lib -type d \( -name "doc" -o -name "docs" -o -name "example" -o -name "examples" \) \
        -not -path "*/botocore/*" -not -path "*/boto3/*" -prune -exec rm -rf {} \; || true)


# =============================================================================
# CI Target - lightweight image for pytest and E2E tests
# =============================================================================
FROM python:3.14.3-slim-trixie AS ci
ARG UID
ARG GID

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    gettext \
    xmlsec1

ENV DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="backend" \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/baserow/venv \
    UV_CACHE_DIR=/tmp/baserow_uv_cache \
    PATH="/baserow/venv/bin:$PATH" \
    PYTHONPATH="/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src:/baserow/backend/tests:/baserow/premium/backend/tests:/baserow/enterprise/backend/tests" \
    DJANGO_SETTINGS_MODULE='baserow.config.settings.test'

RUN groupadd --system --gid $GID ${DOCKER_USER} && \
      useradd --shell /bin/bash -l -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER}

COPY --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=tool-builder /usr/bin/tini /usr/bin/tini
# hadolint ignore=DL3022
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Create baserow directory structure (including subdirs for COPY targets)
RUN mkdir -p /baserow/backend/reports /baserow/premium/backend /baserow/enterprise/backend /baserow/media && \
    chown -R $UID:$GID /baserow/

# Copy the virtual environment and source code with tests
COPY --chown=$UID:$GID --from=builder-ci /baserow /baserow
COPY --chown=$UID:$GID ./docs /baserow/docs/
COPY --chown=$UID:$GID deploy/plugins/*.sh /baserow/plugins/

USER $UID:$GID
WORKDIR /baserow/backend
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh"]


# =============================================================================
# Dev image: includes dev dependencies and tools for local development
# Only works mounting the source code as a bind mount. See docker-compose.dev.yml for usage.
# =============================================================================

FROM python:3.14.3-slim-trixie AS dev
ARG UID="9999"
ARG GID="9999"

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Build dependencies - this layer is always cached
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --batch --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    build-essential \
    python3-dev \
    ca-certificates \
    postgresql-client-15 \
    gettext \
    xmlsec1 \
    curl \
    graphviz \
    procps \
    tmux \
    vim \
    lsof \
    sudo

ENV DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="backend" \
    UV_PYTHON_DOWNLOADS=0 \
    UV_COMPILE_BYTECODE=0 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/baserow/venv \
    UV_CACHE_DIR=/tmp/baserow_uv_cache_dev \
    PYTHONUNBUFFERED=1 \
    PATH=/baserow/venv/bin:$PATH \
    PYTHONPATH=/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src:/baserow/backend/tests:/baserow/premium/backend/tests:/baserow/enterprise/backend/tests \
    DJANGO_SETTINGS_MODULE=baserow.config.settings.dev

RUN getent group $GID || groupadd --system --gid $GID ${DOCKER_USER} && \
    useradd --shell /bin/bash -l -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER} && \
    echo "${DOCKER_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${DOCKER_USER} && \
    chmod 0440 /etc/sudoers.d/${DOCKER_USER}

COPY --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=tool-builder /usr/bin/tini /usr/bin/tini
COPY --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix
# hadolint ignore=DL3022
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /uvx /bin/

# Create directory structure to install dependencies
RUN mkdir -p /baserow/backend/docker /baserow/premium/ /baserow/enterprise/ /baserow/media && \
    chown -R $UID:$GID /baserow/

USER $UID:$GID
WORKDIR /baserow/backend

# Install all dependencies
COPY --chown=$UID:$GID LICENSE /baserow/LICENSE
COPY --chown=$UID:$GID premium/LICENSE /baserow/premium/LICENSE
COPY --chown=$UID:$GID enterprise/LICENSE /baserow/enterprise/LICENSE

RUN --mount=type=cache,target=$UV_CACHE_DIR,sharing=locked,uid=$UID,gid=$GID \
    --mount=type=bind,source=backend/uv.lock,target=/baserow/backend/uv.lock \
    --mount=type=bind,source=backend/pyproject.toml,target=/baserow/backend/pyproject.toml \
    --mount=type=bind,source=premium/backend/pyproject.toml,target=/baserow/premium/backend/pyproject.toml \
    --mount=type=bind,source=enterprise/backend/pyproject.toml,target=/baserow/enterprise/backend/pyproject.toml \
    uv sync --frozen --no-install-workspace --no-install-project

# Configure tmux and bashrc
RUN echo "set -g default-command \"\${SHELL}\"" > /baserow/.tmux.conf && \
    printf '%s\n' \
    '# Aliases' \
    'alias j="just"' \
    'alias m="python /baserow/backend/src/baserow/manage.py"' \
    'alias pytest="python -m pytest"' \
    '' \
    '# Show a helpful message' \
    'echo "Baserow backend dev container"' \
    'echo "  m <cmd>     - Django manage.py (e.g., m shell_plus)"' \
    'echo "  pytest      - Run tests"' \
    'echo "  j           - See available commands"' \
    > /baserow/.bashrc

COPY --chown=$UID:$GID backend/docker/docker-entrypoint.sh /baserow/backend/docker/docker-entrypoint.sh
RUN dos2unix /baserow/backend/docker/docker-entrypoint.sh \
    && chmod a+x /baserow/backend/docker/docker-entrypoint.sh

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh"]
CMD ["django-dev"]


# =============================================================================
# Production target
# =============================================================================
FROM python:3.14.3-slim-trixie AS local 
ARG UID
ARG GID

ENV POSTGRES_VERSION=15 \
    DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="backend" \
    UV_PROJECT_ENVIRONMENT=/baserow/venv \
    PYTHONUNBUFFERED=1 \
    PATH="/baserow/venv/bin:$PATH" \
    PYTHONPATH="/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src" \
    DJANGO_SETTINGS_MODULE='baserow.config.settings.base'

# Runtime dependencies only - this layer is always cached
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl ca-certificates gnupg \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --batch --dearmor -o /usr/share/keyrings/pgdg.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    xmlsec1 \
    gettext \
    postgresql-client-${POSTGRES_VERSION}

RUN groupadd --system --gid $GID ${DOCKER_USER} && \
      useradd --shell /bin/bash -l -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER}

# In slim docker images, mime.types is removed and we need it for mimetypes guessing
COPY ./backend/docker/mime.types /etc/
COPY --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=tool-builder /usr/bin/tini /usr/bin/tini

RUN mkdir -p /baserow/media && chown -R $UID:$GID /baserow/

# Copy the virtual environment with the production dependencies
COPY --chown=$UID:$GID --from=builder-prod /baserow/venv /baserow/venv/

COPY --chown=$UID:$GID LICENSE /baserow/LICENSE
COPY --chown=$UID:$GID --from=builder-prod /baserow/backend /baserow/backend/
COPY --chown=$UID:$GID --from=builder-prod /baserow/premium /baserow/premium/
COPY --chown=$UID:$GID --from=builder-prod /baserow/enterprise /baserow/enterprise/
COPY --chown=$UID:$GID ./docs /baserow/docs/

# Remove application tests and dev-only directories
RUN rm -rf /baserow/backend/tests /baserow/premium/backend/tests \
        /baserow/enterprise/backend/tests /baserow/backend/email_compiler

COPY --chown=$UID:$GID deploy/plugins/*.sh /baserow/plugins/

USER $UID:$GID
WORKDIR /baserow/backend

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh"]
CMD ["gunicorn"]


FROM local AS prod

CMD ["gunicorn"]