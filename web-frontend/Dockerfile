FROM node:24-bookworm as base

ARG UID
ENV UID=${UID:-9999}
ARG GID
ENV GID=${GID:-9999}
ENV NODE_OPTIONS=--openssl-legacy-provider


# Perform all OS package installation and cleanup in one single command to reduce the
# size of the created layer.
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gnupg2 \
    dos2unix \
    tini \
    git \
    && apt-get autoclean \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*

# Install su-exec as a safer alternative to gosu
RUN curl -L -o /usr/local/bin/su-exec.c https://github.com/ncopa/su-exec/raw/master/su-exec.c \
    && gcc -Wall -Werror -static -o /usr/local/bin/su-exec /usr/local/bin/su-exec.c \
    && chmod 0755 /usr/local/bin/su-exec \
    && rm /usr/local/bin/su-exec.c

# The node image already creates a non-root user to run as, update its ids so they
# match the provided UID and GID we wish to build and run this image with.
# If GID or UID already exist that's OK no need to stop the build.
RUN groupmod -g ${GID} node || exit 0
RUN usermod -u ${UID} -g ${GID} node || exit 0
ENV DOCKER_USER=node
ENV BASEROW_IMAGE_TYPE="web-frontend"

USER $UID:$GID

# Create and install the dependencies in separate COPY commands
COPY --chown=$UID:$GID ./web-frontend/package.json ./web-frontend/yarn.lock /baserow/web-frontend/

WORKDIR /baserow/web-frontend

# We still need dev-dependencies as we will be running a nuxt build below
RUN yarn install && yarn cache clean

COPY --chown=$UID:$GID ./web-frontend /baserow/web-frontend/
COPY --chown=$UID:$GID ./premium/web-frontend /baserow/premium/web-frontend/
COPY --chown=$UID:$GID ./enterprise/web-frontend /baserow/enterprise/web-frontend/
COPY --chown=$UID:$GID ./deploy/plugins/*.sh /baserow/plugins/

RUN dos2unix /baserow/web-frontend/docker/docker-entrypoint.sh && \
    chmod a+x /baserow/web-frontend/docker/docker-entrypoint.sh

# tini installed above protects us from zombie processes and ensures the default signal
# handlers work, see https://github.com/krallin/tini.
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/web-frontend/docker/docker-entrypoint.sh"]
HEALTHCHECK --interval=60s CMD ["curl", "-f", "http://localhost:3000/_health/"]
EXPOSE 3000

FROM base as dev

COPY --chown=$UID:$GID ./tests /baserow/tests/

# Create symlinks for jest tests
RUN ln -s /baserow/web-frontend/node_modules/ /baserow/premium/web-frontend/node_modules \
    && ln -s /baserow/web-frontend/node_modules/ /baserow/enterprise/web-frontend/node_modules

# We don't bother running build-local in dev mode as it pre-compiles nuxt which won't
# be used when running the nuxt dev server.
CMD ["nuxt-dev"]

FROM base as local

# Run the nuxt build and then remove all dev dependencies as we don't need them after.
RUN yarn run build-local && rm -rf node_modules && yarn install --production && yarn cache clean
CMD ["nuxt-local"]

