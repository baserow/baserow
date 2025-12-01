# syntax=docker/dockerfile:1.4
ARG BACKEND_IMAGE=baserow_backend
ARG WEBFRONTEND_IMAGE=baserow_web-frontend
# hadolint ignore=DL3006
FROM ${BACKEND_IMAGE}:latest AS backend_image_prod
# hadolint ignore=DL3006
FROM ${BACKEND_IMAGE}:dev AS backend_image_dev
# hadolint ignore=DL3006
FROM ${WEBFRONTEND_IMAGE}:latest AS web_frontend_image
# hadolint ignore=DL3006
FROM ${WEBFRONTEND_IMAGE}:dev AS web_frontend_image_dev

# =============================================================================
# Builder - compile su-exec
# =============================================================================
FROM debian:bookworm-slim AS builder

RUN apt-get update && \
    apt-get install --no-install-recommends -y ca-certificates curl build-essential && \
    curl -L -o /usr/local/bin/su-exec.c https://github.com/ncopa/su-exec/raw/master/su-exec.c && \
    gcc -Wall -Werror -static -o /usr/local/bin/su-exec /usr/local/bin/su-exec.c && \
    chmod 0755 /usr/local/bin/su-exec

# =============================================================================
# Production - minimal runtime image
# =============================================================================
FROM debian:bookworm-slim AS prod

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ARG UID
ENV UID=${UID:-9999}
ARG GID
ENV GID=${GID:-9999}
ARG DOCKER_USER
ENV DOCKER_USER=${DOCKER_USER:-baserow_docker_user}

ENV DATA_DIR=/baserow/data \
    BASEROW_PLUGIN_DIR=/baserow/data/plugins \
    POSTGRES_VERSION=15 \
    POSTGRES_LOCATION=/etc/postgresql/15/main \
    NODE_MAJOR=24 \
    BASEROW_IMAGE_TYPE="all-in-one" \
    PATH="/baserow/venv/bin:$PATH"

# Runtime dependencies only
RUN apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install --no-install-recommends -y \
    supervisor curl gnupg2 ca-certificates && \
    # Add PostgreSQL repo (for pgvector)
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/postgresql.list && \
    # Add Node.js repo
    curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
    postgresql-$POSTGRES_VERSION \
    postgresql-${POSTGRES_VERSION}-pgvector \
    postgresql-client-$POSTGRES_VERSION \
    redis-server \
    python3.11 \
    tini \
    psmisc \
    gawk \
    xmlsec1 \
    nodejs && \
    npm install --global yarn@1.22.19 && \
    # Install Caddy
    curl -o caddy.tar.gz -sL "https://github.com/caddyserver/caddy/releases/download/v2.7.6/caddy_2.7.6_linux_$(dpkg --print-architecture).tar.gz" && \
    tar -xf caddy.tar.gz && mv caddy /usr/bin/ && rm caddy.tar.gz && \
    # Setup users
    ( groupadd -g "$GID" baserow_docker_group || true ) && \
    ( useradd --shell /bin/bash -u $UID -g "$GID" -o -c "" -m "$DOCKER_USER" -l || true ) && \
    usermod -a -G tty "$DOCKER_USER" && \
    # Setup supervisor
    ln -sf /dev/stdout /var/log/supervisor/supervisord.log && \
    # Setup redis
    usermod -a -G tty redis && \
    sed -i 's/daemonize yes/daemonize no/g' /etc/redis/redis.conf && \
    sed -i 's/daemonize no/daemonize no\nbind 127.0.0.1/g' /etc/redis/redis.conf && \
    sed -i '/^logfile/d' /etc/redis/redis.conf && \
    chown redis:redis /etc/redis/redis.conf && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy su-exec from builder
COPY --link --from=builder /usr/local/bin/su-exec /usr/local/bin/su-exec

# Copy from pre-built images
COPY --link --chown=$UID:$GID --from=web_frontend_image /baserow/ /baserow/
COPY --link --chown=$UID:$GID --from=backend_image_prod /baserow/ /baserow/

COPY --link --chown=$UID:$GID ./backend/docker/mime.types /etc/
COPY --link --chown=$UID:$GID Caddyfile /baserow/caddy/Caddyfile
COPY --link --chown=$UID:$GID deploy/all-in-one/supervisor/ /baserow/supervisor
COPY --link --chown=$UID:$GID deploy/all-in-one/baserow.sh /baserow.sh
COPY --link --chown=$UID:$GID deploy/plugins/*.sh /baserow/plugins/

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/baserow.sh"]
CMD ["start"]
EXPOSE 80

# =============================================================================
# Development - adds dev tools, backend dev venv, and frontend dev deps
# =============================================================================
FROM prod AS dev

# Override venv with dev backend image (includes dev dependencies)
COPY --link --chown=$UID:$GID --from=backend_image_dev /baserow/venv /baserow/venv
COPY --link --chown=$UID:$GID --from=backend_image_dev /baserow/backend/tests /baserow/backend/tests
COPY --link --chown=$UID:$GID --from=backend_image_dev /baserow/premium/backend/tests /baserow/premium/backend/tests
COPY --link --chown=$UID:$GID --from=backend_image_dev /baserow/enterprise/backend/tests /baserow/enterprise/backend/tests

# Override web frontend with dev image (includes dev dependencies and tests)
COPY --link --chown=$UID:$GID --from=web_frontend_image_dev /baserow/web-frontend /baserow/web-frontend
COPY --link --chown=$UID:$GID --from=web_frontend_image_dev /baserow/tests /baserow/tests

# Install uv and dev tools
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
    git \
    procps \
    build-essential \
    python3.11-dev && \
    rm -rf /var/lib/apt/lists/*

ENV BASEROW_ALL_IN_ONE_DEV_MODE='true'

