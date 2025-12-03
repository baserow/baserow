# syntax=docker/dockerfile:1.4
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
# Base packages - system dependencies (cached independently of source images)
# =============================================================================
FROM debian:bookworm-slim AS base-packages

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DOCKER_USER=baserow_docker_user

# Caddy checksums for v2.7.6
ENV CADDY_VERSION=2.7.6 \
    CADDY_SHA256_AMD64=99587cf77c595f0bf62cc23c9ea101f9879fa016c7b689d498ce054904821f22 \
    CADDY_SHA256_ARM64=6e6aeca09502a8f0ab0a08acd03bb765e80888052d108de22e0698a9160b7235

# Runtime dependencies (cached - won't rebuild when source images change)
RUN apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install --no-install-recommends -y \
    supervisor curl gnupg2 ca-certificates \
    python3.11 \
    tini \
    psmisc \
    gawk \
    xmlsec1 && \
    # Install Caddy with checksum verification
    ARCH=$(dpkg --print-architecture) && \
    curl -o caddy.tar.gz -sL "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_${ARCH}.tar.gz" && \
    if [ "$ARCH" = "amd64" ]; then echo "${CADDY_SHA256_AMD64}  caddy.tar.gz" | sha256sum -c -; \
    elif [ "$ARCH" = "arm64" ]; then echo "${CADDY_SHA256_ARM64}  caddy.tar.gz" | sha256sum -c -; \
    else echo "Unsupported architecture: $ARCH" && exit 1; fi && \
    tar -xf caddy.tar.gz && mv caddy /usr/bin/ && rm caddy.tar.gz && \
    # Setup users (fixed UID/GID 9999 for build caching)
    ( groupadd -g 9999 baserow_docker_group || true ) && \
    ( useradd --shell /bin/bash -u 9999 -g 9999 -o -c "" -m "$DOCKER_USER" -l || true ) && \
    usermod -a -G tty "$DOCKER_USER" && \
    # Setup supervisor
    ln -sf /dev/stdout /var/log/supervisor/supervisord.log && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# =============================================================================
# Base - common runtime without embedded database/cache
# =============================================================================
FROM base-packages AS base

ENV DATA_DIR=/baserow/data \
    BASEROW_PLUGIN_DIR=/baserow/data/plugins \
    POSTGRES_VERSION=15 \
    BASEROW_IMAGE_TYPE="all-in-one" \
    PATH="/baserow/venv/bin:$PATH"

# Copy Node.js, npm, and yarn from web-frontend image (avoids insecure curl|bash from NodeSource)
COPY --link --from=web_frontend_image /usr/local/bin/node /usr/local/bin/node
COPY --link --from=web_frontend_image /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --link --from=web_frontend_image /opt/yarn-v1.22.22 /opt/yarn-v1.22.22

# Create symlinks for npm/npx/yarn
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx && \
    ln -s /opt/yarn-v1.22.22/bin/yarn /usr/local/bin/yarn

# Copy su-exec from backend image (already built with pinned version + SHA256 verification)
COPY --link --from=backend_image /usr/local/bin/su-exec /usr/local/bin/su-exec

# Copy from pre-built images
COPY --link --chown=9999:9999 --from=web_frontend_image /baserow/ /baserow/
COPY --link --chown=9999:9999 --from=backend_image /baserow/ /baserow/

COPY --link --chown=9999:9999 ./backend/docker/mime.types /etc/
COPY --link --chown=9999:9999 Caddyfile /baserow/caddy/Caddyfile
COPY --link --chown=9999:9999 deploy/all-in-one/supervisor/ /baserow/supervisor
COPY --link --chown=9999:9999 deploy/all-in-one/baserow.sh /baserow.sh
COPY --link --chown=9999:9999 deploy/plugins/*.sh /baserow/plugins/

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/baserow.sh"]
CMD ["start"]
EXPOSE 80

# =============================================================================
# Production Lite - no embedded database/cache (use external services)
# =============================================================================
FROM base AS prod-lite

ENV BASEROW_IMAGE_TYPE="all-in-one-lite"

# =============================================================================
# Production - adds embedded PostgreSQL + Redis
# =============================================================================
FROM base AS prod

ENV POSTGRES_LOCATION=/etc/postgresql/15/main

# Add PostgreSQL repo (for pgvector) and install postgres + redis
RUN apt-get update && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/postgresql.list && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
    postgresql-$POSTGRES_VERSION \
    postgresql-${POSTGRES_VERSION}-pgvector \
    postgresql-client-$POSTGRES_VERSION \
    redis-server && \
    # Setup redis
    usermod -a -G tty redis && \
    sed -i 's/daemonize yes/daemonize no/g' /etc/redis/redis.conf && \
    sed -i 's/daemonize no/daemonize no\nbind 127.0.0.1/g' /etc/redis/redis.conf && \
    sed -i '/^logfile/d' /etc/redis/redis.conf && \
    chown redis:redis /etc/redis/redis.conf && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# =============================================================================
# Development - adds dev tools, backend dev venv, and frontend dev deps
# =============================================================================
FROM prod AS dev

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    git \
    procps \
    build-essential \
    git \
    vim \
    python3.11-dev && \
    rm -rf /var/lib/apt/lists/*

# Install uv and dev tools
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Override venv with dev backend image (includes dev dependencies)
COPY --link --chown=9999:9999 --from=backend_image_dev /baserow/venv /baserow/venv
COPY --link --chown=9999:9999 --from=backend_image_dev /baserow/backend/tests /baserow/backend/tests
COPY --link --chown=9999:9999 --from=backend_image_dev /baserow/premium/backend/tests /baserow/premium/backend/tests
COPY --link --chown=9999:9999 --from=backend_image_dev /baserow/enterprise/backend/tests /baserow/enterprise/backend/tests

# Override web frontend with dev image (includes dev dependencies and tests)
COPY --link --chown=9999:9999 --from=web_frontend_image_dev /baserow/web-frontend /baserow/web-frontend
COPY --link --chown=9999:9999 --from=web_frontend_image_dev /baserow/tests /baserow/tests

RUN ln -s /baserow/venv/bin/just /usr/local/bin/just
ENV BASEROW_ALL_IN_ONE_DEV_MODE='true'

