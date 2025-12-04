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
# Builder packages stage - fully cached (no UID/GID dependency)
# =============================================================================
FROM node:24-bookworm-slim AS builder-packages

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Update node user to fixed UID 9999 (always cached)
RUN groupmod -g 9999 node && usermod -u 9999 -g 9999 node

# =============================================================================
# Builder - compiles dependencies with fixed UID
# =============================================================================
FROM builder-packages AS builder

USER 9999:9999

WORKDIR /baserow/web-frontend

# Copy package files first (changes less often than source)
COPY --chown=9999:9999 ./web-frontend/package.json ./web-frontend/yarn.lock /baserow/web-frontend/

# Install dependencies (cached unless package.json/yarn.lock change)
RUN --mount=type=cache,target=/home/node/.cache/yarn,uid=9999,gid=9999 \
    yarn install

# Copy source code (changes more often)
COPY --chown=9999:9999 ./web-frontend /baserow/web-frontend/
COPY --chown=9999:9999 ./premium/web-frontend /baserow/premium/web-frontend/
COPY --chown=9999:9999 ./enterprise/web-frontend /baserow/enterprise/web-frontend/
COPY --chown=9999:9999 ./deploy/plugins/*.sh /baserow/plugins/

# Fix entrypoint
RUN dos2unix /baserow/web-frontend/docker/docker-entrypoint.sh && \
    chmod a+x /baserow/web-frontend/docker/docker-entrypoint.sh

# Build (only this runs when source changes, yarn install is cached)
RUN yarn run build-local

# =============================================================================
# Builder for CI (no build step - tests/lint don't need .nuxt output)
# =============================================================================
FROM builder-packages AS builder-ci

USER 9999:9999

WORKDIR /baserow/web-frontend

# Copy package files first (changes less often than source)
COPY --chown=9999:9999 ./web-frontend/package.json ./web-frontend/yarn.lock /baserow/web-frontend/

# Install dependencies (cached unless package.json/yarn.lock change)
RUN --mount=type=cache,target=/home/node/.cache/yarn,uid=9999,gid=9999 \
    yarn install

# Copy source code (changes more often)
COPY --chown=9999:9999 ./web-frontend /baserow/web-frontend/
COPY --chown=9999:9999 ./premium/web-frontend /baserow/premium/web-frontend/
COPY --chown=9999:9999 ./enterprise/web-frontend /baserow/enterprise/web-frontend/
COPY --chown=9999:9999 ./deploy/plugins/*.sh /baserow/plugins/

# Fix entrypoint
RUN dos2unix /baserow/web-frontend/docker/docker-entrypoint.sh && \
    chmod a+x /baserow/web-frontend/docker/docker-entrypoint.sh

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
# CI Target - lightweight image for tests and linting (no dev tools)
# =============================================================================
FROM runtime-packages AS ci

ENV DOCKER_USER=node
ENV BASEROW_IMAGE_TYPE="web-frontend"

USER 9999:9999

WORKDIR /baserow/web-frontend

# Copy source and full node_modules from builder-ci (with dev deps for testing)
# Note: Uses builder-ci which skips the slow Nuxt build (not needed for tests/lint)
COPY --link --chown=9999:9999 --from=builder-ci /baserow/web-frontend /baserow/web-frontend
COPY --link --chown=9999:9999 --from=builder-ci /baserow/premium/web-frontend /baserow/premium/web-frontend
COPY --link --chown=9999:9999 --from=builder-ci /baserow/enterprise/web-frontend /baserow/enterprise/web-frontend
COPY --link --chown=9999:9999 --from=builder-ci /baserow/plugins /baserow/plugins
COPY --link --chown=9999:9999 ./tests /baserow/tests/

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]

# =============================================================================
# Dev packages stage - fully cached (no UID/GID dependency)
# =============================================================================
FROM node:24-bookworm-slim AS dev-packages

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    python3 \
    python3-pip \
    tini \
    tmux \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Install just command runner
RUN pip3 install --break-system-packages rust-just

# Copy su-exec from builder
COPY --link --from=su-exec-builder /usr/local/bin/su-exec /usr/local/bin/su-exec

# Update node user to fixed UID 9999 (always cached)
RUN groupmod -g 9999 node && usermod -u 9999 -g 9999 node

# =============================================================================
# Development (build with --target dev, tag as :dev)
# Runs as host user via docker-compose user: directive
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

# Make directories writable by any UID (dev only - allows running as host user)
# This avoids slow chown at startup and permission issues with bind mounts
# Also make /etc/passwd writable so entrypoint can add user entry (fixes "I have no name!")
RUN chmod -R a+rwX /baserow/web-frontend && \
    chmod -R a+rwX /baserow/premium/web-frontend && \
    chmod -R a+rwX /baserow/enterprise/web-frontend && \
    chmod -R a+rwX /baserow/plugins && \
    mkdir -p /baserow/.cache && chmod a+rwX /baserow/.cache && \
    chmod a+rw /etc/passwd && \
    ln -s /baserow/web-frontend/node_modules/ /baserow/premium/web-frontend/node_modules && \
    ln -s /baserow/web-frontend/node_modules/ /baserow/enterprise/web-frontend/node_modules

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]
HEALTHCHECK --interval=60s CMD ["curl", "-f", "http://localhost:3000/_health/"]
EXPOSE 3000
CMD ["nuxt-dev"]
