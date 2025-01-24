ARG FROM_IMAGE=baserow/baserow:1.30.1

# This is pinned as version pinning is done by the CI setting FROM_IMAGE.
# hadolint ignore=DL3006
FROM $FROM_IMAGE as image_base

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Remove PostgreSQL 15 (which is already installed in the base image)
# and add the PostgreSQL 11 repository and install PostgreSQL 11
RUN DEBIAN_FRONTEND=noninteractive apt-get remove -y --purge postgresql-15 postgresql-client-15 || true && \
    apt-get autoremove -y && \
    apt-get update && \
    apt-get install --no-install-recommends -y postgresql-11 postgresql-client-11 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV POSTGRES_VERSION=11
ENV POSTGRES_LOCATION=/etc/postgresql/11/main
