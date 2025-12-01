# syntax = docker/dockerfile:1.3
FROM debian:bookworm-slim AS base

ARG UID
ENV UID=${UID:-9999}
ARG GID
ENV GID=${GID:-9999}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# We might be running as a user which already exists in this image. In that situation
# Everything is OK and we should just continue on.
RUN groupadd -g $GID baserow_docker_group || exit 0
RUN useradd --shell /bin/bash -u $UID -g $GID -o -c "" -m baserow_docker_user -l || exit 0
ENV DOCKER_USER=baserow_docker_user
ENV POSTGRES_VERSION=15
ENV BASEROW_IMAGE_TYPE="backend"

# hadolint ignore=DL3013
RUN apt-get update &&  \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    build-essential \
    lsb-release \
    ca-certificates \
    curl \
    gnupg2 \
    libpq-dev \
    dos2unix \
    tini \
    && \
    # Postgresql repository has to be added manually to get pre-13 versions.
    echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add - \
    && \
    apt-get update && \
    apt-get install --no-install-recommends -y \
    postgresql-client-$POSTGRES_VERSION \
    gettext \
    procps \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv\
    git \
    xmlsec1 \
    && python3 -m pip install --no-cache-dir --upgrade pip setuptools==78.1.1 --break-system-packages \
    && rm -rf /usr/lib/python3/dist-packages/setuptools* /usr/lib/python3/dist-packages/pkg_resources* \
    && apt-get autoclean \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*

# Install su-exec as a safer alternative to gosu
RUN curl -L -o /usr/local/bin/su-exec.c https://github.com/ncopa/su-exec/raw/master/su-exec.c \
    && gcc -Wall -Werror -static -o /usr/local/bin/su-exec /usr/local/bin/su-exec.c \
    && chmod 0755 /usr/local/bin/su-exec \
    && rm /usr/local/bin/su-exec.c

USER $UID:$GID

# In slim docker images, mime.types is removed and we need it for mimetypes guessing
COPY --chown=$UID:$GID ./backend/docker/mime.types /etc/

# Install non-dev base dependencies into a virtual env.
COPY --chown=$UID:$GID ./backend/requirements/base.txt /baserow/requirements/
RUN python3 -m venv /baserow/venv

ENV PIP_CACHE_DIR=/tmp/baserow_pip_cache
# hadolint ignore=SC1091,DL3042,DL3013
RUN --mount=type=cache,mode=777,target=$PIP_CACHE_DIR,uid=$UID,gid=$GID . /baserow/venv/bin/activate \
    && pip3 install --no-cache-dir --upgrade pip setuptools==78.1.1 \
    && pip3 install --no-compile -r /baserow/requirements/base.txt \
    && find /baserow/venv -type d -name "__pycache__" -prune -exec rm -rf '{}' + \
    && find /baserow/venv -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete \
    && find /baserow/venv -type f \( -name "*.c" -o -name "*.h" \) -delete

# Build a dev_deps stage which also has the dev dependencies for use by the dev layer.
FROM base AS dev_deps

COPY ./backend/requirements/dev.txt /baserow/requirements/
# hadolint ignore=SC1091,DL3042,DL3013
RUN --mount=type=cache,mode=777,target=$PIP_CACHE_DIR,uid=$UID,gid=$GID . /baserow/venv/bin/activate \
    && pip3 install --no-cache-dir --upgrade pip setuptools==78.1.1 \
    && pip3 install -r /baserow/requirements/dev.txt

# The core stage contains all of Baserows source code and sets up the entrypoint
FROM base AS core

# Copy over backend code.
COPY --chown=$UID:$GID ./docs /baserow/docs
# TODO - This copy also re-copies the requirements above, meaning this will be re-run
#        and not cached even though we already have separate layers above.
COPY --chown=$UID:$GID ./backend /baserow/backend
COPY --chown=$UID:$GID ./premium/backend /baserow/premium/backend
COPY --chown=$UID:$GID ./enterprise/backend /baserow/enterprise/backend

WORKDIR /baserow/backend

# Ensure that Python outputs everything that's printed inside
# the application rather than buffering it.
ENV PYTHONUNBUFFERED=1

COPY --chown=$UID:$GID ./deploy/plugins/*.sh /baserow/plugins/

RUN dos2unix /baserow/backend/docker/docker-entrypoint.sh && \
    chmod a+x /baserow/backend/docker/docker-entrypoint.sh && \
    /baserow/venv/bin/pip install --no-cache-dir -e /baserow/backend/ && \
    /baserow/venv/bin/pip install --no-cache-dir -e /baserow/premium/backend/ && \
    /baserow/venv/bin/pip install --no-cache-dir -e /baserow/enterprise/backend/

HEALTHCHECK --interval=60s CMD ["/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh", "backend-healthcheck"]
ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/baserow/backend/docker/docker-entrypoint.sh"]

FROM core AS dev

COPY --chown=$UID:$GID ./tests /baserow/tests/

USER root
RUN apt-get update &&  \
    apt-get install -y --no-install-recommends \
    graphviz apache2-utils \
    && apt-get autoclean \
    && apt-get clean \
    && apt-get autoremove \
    && rm -rf /var/lib/apt/lists/*
USER $UID:$GID

# Override virtualenv with one containing dev dependencies.
COPY --chown=$UID:$GID --from=dev_deps /baserow/venv /baserow/venv

# Override env variables and initial cmd to start up in dev mode.
ENV DJANGO_SETTINGS_MODULE='baserow.config.settings.dev'
CMD ["django-dev"]

FROM core AS local

ENV DJANGO_SETTINGS_MODULE='baserow.config.settings.base'
CMD ["gunicorn"]

