ARG FROM_IMAGE=baserow/baserow:1.30.1

# This is pinned as version pinning is done by the CI setting FROM_IMAGE.
# hadolint ignore=DL3006
FROM $FROM_IMAGE as image_base

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Install PostgreSQL 11 (PostgreSQL 15 is already installed in the base image)
RUN apt-get update && \
    apt-get install --no-install-recommends -y postgresql-11 postgresql-client-11 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

COPY --chown=$UID:$GID deploy/all-in-one/pgautoupgrade/docker-postgres-upgrade.sh /docker-postgres-upgrade.sh

ENV POSTGRES_OLD_VERSION=11
ENV POSTGRES_OLD_LOCATION=/etc/postgresql/11/main
ENV POSTGRES_OLD_BIN_FOLDER=/usr/lib/postgresql/11/bin

ENV POSTGRES_VERSION=15
ENV POSTGRES_LOCATION=/etc/postgresql/15/main
ENV POSTGRES_BIN_FOLDER=/usr/lib/postgresql/15/bin

ENV POSTGRES_SETUP_SCRIPT_COMMAND=upgrade
