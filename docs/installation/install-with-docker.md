# Install with Docker

> Any questions, problems or suggestions with this guide? Ask a question in our
> [community](https://community.baserow.io/) or contribute the change yourself at
> https://github.com/baserow/baserow/tree/develop/docs .

> Docker version 19.03 is the minimum required to use Baserow. It is strongly
> advised however that you install the latest version of Docker available.
> Please check that your docker is up-to date by running `docker -v`.

This guide assumes you already have Docker installed and have permissions to run Docker
containers. See the [Install on Ubuntu](install-on-ubuntu.md) for an installation from
scratch.

[comment]: <> (All content from here must be kept in sync with `deploy/all-in-one/README.md`)

## Quick Start

Run the command below to start a Baserow server running locally listening on port `80`.
You will only be able to connect to Baserow from the machine running the server via
`http://localhost`.

```bash
docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=http://localhost \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  -p 443:443 \
  --restart unless-stopped \
  baserow/baserow:2.0.6
```

* Change `BASEROW_PUBLIC_URL` to `https://YOUR_DOMAIN` or `http://YOUR_IP` to enable
  external access. Ensure that this address matches the one you enter in your browser's
  URL bar. Any different address will be considered a published application.
* Add `-e BASEROW_CADDY_ADDRESSES=:443` to enable
  [automatic Caddy HTTPS](https://caddyserver.com/docs/automatic-https).
* Optionally add `-e DATABASE_URL=postgresql://user:pwd@host:port/db` to use an external
  Postgresql.
* Optionally add `-e REDIS_URL=redis://user:pwd@host:port` to use an external Redis.

> There is a security flaw with docker and the ufw firewall.
> By default docker when exposing ports on 0.0.0.0 will bypass any ufw firewall rules
> and expose the above container publicly from your machine on its network. If this
> is not intended then run with the following ports instead:
> `-p 127.0.0.1:80:80 -p 127.0.0.1:443:443` which makes your Baserow only accessible
> from the machine it is running on.
> Please see https://github.com/chaifeng/ufw-docker for more information and how to
> setup ufw to work securely with docker.

## Image Feature Overview

The `baserow/baserow:2.0.6` image by default runs all of Baserow's various services in
a single container for maximum ease of use.

> This image is designed for simple single server deployments or simple container
> deployment services such as Google Cloud Run.
>
> If you are instead looking for images which are better suited for horizontal
> scaling (e.g. when using [K8S](./install-with-k8s.md)) then please instead use our
> [baserow/backend and baserow/web-frontend](./install-with-docker-compose.md) images
> instead which deploy each Baserow service in its own container independently.

A quick summary of its features are:

* Runs a Postgres database and Redis server by default internally and stores all data in
  the `/baserow/data` folder inside the container.
* Set `DATABASE_URL` or the `DATABASE_...` variables to disable the internal postgres
  and instead connect to an external Postgres. This is highly recommended for any
  production deployments of this image, so you can easily connect to the Postgres
  database from any other services or processes you might have.
* Set `REDIS_URL` or the `REDIS_...` variables to disable the internal redis and instead
  connect to an external Postgres.
* Runs all services behind a pre-configured Caddy reverse proxy. Set
  `BASEROW_CADDY_ADDRESSES` to `https://YOUR_DOMAIN.com` and it will
  [automatically enable https](https://caddyserver.com/docs/automatic-https#overview)
  for
  you and store the keys and certs in `/baserow/data/caddy`.
* Provides a CLI for execing admin commands against a running Baserow container or
  running one off commands against just a Baserow data volume.

## Upgrading from a previous version

1. It is recommended that you backup your data before upgrading, see the Backup sections
   below for more details on how to do this.
2. Stop your existing Baserow container:

```bash
docker stop baserow
```

3. Bump the image version in the `docker run` command you usually use to run your
   Baserow and start up a brand-new container:

```bash
# We haven't yet deleted the old Baserow container so you need to start this new one
# with a different name to prevent an error like:
# `response from daemon: Conflict. The container name "/baserow" is already in use by
# container`

docker run \
  -d \
  --name baserow_version_REPLACE_WITH_NEW_VERSION \
  # YOUR STANDARD ARGS HERE
  baserow/baserow:REPLACE_WITH_LATEST_VERSION
```

5. Baserow will automatically upgrade itself on startup, follow the logs to monitor it:

```bash
docker logs -f baserow_version_REPLACE_WITH_NEW_VERSION
```

6. Once you see the following log line your Baserow upgraded and is now available again:

```
[BASEROW-WATCHER][2022-05-10 08:44:46] Baserow is now available at ...
```

7. Make sure your Baserow has been successfully upgraded by visiting it and checking
   everything is working as expected and your data is still present.
8. If everything works you can now remove the old Baserow container.

> WARNING: If you have not been using a volume to persist the `/baserow/data` folder
> inside the container this will delete all of your Baserow data stored in this
> container permanently.

```bash
docker rm baserow
```

## Upgrading PostgreSQL database from a previous version

On November 2023 [PostgreSQL released](https://www.postgresql.org/about/news/postgresql-161-155-1410-1313-1217-and-1122-released-2749/) a final update for version 11 of the database together with an end-of-life notice for this version. This means, that PostgreSQL 11 will no longer receive security and bug fixes.

If you are using an embedded PostgreSQL database (an embedded one is when you do _not_ provide `POSTGRESQL_*` environment variables when launching Baserow, as opposed to an external one, where you provide connection details to your external PostgreSQL instance), and if you restart or try to run a new Baserow instance, if your data was initialized with PostgreSQL version 11, you'll notice that it doesn't start up anymore and raises an error because you need to upgrade your data directory to be compatible with PostgreSQL version 15. Baserow provides an image to automatically upgrade your data directory to PostgreSQL version 15, which is now the version officially supported by Baserow.

If you don't want to upgrade at this point in time, jump to [Legacy PostgreSQL version](#legacy-postgresql-version) section below. Although, be aware, that we will only support PostgreSQL 11 for a limited amount of time and that this version won't receive official updates from PostgreSQL anymore.

### Upgrade process

To upgrade your data directory to be compatible with PostgreSQL 15, follow these steps:

**CAUTION:** before doing this, make sure to [Back up your Baserow instance](#backing-up-and-restoring-baserow) to avoid potential data loss.

1. Make sure there are no Baserow instances running with `docker ps`. If Baserow is running, stop the container with `docker stop baserow`.
2. Run this command to run a Docker image which will automatically update your data directory to be compatible with PostgreSQL version 15:

```
docker run \
  --name baserow-pgautoupgrade \
  # ALL THE ARGUMENTS YOU NORMALLY ADD TO YOUR BASEROW INSTANCE
  --restart no \
  baserow/baserow-pgautoupgrade:1.30.1
```

3. If the upgrade was successful, the container should exit with a success message, you can now start Baserow as you did before.
4. If the upgrade wasn't successful, the upgrade image should output verbose logs of where exactly it failed. In that case, copy all of the log output and refer to [Baserow community](https://community.baserow.io/) or contact us for further assistance.

### Legacy PostgreSQL version

Starting from January 1, 2025, we will no longer create new images with PostgreSQL 11. If you are using the embedded PostgreSQL version in a Baserow version before 1.30 and want to upgrade to the latest version, you must first use the latest `pgautoupgrade` image to upgrade PostgreSQL to version 15, and then upgrade to the latest version of Baserow. If you do not wish to upgrade PostgreSQL, version 1.30.1 is the last image we provide with PostgreSQL 11, but it will not receive any updates.

To run the latest Baserow image that uses the legacy PostgreSQL 11 version, use the following command:

```
docker run \
  --name baserow-pg11 \
  # ALL THE ARGUMENTS YOU NORMALLY ADD TO YOUR BASEROW INSTANCE
  --restart unless-stopped \
  baserow/baserow-pg11:1.30.1
```

## Example Commands

See [Configuring Baserow](configuration.md) for more detailed information on all the
other environment variables you can configure.

### Using a Domain with automatic https

If you have a domain name and have correctly configured DNS then you can run the
following command to make Baserow available at the domain with
[automatic https](https://caddyserver.com/docs/automatic-https#overview) provided by
Caddy.

> Append `,http://localhost` to BASEROW_CADDY_ADDRESSES if you still want to be able to
> access your server from the machine it is running on using http://localhost. See
> [Caddy's Address Docs](https://caddyserver.com/docs/caddyfile/concepts#addresses)
> for all supported values for BASEROW_CADDY_ADDRESSES.

```bash
docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=https://www.REPLACE_WITH_YOUR_DOMAIN.com \
  -e BASEROW_CADDY_ADDRESSES=:443 \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  -p 443:443 \
  --restart unless-stopped \
  baserow/baserow:2.0.6
```

### Behind a reverse proxy already handling ssl

```bash
docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=https://www.yourdomain.com \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  --restart unless-stopped \
  baserow/baserow:2.0.6
```

### On a nonstandard HTTP port

```bash
docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=https://www.yourdomain.com:3001 \
  -v baserow_data:/baserow/data \
  -p 3001:80 \
  --restart unless-stopped \
  baserow/baserow:2.0.6
```

### With an external PostgresSQL server

```bash
docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=https://www.yourdomain.com \
  -e DATABASE_HOST=TODO \
  -e DATABASE_NAME=TODO \
  -e DATABASE_USER=TODO \
  -e DATABASE_PASSWORD=TODO \
  -e DATABASE_PORT=TODO \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  -p 443:443 \
  --restart unless-stopped \
  baserow/baserow:2.0.6
```

### With an external Redis server

```bash
docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=https://www.yourdomain.com \
  -e REDIS_HOST=TODO \
  -e REDIS_USER=TODO \
  -e REDIS_PASSWORD=TODO \
  -e REDIS_PORT=TODO \
  -e REDIS_PROTOCOL=TODO \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  -p 443:443 \
  --restart unless-stopped \
  baserow/baserow:2.0.6
```

### With an external email server

```bash
docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=https://www.yourdomain.com \
  -e EMAIL_SMTP=True \
  -e EMAIL_SMTP_HOST=TODO \
  -e EMAIL_SMTP_PORT=TODO \
  -e EMAIL_SMTP_USER=TODO \
  -e EMAIL_SMTP_PASSWORD=TODO \
  -e EMAIL_SMTP_USE_TLS= \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  -p 443:443 \
  --restart unless-stopped \
  baserow/baserow:2.0.6
```

### With a Postgresql server running on the same host as the Baserow docker container

This is assuming you are using the postgresql server bundled by ubuntu. If not then you
will have to find the correct locations for the config files for your OS.

1. Find out what version of postgresql is installed by running
   `sudo ls /etc/postgresql/`
2. Open `/etc/postgresql/YOUR_PSQL_VERSION/main/postgresql.conf` for editing as root
3. Find the commented out `# listen_addresses` line.
4. Change it to be:
   `listen_addresses = '*'          # what IP address(es) to listen on;`
5. Open `/etc/postgresql/YOUR_PSQL_VERSION/main/pg_hba.conf` for editing as root
6. Add the following line to the end which will allow docker containers to connect.
   `host    all             all             172.17.0.0/16           md5`
7. Restart postgres to load in the config changes.
   `sudo systemctl restart postgresql`
8. Check the logs do not have errors by running
   `sudo less /var/log/postgresql/postgresql-YOUR_PSQL_VERSION-main.log`
9. Run Baserow like so:

```bash
docker run \
  -d \
  --name baserow \
  --add-host host.docker.internal:host-gateway \
  -e BASEROW_PUBLIC_URL=http://localhost \
  -e DATABASE_HOST=host.docker.internal \
  -e DATABASE_PORT=5432 \
  -e DATABASE_NAME=YOUR_DATABASE_NAME \
  -e DATABASE_USER=YOUR_DATABASE_USERNAME \
  -e DATABASE_PASSWORD=REPLACE_WITH_YOUR_DATABASE_PASSWORD \
  --restart unless-stopped \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  -p 443:443 \
  baserow/baserow:2.0.6
```

### Supply secrets using files

The `DATABASE_PASSWORD`, `SECRET_KEY` and `REDIS_PASSWORD` environment variables can
instead be loaded using a file by using the `*_FILE` variants:

```bash
echo "your_redis_password" > .your_redis_password
echo "your_secret_key" > .your_secret_key
echo "your_pg_password" > .your_pg_password
docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=http://localhost \
  -e REDIS_PASSWORD_FILE=/baserow/.your_redis_password \
  -e SECRET_KEY_FILE=/baserow/.your_secret_key \
  -e DATABASE_PASSWORD_FILE=/baserow/.your_pg_password \
  -e EMAIL_SMTP_PASSWORD_FILE=/baserow/.your_smtp_password \
  --restart unless-stopped \
  -v $PWD/.your_redis_password:/baserow/.your_redis_password \
  -v $PWD/.your_secret_key:/baserow/.your_secret_key \
  -v $PWD/.your_pg_password:/baserow/.your_pg_password \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  -p 443:443 \
  baserow/baserow:2.0.6
```

### Start just the embedded database

If you want to directly access the embedded Postgresql database then you can run:

```bash
docker run -it \
  --rm \
  --name baserow \
  -p 5432:5432 \
  -v baserow_data:/baserow/data \
  baserow/baserow:2.0.6 \
  start-only-db
# Now get the password from
docker exec -it baserow cat /baserow/data/.pgpass
# Finally connect on your host machine to the Baserow postgres database at port 5432
# the password above with the username `baserow`.
```

## Application builder domains

The build in Caddy server is configured to automatically handle additional application
builder domains. Depending on the environment variables, it will also automatically
fetch SSL certificates for those domains. Note that the `BASEROW_CADDY_ADDRESSES`
environment variable must be `:80` or `:443` to allow multiple domains. If you have set
a URL there, it won't work.

By default, it will accept requests of any domain over the http protocol, which is
perfect if you have a proxy in front of Baserow. If `BASEROW_CADDY_ADDRESSES` starts
with `https` protocol or is `:443`, then it will redirect http requests to https, and
will handle the SSL certificate part automatically. This is recommended when the
container is directly exposed to the internet.

### Run a one off command on the database

If you want to run a one off backend command against your Baserow data volume without
starting Baserow normally you can do so with the `backend-cmd-with-db` argument like so:

```bash
docker run -it \
  --rm \
  --name baserow \
  -v baserow_data:/baserow/data \
  baserow/baserow:2.0.6 \
  backend-cmd-with-db manage dbshell
```

## Stateless Deployment for Horizontal Scaling

This image can also be configured to deploy Baserow in a horizontally scalable way.
We recommend you first consider using our `baserow/backend` and `baserow/web-frontend`
single service per container images
on [K8S](./install-with-k8s.md)/[Helm](install-with-helm.md).
However, if you just want to easily horizontally scale Baserow on something like
AWS ECS or Google Cloud Run then the `baserow/baserow` can be used.

### Prerequisites

To deploy this image in a horizontally scalable way you need to ensure all state is
stored externally and not inside containers or volumes. To do this you will need a:

1. [A PostgreSQL Database](./supported.md)
2. [A Redis](./supported.md)
3. One of the following services to upload and download user files from:
    1. AWS S3 or compatable service
    2. Google Cloud Storage
    3. Azure Cloud Storage bucket
    4. Some sort of a shared volume that can be mounted into every single container

### Recommended Environment Variables

With this image we recommend you set the following environment variables to scale it
horizontally.

> See our [Configuration Docs](https://baserow.io/docs/installation%2Fconfiguration) for
> more details on the following environment variables.

1. All relevant `DATABASE_*` env vars need to be set to point Baserow at an external
   postgres
2. All relevant `REDIS_*` env vars need to be set to point Baserow at an external redis
3. `DISABLE_VOLUME_CHECK=yes` needs to be set as this image has a
   check for less technical users that `/baserow/data` is mounted to an external
   volume on startup. Instead, you want your containers to be stateless and so this
   check needs to be disabled.
4. `AWS_*/GC_*/AZURE_*` env vars need to be set connecting Baserow to an external
   file storage service.
    1. **Important** The URLs of files uploaded to these buckets needs to be accessible
       directly from browser of your Baserow users.
5. Ensure the containers always have CPU time allocated as they have periodic
   background tasks triggered by an internal CRON service.

### Scaling Options

This image has the following "horizontal scaling" environment variables:

1. `BASEROW_AMOUNT_OF_GUNICORN_WORKERS` this controls the number of REST API
   workers (the things that do most of the API work) per container.
2. `BASEROW_AMOUNT_OF_WORKERS` controls the number of background task celery
   runners, these run realtime collaboration tasks, cleanup jobs and other slow tasks
   like big file exports/imports.
    1. If you are scaling many of these containers you probably only need one or two
       of these background workers per container as they will all pool together and
       collect background tasks submitted from any other container via Redis.
3. You can make the image launch fewer internal processes and hence reduce memory usage
   by setting `BASEROW_RUN_MINIMAL=yes` AND `BASEROW_AMOUNT_OF_WORKERS=1`.
    1. This will cause this image to only launch a single celery task
       process which handles both the fast and slow queues. The consequence of this is
       that there is only one process handling tasks per container and so a slow task
       such as a snapshot of a large Baserow database might delay a fast queue task
       like sending a realtime row updated signal to all users looking at a table.

## Backing up and Restoring Baserow

Baserow stores all of its persistent data in the `/baserow/data` directory by default.
We strongly recommend you mount a docker volume into this location to persist Baserows
data so you do not lose it if you accidentally delete your Baserow container.

> The backup and restore operations discussed below are best done on a Baserow server
> which is not being used.

### Backup all of Baserow

Note, that this only works if you're not using an external PostgreSQL server. This will backup:

1. Baserows postgres database (This will be a raw copy of the PGDATA dir and hence not
   easily portable, see the section below on how to backup just the postgres db in a
   more portable way.)
2. The Caddy config and data, this will include any runtime config changes you might
   have made to the caddy server and any SSL certificates/keys automatically setup by
   Caddy.
3. The Redis servers state. This is not strictly needed.
4. This will backup user-uploaded files as well, but only if you've not configured external file storage.

Otherwise if you remove the Baserow container you will lose all of your data.

The command below assumes you have been running Baserow with the
`-v baserow_data:/baserow/data` volume. Please change this argument accordingly if you
have mounted the /baserow/data folder differently.

```bash
# Ensure Baserow is stopped first before taking a backup.
docker stop baserow
docker run --rm -v baserow_data:/baserow/data -v $PWD:/backup ubuntu tar cvf /backup/backup.tar /baserow/data
```

### Restore all of Baserow

```bash
# Ensure Baserow is stopped first before taking a backup.
docker stop baserow
docker run --rm -v baserow_data:/baserow/data -v $PWD:/backup ubuntu tar cvf /backup/backup.tar /baserow/data
docker run --rm -v new_baserow_data_volume:/results -v $PWD:/backup ubuntu bash -c "mkdir -p /results/ && cd /results && tar xvf /backup/backup.tar --strip 2"
# Now launch Baserow using the new data volume with your normal run command:
docker run -v new_baserow_data_volume:/baserow/data .....
```

### Backup only Baserow's Postgres database

Please ensure you only back-up a Baserow database which is not actively being used by a
running Baserow instance or any other process which is making changes to the database.

Baserow stores all of its own data in Postgres. To backup just this database you can run
the command below.

```bash
# First read the help message for this command
docker run -it --rm -v baserow_data:/baserow/data baserow/baserow:2.0.6 \
   backend-cmd-with-db backup --help

# Stop Baserow instance
docker stop baserow

# The command below backs up Baserow to the backups folder in the baserow_data volume:
docker run -it --rm -v baserow_data:/baserow/data baserow/baserow:2.0.6 \
   backend-cmd-with-db backup -f /baserow/data/backups/backup.tar.gz

# Or backup to a file on your host instead run something like:
docker run -it --rm -v baserow_data:/baserow/data -v $PWD:/baserow/host \
   baserow/baserow:2.0.6 backend-cmd-with-db backup -f /baserow/host/backup.tar.gz
```

### Restore only Baserow's Postgres Database

When restoring Baserow you must ensure you are restoring into a brand new Baserow data
volume.

```bash
# Stop Baserow instance
docker stop baserow

# Restore Baserow backup from a new volume containing the backup:
docker run -it --rm \
  -v old_baserow_data_volume_containing_the_backup_tar_gz:/baserow/old_data \
  -v new_baserow_data_volume_to_restore_into:/baserow/data \
  baserow/baserow:2.0.6 backend-cmd-with-db restore -f /baserow/old_data/backup.tar.gz

# Or to restore from a file on your host instead run something like:
docker run -it --rm \
  -v baserow_data:/baserow/data -v \
  $(pwd):/baserow/host \
  baserow/baserow:2.0.6 backend-cmd-with-db restore -f /baserow/host/backup.tar.gz
```

## Running healthchecks on Baserow

The Dockerfile already defines a HEALTHCHECK command which will be used by software that
supports it. However if you wish to trigger a healthcheck yourself on a running Baserow
container then you can run:

```bash
docker exec baserow ./baserow.sh backend-cmd backend-healthcheck
# Run the below to see all available healthchecks
docker exec baserow ./baserow.sh backend-cmd help
```

## Running Baserow or Django management commands

You can run management commands on an existing Baserow container called baserow by
running the following to see the available commands:

```bash
docker exec baserow ./baserow.sh backend-cmd manage
# For example you could migrate the database of a running Baserow using:
docker exec baserow ./baserow.sh backend-cmd manage migrate
```

## Customizing Baserow

### Mounting in a config file

Baserow will automatically source any `.sh` files found in `/baserow/supervisor/env/` or
`/baserow/data/env/` on startup. Use this to create a single config file to configure
your Baserow like so:

```bash
custom_baserow_conf.sh << EOF
export BASEROW_PUBLIC_URL=todo
export BASEROW_CADDY_ADDRESSES=todo

# You can perform any Bash logic required in here to setup Baserow conditionally.
EOF

docker run \
  -d \
  --name baserow \
  -e BASEROW_PUBLIC_URL=http://localhost \
  -v $PWD/custom_baserow_conf.sh /baserow/supervisor/custom_baserow_conf.sh \
  -v baserow_data:/baserow/data \
  -p 80:80 \
  -p 443:443 \
  --restart unless-stopped \
  baserow/baserow:2.0.6
```

Or you can just store it directly in the volume at `baserow_data/env` meaning it will be
loaded whenever you mount in this data volume.

### Building your own image from Baserow

```dockerfile
FROM baserow/baserow:2.0.6

# Any .sh files found in /baserow/supervisor/env/ will be sourced and loaded at startup
# useful for storing your own environment variable overrides.
COPY custom_env.sh /baserow/supervisor/env/custom_env.sh

# Set the DATA_DIR environment variable to change where Baserow stores its persistent
# data. At startup Baserow will attempt to chown and setup this folder correctly.
ENV DATA_DIR=/baserow/data

# This image bakes in its own default user with UID/GID of 9999:9999 by default. To
# Set this to change the user Baserow will run its Caddy, backend, Celery and
# web-frontend services as. However be warned, the default entrypoint needs to be run
# as root so using USER may break things.
ENV DOCKER_USER=baserow_docker_user
```
