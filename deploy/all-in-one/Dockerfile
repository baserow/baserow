# syntax=docker/dockerfile:1.4
ARG UID="9999"
ARG GID="9999"

ARG BACKEND_IMAGE=baserow_backend
ARG WEBFRONTEND_IMAGE=baserow_web-frontend
# hadolint ignore=DL3006
FROM ${BACKEND_IMAGE}:latest AS backend_image
# hadolint ignore=DL3006
FROM ${BACKEND_IMAGE}:dev AS backend_image_dev
# hadolint ignore=DL3006
FROM ${WEBFRONTEND_IMAGE}:latest AS web_frontend_image
# hadolint ignore=DL3006
FROM ${WEBFRONTEND_IMAGE}:dev AS web_frontend_image_dev

# =============================================================================
# Base - system dependencies (cached independently of source images)
# =============================================================================
FROM python:3.11-slim-bookworm AS base
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="all-in-one" \
    DATA_DIR=/baserow/data \
    POSTGRES_VERSION=15 \
    POSTGRES_LOCATION=/etc/postgresql/15/main \
    BASEROW_PLUGIN_DIR=/baserow/data/plugins \
    UV_PROJECT_ENVIRONMENT=/baserow/venv \
    PATH="/baserow/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

# Caddy checksums for v2.7.6
ENV CADDY_VERSION=2.7.6 \
    CADDY_SHA256_AMD64=99587cf77c595f0bf62cc23c9ea101f9879fa016c7b689d498ce054904821f22 \
    CADDY_SHA256_ARM64=6e6aeca09502a8f0ab0a08acd03bb765e80888052d108de22e0698a9160b7235

# Runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install --no-install-recommends -y \
    supervisor curl gnupg2 ca-certificates \
    psmisc \
    gawk \
    postgresql-client-${POSTGRES_VERSION} \
    xmlsec1 \
    gettext \
    && \
    # Install Caddy with checksum verification
    ARCH=$(dpkg --print-architecture) && \
    curl -o caddy.tar.gz -sL "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_${ARCH}.tar.gz" && \
    if [ "$ARCH" = "amd64" ]; then echo "${CADDY_SHA256_AMD64}  caddy.tar.gz" | sha256sum -c -; \
    elif [ "$ARCH" = "arm64" ]; then echo "${CADDY_SHA256_ARM64}  caddy.tar.gz" | sha256sum -c -; \
    else echo "Unsupported architecture: $ARCH" && exit 1; fi && \
    tar -xf caddy.tar.gz && mv caddy /usr/bin/ && rm caddy.tar.gz && \
    # Setup user and group with fixed UID/GID for volume permission consistency
    getent group $GID || groupadd --system --gid $GID ${DOCKER_USER} && \
    useradd --shell /bin/bash -l -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER} && \
    # Setup supervisor
    ln -sf /dev/stdout /var/log/supervisor/supervisord.log && \
    # Create data and plugin directories with correct ownership
    mkdir -p ${DATA_DIR} ${BASEROW_PLUGIN_DIR} && \
    chown -R $UID:$GID ${DATA_DIR} ${BASEROW_PLUGIN_DIR}

# Copy Node.js, npm, and yarn from web-frontend image (avoids insecure curl|bash from NodeSource)
COPY --from=web_frontend_image /usr/local/bin/node /usr/local/bin/node
COPY --link --from=web_frontend_image /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --link --from=web_frontend_image /opt/yarn-v1.22.22 /opt/yarn-v1.22.22
RUN ln -s /opt/yarn-v1.22.22/bin/yarn /usr/local/bin/yarn

# Copy su-exec from backend image (already built with pinned version + SHA256 verification)
COPY --link --from=backend_image /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --link --from=backend_image /usr/bin/tini /usr/bin/tini


# =============================================================================
# Development - adds dev tools, backend dev venv, and frontend dev deps
# =============================================================================
FROM base AS dev
ARG UID
ARG GID

# Install uv and dev tools
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONPATH="/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src:/baserow/backend/tests:/baserow/premium/backend/tests:/baserow/enterprise/backend/tests" \
    DJANGO_SETTINGS_MODULE='baserow.config.settings.dev' \
    BASEROW_ALL_IN_ONE_DEV_MODE='true' \
    UV_PROJECT_ENVIRONMENT='/baserow/venv' \
    NUXT_CACHE_DIR='/baserow/node_modules/.cache'

    RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    # Add PostgreSQL repo (for pgvector) and install postgres + redis
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/postgresql.list && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
    build-essential \
    python3.11-dev \
    procps \
    vim \
    tmux \
    sudo \
    postgresql-${POSTGRES_VERSION} \
    postgresql-${POSTGRES_VERSION}-pgvector \
    redis-server && \
    # Setup redis
    usermod -a -G tty redis && \
    sed -i 's/daemonize yes/daemonize no/g' /etc/redis/redis.conf && \
    sed -i 's/daemonize no/daemonize no\nbind 127.0.0.1/g' /etc/redis/redis.conf && \
    sed -i '/^logfile/d' /etc/redis/redis.conf && \
    chown redis:redis /etc/redis/redis.conf

RUN echo "${DOCKER_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${DOCKER_USER} && \
    chmod 0440 /etc/sudoers.d/${DOCKER_USER}

# Backend venv and frontend deps
COPY --chown=$UID:$GID --from=backend_image ${UV_PROJECT_ENVIRONMENT} ${UV_PROJECT_ENVIRONMENT}
COPY --chown=$UID:$GID --from=web_frontend_image /baserow/web-frontend/node_modules /baserow/web-frontend/node_modules

COPY --chown=$UID:$GID ./LICENSE /baserow/LICENSE
COPY --chown=$UID:$GID ./backend/docker/mime.types /etc/
COPY --chown=$UID:$GID Caddyfile /baserow/caddy/Caddyfile
COPY --chown=$UID:$GID deploy/all-in-one/supervisor/ /baserow/supervisor
COPY --chown=$UID:$GID deploy/all-in-one/baserow.sh /baserow.sh

USER $UID:$GID

# Configure tmux to preserve environment variables (don't start login shell)
RUN echo 'set -g default-command "${SHELL}"' > /baserow/.tmux.conf

# Create .bashrc with environment variables for interactive shells
RUN printf '%s\n' \
    '# Baserow All-in-One Development Environment' \
    'export PATH="/baserow/venv/bin:/baserow/web-frontend/node_modules/.bin:$PATH"' \
    'export PYTHONPATH="/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src:/baserow/backend/tests:/baserow/premium/backend/tests:/baserow/enterprise/backend/tests"' \
    'export PYTHONUNBUFFERED=1' \
    'export UV_PROJECT_ENVIRONMENT=/baserow/venv' \
    'export UV_PYTHON_PREFERENCE=only-system' \
    'export UV_COMPILE_BYTECODE=0' \
    'export UV_CACHE_DIR=/tmp/baserow_uv_cache' \
    'export DJANGO_SETTINGS_MODULE=baserow.config.settings.dev' \
    '' \
    '# Aliases' \
    'alias j="just"' \
    'alias m="python /baserow/backend/src/baserow/manage.py"' \
    'alias pytest="python -m pytest"' \
    'alias y="yarn"' \
    '' \
    '# Show a helpful message' \
    'echo "Baserow all-in-one dev container"' \
    'echo "  j           - See available commands"' \
    'echo "Backend:"' \
    'echo "  m <cmd>     - Django manage.py (e.g., m shell_plus)"' \
    'echo "  pytest      - Run tests"' \
    'echo "Frontend:"' \
    'echo "  y <cmd>     - Run yarn commands"' \
    > /baserow/.bashrc

USER root
HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/baserow.sh"]
CMD ["start"]
EXPOSE 80


# =============================================================================
# Production Lite - no embedded database/cache (use external services)
# =============================================================================
FROM base AS prod-lite
ARG UID
ARG GID

ENV DJANGO_SETTINGS_MODULE='baserow.config.settings.base' \
    PYTHONPATH="/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src"

# Copy from pre-built images
COPY --link --from=web_frontend_image /baserow/ /baserow/
COPY --link --from=backend_image /baserow/ /baserow/

COPY --chown=$UID:$GID ./backend/docker/mime.types /etc/
COPY --chown=$UID:$GID Caddyfile /baserow/caddy/Caddyfile
COPY --chown=$UID:$GID deploy/all-in-one/supervisor/ /baserow/supervisor
COPY --chown=$UID:$GID deploy/all-in-one/baserow.sh /baserow.sh
COPY --chown=$UID:$GID deploy/plugins/*.sh /baserow/plugins/

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/baserow.sh"]
CMD ["start"]
EXPOSE 80


# =============================================================================
# Production - adds embedded PostgreSQL + Redis
# =============================================================================
FROM base AS prod
ARG UID
ARG GID

ENV DJANGO_SETTINGS_MODULE='baserow.config.settings.base' \
    PYTHONPATH="/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src"

# Add PostgreSQL repo (for pgvector) and install postgres + redis
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/postgresql.list && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
    postgresql-$POSTGRES_VERSION \
    postgresql-${POSTGRES_VERSION}-pgvector \
    redis-server && \
    # Setup redis
    usermod -a -G tty redis && \
    sed -i 's/daemonize yes/daemonize no/g' /etc/redis/redis.conf && \
    sed -i 's/daemonize no/daemonize no\nbind 127.0.0.1/g' /etc/redis/redis.conf && \
    sed -i '/^logfile/d' /etc/redis/redis.conf && \
    chown redis:redis /etc/redis/redis.conf

COPY --link --from=web_frontend_image /baserow/ /baserow/
COPY --link --from=backend_image /baserow/ /baserow/

COPY --chown=$UID:$GID ./backend/docker/mime.types /etc/
COPY --chown=$UID:$GID Caddyfile /baserow/caddy/Caddyfile
COPY --chown=$UID:$GID deploy/all-in-one/supervisor/ /baserow/supervisor
COPY --chown=$UID:$GID deploy/all-in-one/baserow.sh /baserow.sh
COPY --chown=$UID:$GID deploy/plugins/*.sh /baserow/plugins/

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/baserow.sh"]
CMD ["start"]
EXPOSE 80