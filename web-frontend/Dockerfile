# syntax=docker/dockerfile:1.4
ARG UID="9999"
ARG GID="9999"

# =============================================================================
# Builder for su-exec (replaces gosu, smaller footprint)
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
    apt-get install -y --no-install-recommends ca-certificates curl build-essential dos2unix tini && \
    curl -fsSL -o /usr/local/bin/su-exec.c "https://github.com/ncopa/su-exec/raw/${SU_EXEC_VERSION}/su-exec.c" && \
    echo "${SU_EXEC_SHA256}  /usr/local/bin/su-exec.c" | sha256sum -c - && \
    gcc -Wall -Werror -static -o /usr/local/bin/su-exec /usr/local/bin/su-exec.c && \
    chmod 0755 /usr/local/bin/su-exec


# =============================================================================
# CI builder stage
# =============================================================================
FROM node:24.13.0-trixie-slim AS builder-ci
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV YARN_CACHE_FOLDER=/tmp/.yarn-cache

RUN mkdir -p /baserow/web-frontend /baserow/premium/web-frontend /baserow/enterprise/web-frontend && \
    chown -R $UID:$GID /baserow

USER $UID:$GID
WORKDIR /baserow/web-frontend

# Install dependencies (including dev)
RUN --mount=type=cache,target=$YARN_CACHE_FOLDER,uid=$UID,gid=$GID,sharing=locked \
    --mount=type=bind,source=web-frontend/package.json,target=/baserow/web-frontend/package.json \
    --mount=type=bind,source=web-frontend/yarn.lock,target=/baserow/web-frontend/yarn.lock \
    yarn install --pure-lockfile --cache-folder $YARN_CACHE_FOLDER


# =============================================================================
# Production builder stage
# =============================================================================
FROM node:24.13.0-trixie-slim AS builder-prod
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV YARN_CACHE_FOLDER=/tmp/.yarn-cache \
    NUXT_TELEMETRY_DISABLED=1 \
    NODE_OPTIONS="--max-old-space-size=4096" \
    NODE_ENV=production

RUN mkdir -p /baserow/web-frontend /baserow/premium/web-frontend /baserow/enterprise/web-frontend && \
    chown -R $UID:$GID /baserow/

# Copy source code
COPY --chown=$UID:$GID ./web-frontend /baserow/web-frontend/
COPY --chown=$UID:$GID ./premium/web-frontend /baserow/premium/web-frontend/
COPY --chown=$UID:$GID ./enterprise/web-frontend /baserow/enterprise/web-frontend/

# Copy all dependencies so we can build the production files
COPY --chown=$UID:$GID --from=builder-ci /baserow/web-frontend/node_modules /baserow/web-frontend/node_modules

# Create symlinks because premium and enterprise are node packages
RUN ln -s /baserow/web-frontend/node_modules/ /baserow/premium/web-frontend/node_modules \
    && ln -s /baserow/web-frontend/node_modules/ /baserow/enterprise/web-frontend/node_modules

COPY --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix
RUN dos2unix /baserow/web-frontend/docker/docker-entrypoint.sh \
    && chmod a+x /baserow/web-frontend/docker/docker-entrypoint.sh \
    && chown $UID:$GID /baserow/web-frontend/docker/docker-entrypoint.sh

USER $UID:$GID
WORKDIR /baserow/web-frontend

# Build, then clean reinstall production only
RUN --mount=type=cache,target=$YARN_CACHE_FOLDER,uid=$UID,gid=$GID,sharing=locked \
    yarn run build \
    && find .output -type f -name "*.map" -delete


# =============================================================================
# Busybox helper stage for wget binary
# =============================================================================
FROM busybox:musl AS busybox-helper

# =============================================================================
# CI target - used in CI pipelines
# =============================================================================
FROM node:24.13.0-trixie-slim AS ci
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DOCKER_USER=baserow_docker_user \
    APP_ENV=test \
    BASEROW_IMAGE_TYPE="web-frontend"

RUN groupadd --system --gid $GID ${DOCKER_USER} && \
    useradd --shell /bin/bash -l -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER}

COPY --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=tool-builder /usr/bin/tini /usr/bin/tini
COPY --from=busybox-helper /bin/wget /usr/local/bin/wget

RUN mkdir -p /baserow/reports /baserow/.cache /baserow/.yarn && \
    chown -R $UID:$GID /baserow

# Copy dependencies and source code
COPY --chown=$UID:$GID ./eslint.config.mjs /baserow/eslint.config.mjs
COPY --chown=$UID:$GID web-frontend /baserow/web-frontend
COPY --chown=$UID:$GID premium/web-frontend /baserow/premium/web-frontend
COPY --chown=$UID:$GID enterprise/web-frontend /baserow/enterprise/web-frontend

COPY --chown=$UID:$GID --from=builder-ci /baserow/web-frontend/node_modules /baserow/web-frontend/node_modules
COPY --chown=$UID:$GID --from=builder-prod /baserow/web-frontend/.nuxt /baserow/web-frontend/.nuxt
COPY --chown=$UID:$GID --from=builder-prod /baserow/web-frontend/.output /baserow/web-frontend/.output

# Create symlinks and cache directories (after COPY so they don't get overwritten)
RUN ln -s /baserow/web-frontend/node_modules/ /baserow/premium/web-frontend/node_modules \
    && ln -s /baserow/web-frontend/node_modules/ /baserow/enterprise/web-frontend/node_modules \
    && mkdir -p /baserow/web-frontend/.cache /baserow/web-frontend/reports/coverage \
    && chown -R $UID:$GID /baserow/web-frontend/.cache /baserow/web-frontend/reports

COPY --chown=$UID:$GID tests /baserow/tests
COPY --chown=$UID:$GID deploy/plugins/*.sh /baserow/plugins/

USER $UID:$GID
WORKDIR /baserow/web-frontend

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]
HEALTHCHECK --interval=60s CMD wget -q -O /dev/null http://localhost:3000/_health/ || exit 1

CMD ["nuxt-prod"]


# =============================================================================
# Development target - used for local development with live reload
# =============================================================================
FROM node:24.13.0-trixie-slim AS dev
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# hadolint ignore=DL3008
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    python3 \
    python3-pip \
    build-essential \
    curl \
    wget \
    tmux \
    vim \
    lsof \
    procps \
    sudo

ENV DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="web-frontend" \
    PATH="/baserow/web-frontend/node_modules/.bin:$PATH" \
    YARN_CACHE_FOLDER=/tmp/.yarn-dev-cache

# Install rust-just for running justfiles
RUN pip3 install --break-system-packages --no-cache-dir rust-just==1.43.1

COPY --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=tool-builder /usr/bin/tini /usr/bin/tini
COPY --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix

RUN getent group $GID || groupadd --system --gid $GID ${DOCKER_USER} && \
    useradd --shell /bin/bash -l -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER} && \
    echo "${DOCKER_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${DOCKER_USER} && \
    chmod 0440 /etc/sudoers.d/${DOCKER_USER}

RUN mkdir -p /baserow/web-frontend /baserow/premium/web-frontend /baserow/enterprise/web-frontend && \
    chown -R $UID:$GID /baserow

USER $UID:$GID
WORKDIR /baserow/web-frontend

# Configure tmux to preserve environment variables (don't start login shell)
RUN echo "set -g default-command \"\${SHELL}\"" > /baserow/.tmux.conf && \
    printf '%s\n' \
    '# Aliases' \
    'alias j="just"' \
    'alias y="yarn"' \
    '' \
    '# Show a helpful message' \
    'echo "Baserow frontend dev container"' \
    'echo "  y <cmd>  - Run yarn commands"' \
    'echo "  j        - See available commands"' \
    > /baserow/.bashrc

COPY ./eslint.config.mjs /baserow/eslint.config.mjs
COPY --chown=$UID:$GID web-frontend/docker/docker-entrypoint.sh /baserow/web-frontend/docker/docker-entrypoint.sh

RUN dos2unix /baserow/web-frontend/docker/docker-entrypoint.sh \
    && chmod a+x /baserow/web-frontend/docker/docker-entrypoint.sh

COPY --chown=$UID:$GID web-frontend/package.json /baserow/web-frontend/package.json
COPY --chown=$UID:$GID web-frontend/yarn.lock /baserow/web-frontend/yarn.lock

# Create symlinks because premium and enterprise are node packages
RUN ln -s /baserow/web-frontend/node_modules/ /baserow/premium/web-frontend/node_modules \
    && ln -s /baserow/web-frontend/node_modules/ /baserow/enterprise/web-frontend/node_modules

# Make sure these directories exist and are owned by the non-root user
RUN mkdir -p /baserow/web-frontend/.nuxt /baserow/web-frontend/.cache /baserow/web-frontend/.nuxt-storybook /baserow/web-frontend/.output

# Install dependencies (including dev)
RUN --mount=type=cache,target=$YARN_CACHE_FOLDER,uid=$UID,gid=$GID,sharing=locked \
    yarn install --pure-lockfile --cache-folder $YARN_CACHE_FOLDER

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]
HEALTHCHECK --interval=60s CMD wget -q -O /dev/null http://localhost:3000/_health/ || exit 1
CMD ["nuxt-dev"]


# =============================================================================
# Production target - minimal image with only runtime requirements
# =============================================================================
FROM node:24.13.0-trixie-slim AS local
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="web-frontend" \
    NODE_ENV=production \
    YARN_CACHE_FOLDER=/tmp/.yarn-cache

COPY --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix
COPY --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=tool-builder /usr/bin/tini /usr/bin/tini
COPY --from=busybox-helper /bin/wget /usr/local/bin/wget

# Update npm to patch CVEs in its bundled deps (glob, tar, @isaacs/brace-expansion)
RUN npm install -g npm@latest

RUN groupadd --system --gid $GID ${DOCKER_USER} && \
    useradd --shell /bin/bash -l -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER}

USER $UID:$GID
RUN mkdir -p /baserow/web-frontend

COPY --chown=$UID:$GID --from=builder-prod /baserow/web-frontend/.output /baserow/web-frontend/.output
COPY --chown=$UID:$GID ./web-frontend/env-remap.mjs /baserow/web-frontend/env-remap.mjs

HEALTHCHECK --interval=10s CMD wget -q -O /dev/null http://localhost:3000/_health/ || exit 1

WORKDIR /baserow/web-frontend
CMD ["node", "--import", "./env-remap.mjs", ".output/server/index.mjs"]


FROM local AS prod
