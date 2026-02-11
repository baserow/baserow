ARG UID="9999"
ARG GID="9999"

ARG BACKEND_IMAGE=baserow/backend
ARG WEBFRONTEND_IMAGE=baserow/web-frontend
ARG CADDY_VERSION=2.10.2
# hadolint ignore=DL3006
FROM ${BACKEND_IMAGE} AS backend_image
# hadolint ignore=DL3006
FROM ${WEBFRONTEND_IMAGE} AS web_frontend_image
FROM caddy:${CADDY_VERSION} AS caddy_image

# =============================================================================
# Base - system dependencies (cached independently of source images)
# =============================================================================
FROM python:3.14.3-slim-trixie AS base
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DOCKER_USER=baserow_docker_user \
    POSTGRES_VERSION=15 \
    BASEROW_IMAGE_TYPE="all-in-one" \
    DATA_DIR=/baserow/data \
    BASEROW_PLUGIN_DIR=/baserow/data/plugins

# Runtime dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install --no-install-recommends -y \
    curl gnupg2 ca-certificates && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --batch --dearmor -o /usr/share/keyrings/pgdg.gpg && \
    echo "deb [signed-by=/usr/share/keyrings/pgdg.gpg] https://apt.postgresql.org/pub/repos/apt trixie-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive TZ=Etc/UTC apt-get install --no-install-recommends -y \
    supervisor \
    psmisc \
    gawk \
    postgresql-client-"${POSTGRES_VERSION}" \
    xmlsec1 \
    gettext \
    tini \
    && \
    # Setup user and group with fixed UID/GID for volume permission consistency
    getent group "$GID" || groupadd --system --gid "$GID" "${DOCKER_USER}" && \
    useradd --shell /bin/bash -l -u "$UID" -g "$GID" -o -c "" -d /baserow -m "${DOCKER_USER}" && \
    chmod 755 /baserow && \
    # Setup supervisor
    ln -sf /dev/stdout /var/log/supervisor/supervisord.log && \
    # Create data and plugin directories with correct ownership
    mkdir -p "${DATA_DIR}" "${BASEROW_PLUGIN_DIR}" && \
    chown -R "$UID:$GID" "${DATA_DIR}" "${BASEROW_PLUGIN_DIR}"

COPY --from=caddy_image /usr/bin/caddy /usr/bin/caddy

# Copy Node.js, npm, and yarn from web-frontend image (avoids insecure curl|bash from NodeSource)
COPY --from=web_frontend_image /usr/local/bin/node /usr/local/bin/node
COPY --from=web_frontend_image /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=web_frontend_image /opt/yarn-v1.22.22 /opt/yarn-v1.22.22
RUN ln -s /opt/yarn-v1.22.22/bin/yarn /usr/local/bin/yarn

# Copy su-exec from backend image (already built with pinned version + SHA256 verification)
COPY --from=backend_image /usr/local/bin/su-exec /usr/local/bin/su-exec

ENV POSTGRES_LOCATION=/etc/postgresql/15/main \
    UV_PROJECT_ENVIRONMENT=/baserow/venv \
    UV_CACHE_DIR=/tmp/baserow_uv_cache \
    UV_VERBOSE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/baserow/venv/bin:$PATH" \
    PYTHONPATH="/baserow/backend/src:/baserow/premium/backend/src:/baserow/enterprise/backend/src" \
    DJANGO_SETTINGS_MODULE='baserow.config.settings.base' \
    NODE_OPTIONS="--max-old-space-size=4096" \
    NODE_ENV=production


# =============================================================================
# Production Lite - no embedded database/cache (use external services)
# =============================================================================
FROM base AS prod-lite
ARG UID
ARG GID

# Web-frontend
COPY --chown=$UID:$GID --from=web_frontend_image /baserow/web-frontend /baserow/web-frontend

# Backend
COPY --chown=$UID:$GID --from=backend_image /baserow/backend /baserow/backend
COPY --chown=$UID:$GID --from=backend_image /baserow/premium/backend /baserow/premium/backend
COPY --chown=$UID:$GID --from=backend_image /baserow/enterprise/backend /baserow/enterprise/backend
COPY --chown=$UID:$GID --from=backend_image /baserow/venv /baserow/venv

# Configuration and startup scripts
COPY ./backend/docker/mime.types /etc/
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

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install postgres + redis (PGDG repo already added in base stage)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install --no-install-recommends -y \
    "postgresql-${POSTGRES_VERSION}" \
    "postgresql-${POSTGRES_VERSION}-pgvector" \
    redis-server && \
    # Setup redis
    usermod -a -G tty redis && \
    sed -i 's/daemonize yes/daemonize no/g' /etc/redis/redis.conf && \
    sed -i 's/daemonize no/daemonize no\nbind 127.0.0.1/g' /etc/redis/redis.conf && \
    sed -i '/^logfile/d' /etc/redis/redis.conf && \
    chown redis:redis /etc/redis/redis.conf

# Web-frontend
COPY --chown=$UID:$GID --from=web_frontend_image /baserow/web-frontend /baserow/web-frontend

# Backend
COPY --chown=$UID:$GID --from=backend_image /baserow/backend /baserow/backend
COPY --chown=$UID:$GID --from=backend_image /baserow/premium/backend /baserow/premium/backend
COPY --chown=$UID:$GID --from=backend_image /baserow/enterprise/backend /baserow/enterprise/backend
COPY --chown=$UID:$GID --from=backend_image /baserow/venv /baserow/venv

# Configuration and startup scripts
COPY ./backend/docker/mime.types /etc/
COPY --chown=$UID:$GID Caddyfile /baserow/caddy/Caddyfile
COPY --chown=$UID:$GID deploy/all-in-one/supervisor/ /baserow/supervisor
COPY --chown=$UID:$GID deploy/all-in-one/baserow.sh /baserow.sh
COPY --chown=$UID:$GID deploy/plugins/*.sh /baserow/plugins/

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/baserow.sh"]
CMD ["start"]
EXPOSE 80