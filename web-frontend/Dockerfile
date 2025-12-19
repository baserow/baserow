# syntax=docker/dockerfile:1.4
ARG UID="9999"
ARG GID="9999"

# =============================================================================
# Builder for su-exec (replaces gosu, smaller footprint)
# Pinned to v0.2 (commit 212b75144bbc) with SHA256 verification
# =============================================================================
FROM debian:bookworm-slim AS tool-builder

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
FROM node:24-bookworm-slim AS builder-ci
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
FROM node:24-bookworm-slim AS builder-prod
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

COPY --link --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix
RUN dos2unix /baserow/web-frontend/docker/docker-entrypoint.sh \
    && chmod a+x /baserow/web-frontend/docker/docker-entrypoint.sh \
    && chown $UID:$GID /baserow/web-frontend/docker/docker-entrypoint.sh

USER $UID:$GID
WORKDIR /baserow/web-frontend

# Build, then clean reinstall production only
RUN --mount=type=cache,target=$YARN_CACHE_FOLDER,uid=$UID,gid=$GID,sharing=locked \
    yarn run build-local \
    && find .nuxt -type f -name "*.map" -delete


# =============================================================================
# CI target - used in CI pipelines
# =============================================================================
FROM node:24-bookworm-slim AS ci
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="web-frontend"

RUN groupadd --system --gid $GID ${DOCKER_USER} && \
    useradd --shell /bin/bash -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER}

COPY --link --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --link --from=tool-builder /usr/bin/tini /usr/bin/tini
COPY --from=busybox:musl /bin/wget /usr/local/bin/wget

RUN mkdir -p /baserow/web-frontend/.cache /baserow/reports /baserow/.cache /baserow/.yarn /baserow/web-frontend/reports/coverage && \
    chown -R $UID:$GID /baserow

# Copy dependencies and source code
COPY --chown=$UID:$GID web-frontend /baserow/web-frontend
COPY --chown=$UID:$GID premium/web-frontend /baserow/premium/web-frontend
COPY --chown=$UID:$GID enterprise/web-frontend /baserow/enterprise/web-frontend/

COPY --link --from=builder-ci /baserow/web-frontend/node_modules /baserow/web-frontend/node_modules
COPY --link --from=builder-prod /baserow/web-frontend/.nuxt /baserow/web-frontend/.nuxt

COPY --chown=$UID:$GID tests /baserow/tests
COPY --chown=$UID:$GID deploy/plugins/*.sh /baserow/plugins/

USER $UID:$GID
WORKDIR /baserow/web-frontend

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]
HEALTHCHECK --interval=60s CMD wget -q -O /dev/null http://localhost:3000/_health/ || exit 1
CMD ["nuxt-local"]


# =============================================================================
# Development target - used for local development with live reload
# =============================================================================
FROM node:24-bookworm-slim AS dev
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
    sudo

ENV DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="web-frontend" \
    PATH="/baserow/web-frontend/node_modules/.bin:$PATH" \
    YARN_CACHE_FOLDER=/tmp/.yarn-dev-cache

# Install rust-just for running justfiles
RUN pip3 install --break-system-packages rust-just

COPY --link --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --link --from=tool-builder /usr/bin/tini /usr/bin/tini
COPY --link --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix

RUN getent group $GID || groupadd --system --gid $GID ${DOCKER_USER} && \
    useradd --shell /bin/bash -l -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER} && \
    echo "${DOCKER_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${DOCKER_USER} && \
    chmod 0440 /etc/sudoers.d/${DOCKER_USER}

RUN mkdir -p /baserow/web-frontend /baserow/premium/web-frontend /baserow/enterprise/web-frontend && \
    chown -R $UID:$GID /baserow

USER $UID:$GID
WORKDIR /baserow/web-frontend

# Configure tmux to preserve environment variables (don't start login shell)
RUN echo 'set -g default-command "${SHELL}"' > /baserow/.tmux.conf

# Create .bashrc with environment variables for interactive shells
RUN printf '%s\n' \
    '# Aliases' \
    'alias j="just"' \
    'alias y="yarn"' \
    '' \
    '# Show a helpful message' \
    'echo "Baserow frontend dev container"' \
    'echo "  y <cmd>  - Run yarn commands"' \
    'echo "  j        - See available commands"' \
    > /baserow/.bashrc

COPY --chown=$UID:$GID web-frontend/docker/docker-entrypoint.sh /baserow/web-frontend/docker/docker-entrypoint.sh

RUN dos2unix /baserow/web-frontend/docker/docker-entrypoint.sh \
    && chmod a+x /baserow/web-frontend/docker/docker-entrypoint.sh

COPY --chown=$UID:$GID web-frontend/package.json /baserow/web-frontend/package.json
COPY --chown=$UID:$GID web-frontend/yarn.lock /baserow/web-frontend/yarn.lock

# Install dependencies (including dev)
RUN --mount=type=cache,target=$YARN_CACHE_FOLDER,uid=$UID,gid=$GID,sharing=locked \
    yarn install --pure-lockfile --cache-folder $YARN_CACHE_FOLDER

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]
HEALTHCHECK --interval=60s CMD wget -q -O /dev/null http://localhost:3000/_health/ || exit 1
CMD ["nuxt-dev"]


# =============================================================================
# Production target - minimal image with only runtime requirements
# =============================================================================
FROM node:24-bookworm-slim AS local-base
ARG UID
ARG GID

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

ENV DOCKER_USER=baserow_docker_user \
    BASEROW_IMAGE_TYPE="web-frontend" \
    NODE_ENV=production \
    YARN_CACHE_FOLDER=/tmp/.yarn-cache

COPY --link --from=tool-builder /usr/bin/dos2unix /usr/local/bin/dos2unix
COPY --link --from=tool-builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --link --from=tool-builder /usr/bin/tini /usr/bin/tini
COPY --from=busybox:musl /bin/wget /usr/local/bin/wget

RUN groupadd --system --gid $GID ${DOCKER_USER} && \
    useradd --shell /bin/bash -u $UID -g $GID -o -c "" -d /baserow -m ${DOCKER_USER}

USER $UID:$GID
RUN mkdir -p /baserow/web-frontend
WORKDIR /baserow/web-frontend

# Install dependencies first (cached unless package.json/yarn.lock change)
RUN --mount=type=cache,target=$YARN_CACHE_FOLDER,uid=$UID,gid=$GID,sharing=locked \
    --mount=type=bind,source=web-frontend/package.json,target=/baserow/web-frontend/package.json \
    --mount=type=bind,source=web-frontend/yarn.lock,target=/baserow/web-frontend/yarn.lock \
    yarn install --production --pure-lockfile --cache-folder $YARN_CACHE_FOLDER \
    # Clean up unnecessary files to reduce image size
    && find node_modules -type f -name "*.map" -delete \
    && find node_modules -type f \( \
        -name "*.md" -o -name "*.markdown" \
        -o -name "*.ts" -o -name "*.d.ts" \
        -o -name "LICENSE*" -o -name "license*" -o -name "License*" \
        -o -name "CHANGELOG*" -o -name "HISTORY*" \
        -o -name ".npmignore" -o -name ".gitignore" -o -name ".eslintrc*" \
    \) -delete \
    && find node_modules -type d \( \
        -name "test" -o -name "tests" -o -name "__tests__" \
        -o -name "example" -o -name "examples" \
        -o -name "doc" -o -name "docs" \
        -o -name ".github" \
    \) -prune -exec rm -rf {} +

COPY --chown=$UID:$GID web-frontend /baserow/web-frontend
COPY --chown=$UID:$GID premium/web-frontend /baserow/premium/web-frontend
COPY --chown=$UID:$GID enterprise/web-frontend /baserow/enterprise/web-frontend/
COPY --chown=$UID:$GID ./deploy/plugins/*.sh /baserow/plugins/

HEALTHCHECK --interval=60s CMD wget -q -O /dev/null http://localhost:3000/_health/ || exit 1
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]

FROM local-base AS local

COPY --link --from=builder-prod /baserow/web-frontend/.nuxt /baserow/web-frontend/.nuxt

CMD ["nuxt-local"]


FROM local AS prod

CMD ["nuxt-local"]