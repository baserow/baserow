# syntax=docker/dockerfile:1.4

# =============================================================================
# Builder for su-exec (replaces gosu, smaller footprint)
# =============================================================================
FROM debian:bookworm-slim AS su-exec-builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates curl build-essential && \
    curl -L -o /usr/local/bin/su-exec.c https://github.com/ncopa/su-exec/raw/master/su-exec.c && \
    gcc -Wall -Werror -static -o /usr/local/bin/su-exec /usr/local/bin/su-exec.c && \
    chmod 0755 /usr/local/bin/su-exec

# =============================================================================
# Builder packages stage - fully cached (no UID/GID dependency)
# =============================================================================
FROM node:24-bookworm-slim AS builder-packages

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    dos2unix \
    python3 \
    && rm -rf /var/lib/apt/lists/*

# Update node user to fixed UID 9999 (always cached)
RUN groupmod -g 9999 node && usermod -u 9999 -g 9999 node

# =============================================================================
# Builder - compiles dependencies with fixed UID
# =============================================================================
FROM builder-packages AS builder

USER 9999:9999

WORKDIR /baserow/web-frontend

# Copy source
COPY --chown=9999:9999 ./web-frontend /baserow/web-frontend/
COPY --chown=9999:9999 ./premium/web-frontend /baserow/premium/web-frontend/
COPY --chown=9999:9999 ./enterprise/web-frontend /baserow/enterprise/web-frontend/
COPY --chown=9999:9999 ./deploy/plugins/*.sh /baserow/plugins/

# Fix entrypoint
RUN dos2unix /baserow/web-frontend/docker/docker-entrypoint.sh && \
    chmod a+x /baserow/web-frontend/docker/docker-entrypoint.sh

# Install all dependencies and build (with cache mount for faster rebuilds)
RUN --mount=type=cache,target=/home/node/.cache/yarn,uid=9999,gid=9999 \
    yarn install && yarn run build-local

# =============================================================================
# Builder for production (fresh stage with prod deps only)
# =============================================================================
FROM builder-packages AS builder-prod

USER 9999:9999
WORKDIR /baserow/web-frontend

# Copy built .nuxt and source from builder (without node_modules)
COPY --link --chown=9999:9999 --from=builder /baserow/web-frontend/.nuxt /baserow/web-frontend/.nuxt
COPY --link --chown=9999:9999 --from=builder /baserow/web-frontend/package.json /baserow/web-frontend/
COPY --link --chown=9999:9999 --from=builder /baserow/web-frontend/yarn.lock /baserow/web-frontend/
COPY --link --chown=9999:9999 --from=builder /baserow/web-frontend/nuxt.config.js /baserow/web-frontend/
COPY --link --chown=9999:9999 --from=builder /baserow/web-frontend/config /baserow/web-frontend/config
COPY --link --chown=9999:9999 --from=builder /baserow/web-frontend/modules /baserow/web-frontend/modules
COPY --link --chown=9999:9999 --from=builder /baserow/web-frontend/locales /baserow/web-frontend/locales
COPY --link --chown=9999:9999 --from=builder /baserow/web-frontend/docker /baserow/web-frontend/docker
COPY --link --chown=9999:9999 --from=builder /baserow/premium/web-frontend /baserow/premium/web-frontend
COPY --link --chown=9999:9999 --from=builder /baserow/enterprise/web-frontend /baserow/enterprise/web-frontend
COPY --link --chown=9999:9999 --from=builder /baserow/plugins /baserow/plugins

# Install production dependencies only (with cache mount for faster rebuilds)
RUN --mount=type=cache,target=/home/node/.cache/yarn,uid=9999,gid=9999 \
    yarn install --production && \
    find node_modules -type f \( -name "*.o" -o -name "*.a" \) -delete && \
    find node_modules -type d \( -name "test" -o -name "tests" -o -name "__tests__" -o -name "example" -o -name "examples" -o -name "doc" -o -name "docs" \) -prune -exec rm -rf '{}' + && \
    find .nuxt -type f -name "*.map" -delete

# =============================================================================
# Runtime packages stage - fully cached (no UID/GID dependency)
# =============================================================================
FROM node:24-bookworm-slim AS runtime-packages

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tini \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy su-exec from builder
COPY --link --from=su-exec-builder /usr/local/bin/su-exec /usr/local/bin/su-exec

# Update node user to fixed UID 9999 (always cached)
RUN groupmod -g 9999 node && usermod -u 9999 -g 9999 node

# =============================================================================
# Production (build with --target prod, tag as :latest)
# =============================================================================
FROM runtime-packages AS prod

ENV DOCKER_USER=node
ENV BASEROW_IMAGE_TYPE="web-frontend"

USER 9999:9999

WORKDIR /baserow/web-frontend

# Copy only what's needed from builder-prod
COPY --link --chown=9999:9999 --from=builder-prod /baserow /baserow

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]
HEALTHCHECK --interval=60s CMD ["curl", "-f", "http://localhost:3000/_health/"]
EXPOSE 3000
CMD ["nuxt-local"]

# =============================================================================
# Dev packages stage - fully cached (no UID/GID dependency)
# =============================================================================
FROM node:24-bookworm-slim AS dev-packages

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    tini \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy su-exec from builder
COPY --link --from=su-exec-builder /usr/local/bin/su-exec /usr/local/bin/su-exec

# Update node user to fixed UID 9999 (always cached)
RUN groupmod -g 9999 node && usermod -u 9999 -g 9999 node

# =============================================================================
# Development (build with --target dev, tag as :dev)
# Starts as root, entrypoint switches to host user via su-exec
# =============================================================================
FROM dev-packages AS dev

ENV DOCKER_USER=node
ENV BASEROW_IMAGE_TYPE="web-frontend"

WORKDIR /baserow/web-frontend

# Copy source and full node_modules from builder (with dev deps)
COPY --link --from=builder /baserow/web-frontend /baserow/web-frontend
COPY --link --from=builder /baserow/premium/web-frontend /baserow/premium/web-frontend
COPY --link --from=builder /baserow/enterprise/web-frontend /baserow/enterprise/web-frontend
COPY --link --from=builder /baserow/plugins /baserow/plugins
COPY --link ./tests /baserow/tests/

# Make everything owned by node user (9999) - entrypoint will switch at runtime
RUN chown -R 9999:9999 /baserow && \
    ln -s /baserow/web-frontend/node_modules/ /baserow/premium/web-frontend/node_modules && \
    ln -s /baserow/web-frontend/node_modules/ /baserow/enterprise/web-frontend/node_modules

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]
HEALTHCHECK --interval=60s CMD ["curl", "-f", "http://localhost:3000/_health/"]
EXPOSE 3000
CMD ["nuxt-dev"]
