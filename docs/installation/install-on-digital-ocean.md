# Installation on Digital Ocean Apps

This guide will walk you through deploying on the Digital Ocean Apps platform. It's a
step-by-step guide that helps you install Baserow from scratch in a scalable way.

## Create managed database

The app platform doesn't support volumes, and offers horizontal scalability. That means
the application that runs will be stateless. We will therefore need to create a managed
PostgreSQL, managed Redis, and a Spaces Object Storage to store all the data. Because
the app depends on these resources to exist, we have to create those first.

### Managed PostgreSQL

Navigate to the `Databases` page in the left sidebar of your Digital Ocean dashboard.
Click on `Create Database` in the top right corner. Choose your region, it's important
that all the created servers are in the same region, select PostgreSQL v15, and choose
the server specs you would like to have. Baserow is compatible with 1vCPU and 1GB
RAM.

While the database server is being created, you can already find the `Connection
Details` on the database detail page. Click on the dropdown in that top right corner,
and switch to `Connection String`. Copy that string because you're going to need it
later.

### Managed Redis

Navigate to the `Databases` page in the left sidebar of your Digital Ocean dashboard.
Click on `Create Database` in the top right corner. Choose your region, it's important
that all the created servers are in the same region, select Redis v7, and choose the
server specs you would like to have. Baserow is compatible with 1vCPU and 1GB RAM.

While the database server is being created, you can already find the `Connection
Details` on the database detail page. Click on the dropdown in that top right corner,
and switch to `Connection String`. Copy that string because you're going to need it
later.

### Spaces Object Storage

Navigate to the `Spaces Object Storage` page in the left sidebar of your Digital Ocean
dashboard. Click on `Create Spaces Bucket`. Choose your region, it's important
that the bucket is created the same region, and create the bucket.

Navigate to the `API` page in the left sidebar of the sidebar, click on the `Spaces
Keys` tab, click on `Generate New Key`, and create a new key. Copy the `Access Key` and
`Secret key` because your going to need that later.

## Application

Navigate to the `Apps` page in the left sidebar of your Digital Ocean dashboard. Click
on `Create App`, select `Docker Hub`, and fill out the following:

Repository: `baserow/baserow`
Image tag or digest: `2.0.6`

Click on `Next`, then on the `Edit` button of the `baserow-baserow` web service. Here
you must change the HTTP Port to 80, and then click on `Back`. Click on the `Next`
button, and then on `Edit` next to the `baserow-baserow` environment variables. Add the
following environment variables. Everything between brackets must be replaced.

Generate a unique secret string for `SECRET_KEY` and `BASEROW_JWT_SIGNING_KEY`. This
can for example be done via https://djecrety.ir/.

```
SECRET_KEY=(generate a unique random string)
BASEROW_JWT_SIGNING_KEY=(generate a unique random string)
BASEROW_PUBLIC_URL=http://localhost
BASEROW_AMOUNT_OF_GUNICORN_WORKERS=2
BASEROW_AMOUNT_OF_WORKERS=2
DATABASE_URL=(YOUR_POSTGRESQL_CONNECTION_STRING)
REDIS_URL=(YOUR_REDIS_CONNECTION_STRING)
DISABLE_VOLUME_CHECK=yes
BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION=false

AWS_ACCESS_KEY_ID=(Spaces Access Key)
AWS_SECRET_ACCESS_KEY=(Spaces Secret key)
AWS_STORAGE_BUCKET_NAME=(Space name)
AWS_S3_REGION_NAME=(Spaces region e.g. ams3)
AWS_S3_ENDPOINT_URL=https://(region).(digitaloceanspaces.com)
AWS_S3_CUSTOM_DOMAIN=(name-of-your-space).(region).(digitaloceanspaces.com)
DOWNLOAD_FILE_VIA_XHR=1
```

Don't forget to click on the `Save` button, and then on `Next` and again on `Next` until
you're at the `Review` section. Scroll all the way down, and click on `Edit Plan`. Here
you can choose the instance size. You need 1 vCPU and 2 GB RAM 1 container at minimum.
You can scale up later. Click on `Back` and then on `Create Resources`.

## Security

To make your PostgreSQL and Redis servers secure, navigate to their detail pages, click
`Settings`, click on `Edit` at `Trusted Sources`, and add the newly created app.

## Change domain

Navigate back to the `Settings` of the newly created App, and wait until the deployment
completes. After, it will automatically add a domain/URL for you, and it will become
visible in the settings. Copy this URL, click on the baserow-baserow component settings,
edit the environment variables and set `BASEROW_PUBLIC_URL` to `(the copied URL)`, then
hit the save button. Note that the URL does not have a trailing slask, so it should
look like `https://baserow.io` and not `https://baserow.io/`.

## Templates

The templates are not installed because it will result in an `out of shared memory` on
the cheapest managed database plan. If you wish to enable it, then you must set the
environment variable `BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION` to `true`.

### Spaces

In order for the download button to work in Baserow you would need to configure the CORS
settings in spaces. Navigate to the created space, go to the `Settings` tab, click on
`Add` next to the CORS  Configurations, and add the URL of the newly created
application without a trailing slash, so it must not end with a `/`. Select the `GET`,
`HEAD` and `OPTIONS` method, and click `Save CORS Configuration`.

## Finish

Wait until the build restarts, and then visit the copied URL to make use of your Baserow
environment.

## Update version

In order to update the Baserow version, you simply need to replace the image tag.
Navigate to the `Settings` tag of your created app, click on the `baserow-baserow`
component, then click on the `Edit` button next to source, change the `Image tag` into
the desired version (latest is `2.0.6`), and click on save. The app will redeploy
with the latest version.

## External email server

You can enable email by adding the following environment variables:

```
EMAIL_SMTP=True
EMAIL_SMTP_HOST=
EMAIL_SMTP_PORT=
EMAIL_SMTP_USER=
EMAIL_SMTP_PASSWORD=
EMAIL_SMTP_USE_TLS=
```

## Application builder domains

Baserow has an application builder that allows to deploy an application to a specific
domain. Because Digital Ocean has a reverse proxy that routes a domain to the right
app, the deployed application isn't automatically available on the chosen domain.

To make this work you must navigate to the App `Settings`, and click on `Edit` next to
the domain. Here you can add additional domains that will be routed to your published
application builder domain.

## Scaling

### Containers

If you're going to use Baserow with more concurrent users, have big database schemas,
need more API requests per second, then you're going to run into limitations with
the current setup, and you need to scale up.

With the existing environment variables, you can easily scale the number of containers
if they have 1vCPU and 2GB of ram.

If you decide to increase the instance size, then you must also change some environment
variables to make the most use of it.

- 4GB of RAM:
    - `BASEROW_AMOUNT_OF_GUNICORN_WORKERS=5`
    - `BASEROW_AMOUNT_OF_WORKERS=4`
- 8GB of RAM:
    - `BASEROW_AMOUNT_OF_GUNICORN_WORKERS=10`
    - `BASEROW_AMOUNT_OF_WORKERS=8`
- 16GB of RAM:
    - `BASEROW_AMOUNT_OF_GUNICORN_WORKERS=20`
    - `BASEROW_AMOUNT_OF_WORKERS=16`

Every `gunicorn workers * the number instances` is the number of concurrent API requests
your setup can handle.

### PostgreSQL and Redis

If you're going to increase the containers or gunicorn workers, you must make sure that
your PostgreSQL and Redis servers can handle that many requests. The rule of thumb is
roughly:

```
number of connections needed =
    (
        (BASEROW_AMOUNT_OF_GUNICORN_WORKERS * 2)
        + (BASEROW_AMOUNT_OF_WORKERS * 2)
    ) * number of containers
    + service connections
```

So if you have 2 containers of 8GB of ram, you would need at least:
`((10 * 2) + (8 * 2)) * 2 + 5 = 77 connections`.
