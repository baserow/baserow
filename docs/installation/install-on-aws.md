# Install on AWS

This guide will walk you through picking the best way to deploy Baserow to AWS, what
pre-requisites you will need to set up and also provide specific installation
instructions. This guide is for those who already have experience and
knowledge of deploying applications to AWS.

## Overview of deployment options

Baserow can be deployed to AWS in the following ways:

1. Deploying the [all-in-one image](./install-with-docker.md) to Fargate/ECS for a
   horizontally scalable but easy to
   set up deployment. **See below for a detailed guide.**
2. Using
   this [docker-compose](https://github.com/baserow/baserow/blob/develop/docker-compose.no-caddy.yml)
   file or our [sample K8S configuration](./install-with-k8s.md) as a starting point to
   configure ECS/Fargate tasks for more advanced, production ready, one service per
   container model. **See below for a detailed guide**
3. Using the [Official Baserow helm chart](./install-with-helm.md) and EKS.
4. Customizing our [sample K8S configuration](./install-with-k8s.md) and using that with
   EKS.
5. Installing and using docker/docker-compose on an EC2 instance with
   our [all-in-one](./install-with-docker.md) or
   our [one container per service](./install-with-docker-compose.md) docker images.

All of these deployment methods will store Baserow's data and state in RDS and S3 making
switching between them (for example migrating to using EKS later on)
straightforward.

## Prerequisites for deploying Baserow to AWS

We will go through these in more detail later in the guide but to give you a quick
overview this is what any AWS deployment of Baserow will need:

* An AWS IAM account with sufficient privileges to create AWS resources* A Postgres
  database (RDS)
* A S3 bucket for storing user uploaded files and user triggered exports
  of tables.
* An AWS IAM account with privileges to upload to the S3 bucket.
    * Specifically their AWS Access Key ID and Secret Access Key will be needed to
      configure Baserow to upload into the bucket.
    * A VPC
    * A non-clustered Redis
      server (Elasticache with TLS on and cluster mode off)
    *
        * A SMTP email server for
          Baserow to send emails with.

## Option 1) Deploying the all-in-one image to Fargate/ECS

The `baserow/baserow:2.0.6` image runs all of Baserow’s various services inside the
container for ease of use.

This image is designed for single server deployments or simple deployments to
horizontally scalable container deployment platforms such as AWS Fargate or Google Cloud
Run.

### Why choose this method

#### Pros

* Can be easily horizontally scaled with enough control for most production setups by
  just increasing the container count.
* Simpler to use and setup compared to the one container per-service model below
  because:
    * You don't need to worry about configuring and linking together the different
      services that make up a Baserow deployment.
    * Configuring load balancers is easier as you can just directly route through all
      requests to any horizontally scaled container running `baserow/baserow:2.0.6`.

#### Cons

* Doesn't follow the traditional one container per task/service model.
* Potentially higher resource usage overall as each of the all-in-one containers will
  come with its internal services, so you have less granular control over scaling
  specific services.
    * For example if you deploy 10 `baserow/baserow:2.0.6` containers horizontally you
      by default end up with:
        * 10 web-frontend services
        * 10 backend services
        * 10 backend fast async task workers
        * 10 backend slow async task workers
    * You can use environment variables to configure this somewhat.
* Harder to isolate failures specific to certain services as the logs per container will
  include multiple services.
    * However, Baserow fully
      supports [Open Telemetry](./monitoring.md) which lets you hook Baserow up to many
      cloud application monitoring solutions like Honeycomb, Datadog, NewRelic or a
      Grafana/Loki/Tempo/Prometheus stack.

### Installation steps

We will be skipping over configuring VPCs, security groups, IAM users, secrets manager
etc and ELB specifics to keep this guide more generally applicable.

#### 1) Provision an S3 bucket for user file uploads

First Baserow needs an S3 bucket. Baserow will use this bucket to store files uploaded
by users into tables and view/table exports for users to then download.

Baserow will then generate pre-signed S3 URLs for the user to view and download files
from this bucket. As a result, these pre-signed URLs need to be accessible from the
user's browser and so depending on your setup most likely the bucket to allow public
GET/ACLs.

We recommend setting up a separate IAM user who Baserow will be configured with
credentials for, so it can upload into and delete from the bucket. Here is an example S3
policy for this
user to grant the minimal required operations:

```terraform
policy = <<EOF
{
    "Version": "2012-10-17",
    "Statement": [{
        "Effect": "Allow",
        "Action": [
                "s3:PutObject",
                "s3:GetObjectAcl",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:PutObjectAcl"
            ],
             "Principal": {
                "AWS": "arn:aws:iam::xyz:user/YOUR_USER"
             },
        "Resource": [
            "arn:aws:s3:::YOUR_BUCKET_NAME/*",
            "arn:aws:s3:::YOUR_BUCKET_NAME"
        ]
    }]
}
```

This bucket will also in the current version of Baserow need CORS rules set for the
in-tool file download button to work correctly. An example rule is provided below:

```
cors_rule {
allowed_headers = ["*"]
allowed_methods = ["GET", "HEAD", "OPTIONS"]
allowed_origins = ["REPLACE_WITH_YOUR_BASEROW_PUBLIC_URL"]
expose_headers  = ["ETag", "Content-Length", "Content-Type"]
max_age_seconds = 3000
}
```

Finally, these are the following public access settings we used to ensure the users
browser can GET and download the S3 files:

```
 block_public_acls       = false
 block_public_policy     = true
 ignore_public_acls      = true
 restrict_public_buckets = true
```

#### 2) Provisioning a Postgres using RDS

Baserow stores all of its non-file data in a PostgreSQL database. In AWS we recommend
using an RDS Postgres cluster. You will later need to configure Baserow to be able to
access this cluster.

Baserow uses PostgreSQL heavily so scaling the RDS cluster up will be needed for larger
deployments.

> You should not put an RDS Proxy in front of the RDS instance. This is because the
> proxy causes a transaction to end after a definition language (DDL) statement
> completes. Baserow is therefore incompatible because it makes schema changes, and if
> anything goes wrong the after a schema migration, the transaction isn't rolled back,
> and results in data inconsistencies. More information:
> https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-proxy.howitworks.html#rds-proxy-transactions

#### 3) Provisioning a Redis using Elasticache

Baserow uses Redis as a cache, for real-time collaboration over WebSockets and async
background task processing.

We recommend setting up an Elasticache Redis in non-cluster mode with TLS enabled and in
AUTH mode where you can specify an AUTH token password for Baserow to later connect to
the Redis server.

Generally, the Redis server is not the bottleneck in Baserow deployments as they scale.

#### 4) Setting up an ALB and target group

Now create a target group on port 80 and ALB ready to route traffic to the Baserow
containers.

When setting up the health check for the ALB the `baserow/baserow:2.0.6` container
,which you'll be deploying next, choose port `80` and health check
URL `/api/_health/`. We recommend a long grace period of 900 seconds to account for
first-time migrations being run on the first container's startup.

#### 5) Launching Baserow on ECS/Fargate

Now we are ready to spin up our `baserow/baserow:2.0.6` containers. See below for a
full task definition and environment variables. We recommend launching the containers
with 2vCPUs and 4 GB of RAM each to start with. In short, you will want to:

1. Select the `baserow/baserow:2.0.6` image.
2. Add a port mapping of `80` on TCP as this is where this images HTTP server is
   listening by default.
3. Mark the container as essential.
4. Set the following env variables:

> A full list of all environment variables available can be
> found [here](./configuration.md).

| Env variable                  | Description                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DISABLE_VOLUME_CHECK=true`   | *Must be set to true*. Needed to disable the check designed to help non-technical users who are not configuring an external Postgres and S3. Because we are configuring external services we do not need any volume mounted into the container.                                                                                                                                                                                           |
| `BASEROW_PUBLIC_URL`          | The public URL or IP that will be used to access baserow in your user's browser. Always should start with http:// https:// even if accessing via an IP address.                                                                                                                                                                                                                                                                           |
| `DATABASE_HOST`               | The hostname of the Postgres database Baserow will use to store its data in.                                                                                                                                                                                                                                                                                                                                                              |
| `DATABASE_USER`               | The username of the database user Baserow will use to connect to the database at `DATABASE_HOST`.                                                                                                                                                                                                                                                                                                                                         |
| `DATABASE_PORT`               | The port Baserow will use when trying to connect to the Postgres database at `DATABASE_HOST`.                                                                                                                                                                                                                                                                                                                                             |
| `DATABASE_NAME`               | The database name Baserow will use to store data.                                                                                                                                                                                                                                                                                                                                                                                         |
| `DATABASE_PASSWORD`           | The password of `DATABASE_USER` on the Postgres server at `DATABASE_HOST`. Alternatively, you can provide `DATABASE_PASSWORD_FILE` and set it to the file path of a secret injected into the container's file system.                                                                                                                                                                                                                     |
| `REDIS_URL`                   | A standard Redis connection string in the format of: `redis://[redisuser]:[password]@[redishost]:[redisport]/0?ssl_cert_reqs=required`.                                                                                                                                                                                                                                                                                                   |
| `AWS_STORAGE_BUCKET_NAME`     | Your AWS storage bucket name.                                                                                                                                                                                                                                                                                                                                                                                                             |
| `AWS_ACCESS_KEY_ID`           | The access key for your S3 IAM AWS account. When set to anything other than empty will switch Baserow to use a S3 compatible bucket for storing user file uploads.                                                                                                                                                                                                                                                                        |
| `AWS_SECRET_ACCESS_KEY`       | The access secret key for your S3 IAM AWS account. `AWS_SECRET_ACCESS_KEY_FILE` can similarly be provided instead.                                                                                                                                                                                                                                                                                                                        |
| `DOWNLOAD_FILE_VIA_XHR`       | Must be set to `1` to work with AWS S3 currently to force download links to download files via XHR query to bypass `Content-Disposition: inline`. If your files are stored under another origin, you also must add CORS headers to your S3 bucket.                                                                                                                                                                                        |
| `BASEROW_EXTRA_ALLOWED_HOSTS` | An optional comma-separated list of hostnames which will be added to Baserow’s Django backend ALLOWED_HOSTS setting. Add your ALB IP address here so the health checks it sends are allowed through, or alternatively configure the less secure value `*` to get things running and restrict hosts later once everything is working.                                                                                                      |
| `BASEROW_JWT_SIGNING_KEY`     | **Must be set so all the containers share the same signing key.** The signing key is used to sign the content of generated tokens. For HMAC signing, this should be a random string with at least as many bits of data as is required by the signing protocol. See [here](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html#signing-key) for more details. `BASEROW_JWT_SIGNING_KEY_FILE` is also supported. |
| `SECRET_KEY`                  | **Must be set so all the containers share the same secret key.** The Secret key used by Django for cryptographic signing such as generating secure password reset links and managing sessions. See [here](https://docs.djangoproject.com/en/3.2/ref/settings/#std:setting-SECRET_KEY) for more details. `SECRET_KEY_FILE` is also supported.                                                                                              |
| `EMAIL_SMTP_*`                | There are a number of SMTP related environment variables documented in our environment variable guide [here](./configuration.md) which will also need to be set so Baserow can send invitation and password reset emails.                                                                                                                                                                                                                 |

5. Select the desired launch type (we used Fargate).
6. Set the OS family as Linux.
7. Next create the ECS service using your ALB, target group and this task definition.
8. Ensure the Ingress security group for the ECS containers should allow the ports for:
    1. The HTTP port (80 unless you've set up different port mappings)
    2. The Redis port
    3. The Postgres port

#### 6) Example task definition

Here is a full example task definition using ECS and Fargate.

```
container_definitions    = <<DEFINITION
  [
    {
      "name": "baserow_task",
      "image": "baserow/baserow:2.0.6", 
      "logConfiguration": {                     #logs are not mandatory
                "logDriver": "awslogs",
                "options": {
                    "awslogs-region" : "YOUR_REGION_NAME",
                    "awslogs-group" : "/ecs/baserow_log",
                    "awslogs-stream-prefix" : "baserow",
                    "awslogs-create-group": "true"
      }
    },
      "environment": [
      {
        "name": "DISABLE_VOLUME_CHECK",
        "value": "yes"
      },
      {
        "name": "BASEROW_PUBLIC_URL",
        "value": "<YOUR_PUBLIC_URL>"
      },
       {
        "name": "DATABASE_HOST",
        "value": "<YOUR_POSTGRES_DB_HOST>"
      },
      {
        "name": "DATABASE_USER",
        "value": "postgres"
      },
      {
        "name": "DATABASE_PORT",
        "value": "<PORT_NUMBER>"
      },
      {
        "name": "DATABASE_NAME",
        "value": "<YOUR_POSTGRES_DB_NAME>"
      },
      {
        "name": "DATABASE_PASSWORD",
        "value": "<YOUR_POSTGRES_DB_PASSWORD>"
      },
      {
        "name": "REDIS_URL",
        "value": "rediss://default:password@YOUR_REDIS_PRIMARY_ENDPOINT:6379/0?ssl_cert_reqs=required"
      },
      {
        "name": "AWS_STORAGE_BUCKET_NAME",
        "value": "<YOUR_BUCKET_NAME>"
      },
      {
        "name": "AWS_ACCESS_KEY_ID",
        "value": "<YOUR_AWS_ACCESS_KEY_ID>"
      },
      {
        "name": "AWS_SECRET_ACCESS_KEY",
        "value": "<YOUR_AWS_SECRET_ACCESS_KEY>"
      },
       {
        "name": "DOWNLOAD_FILE_VIA_XHR",
        "value": "1"
      },
      {
        "name": "BASEROW_EXTRA_ALLOWED_HOSTS",
        "value": "<YOUR_ALLOWED_HOSTS>"
      },
      {
        "name": "BASEROW_JWT_SIGNING_KEY",
        "value": "<YOUR_SIGNING_KEY>"
      },
      {
        "name": "SECRET_KEY",
        "value": "<YOUR_SECRET_KEY>"
      }
      ],
      "essential": true,
      "portMappings": [
        {
          "containerPort": 80,
          "hostPort": 80 
        }
      ],
      "memory": 8192,
      "cpu": 4096
    }
  ]
  DEFINITION
  requires_compatibilities = ["FARGATE"] 
  network_mode             = "awsvpc"    
  memory                   = 8192         
  cpu                      = 4096        
  ```

#### 7) Extra Scaling Options

Other than launching more `baserow/baserow` tasks and scaling up the RDS postgres
server, the `baserow/baserow` image has the following scaling environment variables
which can help reduce the resource usage per container or allocate more resources to
certain services inside the container.

1. `BASEROW_AMOUNT_OF_GUNICORN_WORKERS` controls the number of REST API workers (
   the things that do most of the API work) per container. Defaults to 3. Each extra
   worker generally takes up around 100-200 MB of RAM.
2. `BASEROW_AMOUNT_OF_WORKERS` controls the number of background task celery runners,
   these run real-time collaboration tasks, cleanup jobs, and other slow tasks like big
   file exports/imports. If you are scaling many of these containers you probably only
   need one of these background workers per container as they will all pool together and
   collect background tasks submitted from any other container via Redis.
3. You can make the image launch fewer internal processes and hence reduce memory usage
   by setting `BASEROW_RUN_MINIMAL=yes` AND `BASEROW_AMOUNT_OF_WORKERS=1`.
    1. This will cause this image to only launch a single celery task process which
       handles both the fast and slow queues.
    2. The consequence of this is that there is only one process handling tasks per
       container and so a slow task such as a snapshot of a large Baserow database might
       delay a fast queue task like sending a real-time row updated signal to all users
       looking at a table.
    3. However, if you have enough other containers, the overall pool of async task
       workers will be more than enough to deal with a mix of slow and fast tasks.

#### 8) Deployment complete

You should now have a fully running Baserow cluster. The first user to sign-up becomes
the first "staff" instance-wide admin user. This user can then configure Baserow's
in-tool settings, active enterprise licenses, promote other users to being staff etc.

## Option 2) Deploying Baserow as separate services to Fargate/ECS

The `baserow/backend:2.0.6` and `baserow/web-frontend:2.0.6` images allow you to run
Baserow's various services as separate containers.

These images are used by the Official Helm chart, our various docker-compose.yml
example setups and are best for production environments where you want full control and
flexibility managing Baserow.

### Why choose this method

#### Pros

* Each service can be scaled individually giving you fine-grained control.
* Follows the more traditional one server per container model.
* Logging and debugging per service issues is easier.
* The containers are individually simpler have less moving parts.

#### Cons

* More complex to set up and maintain as a whole.
* More involved ALB and networking configuration is required to ensure the correct
  requests get sent to the correct service.

### Installation steps

Follow steps 1, 2 and 3 from the Option 1 guide above as we need the exact same S3
bucket, RDS and Redis setup first.

#### 4) Configuring an ALB and Target groups

First you will need to make 3 separate target groups with a target type of
IP:

1. `backend-asgi` on port `8000`/`HTTP` with a health check using URL `/api/_health/`
   for
   our websocket service.
2. `backend-wsgi` on port `8000`/`HTTP` with a health check using URL `/api/_health/`
   for
   our backend API service.
3. `web-frontend` on port `3000`/`HTTP` with a health check using URL `/_health/` for
   our frontend service.

*The trailing slash on the health check endpoints is required!*

Now make the ALB with a HTTP port 80 listener routing to the `web-frontend` group.
Then once it is made go to this listener and configure it with three different rules
routing to each of the separate groups.

1. The default rule to catch all other requests which forwards to the `web-frontend`
   group.
2. A path condition of `/ws/*` which forwards to the `backend-asgi` group.
3. A path condition of `/api/*` which forwards to the `backend-wsgi` group.

Later on the Baserow `web-frontend` service will need to be able to communicate with
the `backend-wsgi` service through a load balancer. You can use this same load balancer
to both balance external requests and these inter service requests if you want, however
make sure you've appropriately setup the security groups to allow communication between
the ECS tasks and ALB.

#### 5) Deploying Baserow's individual services

Let's now deploy each of Baserow's individual services to Fargate/ECS. Make a
new cluster for Baserow and then proceed to make the following task definitions.

> If you are familiar with K8S then [this sample config](./install-with-k8s.md) gives an
> overview of the services.
>
Alternatively [this docker-compose](https://github.com/baserow/baserow/blob/develop/docker-compose.no-caddy.yml)
> can also be used as reference

#### 6) The backend WSGI service

This service is our HTTP REST API service. When creating the task definition you should:

1. In the task defintion use the `baserow/backend:2.0.6` image
2. Under docker configuration set `gunicorn-wsgi,--timeout,60` as the Command.

> We recommend setting the timeout of each HTTP API request to 60 seconds in the
> command above as the default of 30 seconds can be too short for very large
> Baserow tables.

3. We recommend 2vCPUs and 4 GB of RAM per container to start with.
4. Map the container port `8000`/`TCP` with `HTTP` App protocol.
5. Mark the container as essential.
6. Set the following environment variables and keep note of these as you'll need to set
   the same variables again later on the other task definitions. Using an environment
   file to share these is also a good idea.

| Env variable                  | Description                                                                                                                                                                                                                                                                                                                                                                                                                               |
| ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BASEROW_PUBLIC_URL`          | The public URL or IP that will be used to access baserow in your user's browser. Always should start with http:// https:// even if accessing via an IP address.                                                                                                                                                                                                                                                                           |
| `DATABASE_HOST`               | The hostname of the Postgres database Baserow will use to store its data in.                                                                                                                                                                                                                                                                                                                                                              |
| `DATABASE_USER`               | The username of the database user Baserow will use to connect to the database at `DATABASE_HOST`.                                                                                                                                                                                                                                                                                                                                         |
| `DATABASE_PORT`               | The port Baserow will use when trying to connect to the Postgres database at `DATABASE_HOST`.                                                                                                                                                                                                                                                                                                                                             |
| `DATABASE_NAME`               | The database name Baserow will use to store data.                                                                                                                                                                                                                                                                                                                                                                                         |
| `DATABASE_PASSWORD`           | The password of `DATABASE_USER` on the Postgres server at `DATABASE_HOST`. Alternatively, you can provide `DATABASE_PASSWORD_FILE` and set it to the file path of a secret injected into the container's file system.                                                                                                                                                                                                                     |
| `REDIS_URL`                   | A standard Redis connection string in the format of: `redis://[redisuser]:[password]@[redishost]:[redisport]/0?ssl_cert_reqs=required`.                                                                                                                                                                                                                                                                                                   |
| `AWS_STORAGE_BUCKET_NAME`     | Your AWS storage bucket name.                                                                                                                                                                                                                                                                                                                                                                                                             |
| `AWS_ACCESS_KEY_ID`           | The access key for your S3 IAM AWS account. When set to anything other than empty will switch Baserow to use a S3 compatible bucket for storing user file uploads.                                                                                                                                                                                                                                                                        |
| `AWS_SECRET_ACCESS_KEY`       | The access secret key for your S3 IAM AWS account. `AWS_SECRET_ACCESS_KEY_FILE` can similarly be provided instead.                                                                                                                                                                                                                                                                                                                        |
| `BASEROW_EXTRA_ALLOWED_HOSTS` | An optional comma-separated list of hostnames which will be added to Baserow’s Django backend ALLOWED_HOSTS setting. Add your ALB IP address here so the health checks it sends are allowed through, or alternatively configure the less secure value `*` to get things running and restrict hosts later once everything is working.                                                                                                      |
| `BASEROW_JWT_SIGNING_KEY`     | **Must be set so all the containers share the same signing key.** The signing key is used to sign the content of generated tokens. For HMAC signing, this should be a random string with at least as many bits of data as is required by the signing protocol. See [here](https://django-rest-framework-simplejwt.readthedocs.io/en/latest/settings.html#signing-key) for more details. `BASEROW_JWT_SIGNING_KEY_FILE` is also supported. |
| `SECRET_KEY`                  | **Must be set so all the containers share the same secret key.** The Secret key used by Django for cryptographic signing such as generating secure password reset links and managing sessions. See [here](https://docs.djangoproject.com/en/3.2/ref/settings/#std:setting-SECRET_KEY) for more details. `SECRET_KEY_FILE` is also supported.                                                                                              |
| `EMAIL_SMTP_*`                | There are a number of SMTP related environment variables documented in our environment variable guide [here](./configuration.md) which will also need to be set so Baserow can send invitation and password reset emails.                                                                                                                                                                                                                 |

#### 7) The backend ASGI service

> It is possible to just use the ASGI service and not make a separate ASGI and WSGI
> service and then route all HTTP and Websocket requests to the single ASGI service.
> However, the ASGI service has degraded performance handling normal HTTP requests
> compared to the service in WSGI mode above. Also being able to scale them separately
> is
> nice as often only a few ASGI services are needed to handle the websocket load.

This service is our Websocket API service and when configuring the task definition you
should:

1. Use the `baserow/backend:2.0.6`
2. Under docker configuration set `gunicorn` as the Command.
3. We recommend 2vCPUs and 4 GB of RAM per container to start with.
4. Map the container port `8000`/`TCP`
5. Mark the container as essential.
6. Set the same environment variables as you did with the backend-wsgi service above.

#### 8) The backend celery worker service

This service is our asynchronous high priority task worker queue used for realtime
collaboration and sending emails.

1. Use the `baserow/backend:2.0.6` image with `celery-worker` as the image command.
2. Under docker configuration set `celery-worker` as the Command.
3. No port mappings needed.
4. We recommend 2vCPUs and 4 GB of RAM per container to start with.
5. Mark the container as essential.
6. Set same environment variables as you did with the backend-wsgi service above.

#### 9) The backend celery export worker service

This service is our asynchronous slow/low priority task worker queue for batch
processes and running potentially slow operations for users like table exports and
imports etc.

1. Use the `baserow/backend:2.0.6` image.
2. Under docker configuration set `celery-exportworker` as the Command.
3. No port mappings needed.
4. We recommend 2vCPUs and 4 GB of RAM per container to start with.
5. Mark the container as essential.
6. Set same environment variables as you did with the backend-wsgi service above.

#### 10) The backend celery beat service

This service is our CRON task scheduler that can have multiple replicas deployed.

1. Use the `baserow/backend:2.0.6` image.
2. Under docker configuration set `celery-beat` as the Command.
3. No port mapping needed.
4. We recommend 1vCPUs and 3 GB of RAM per container to start with.
    1. Only one of these
       containers will be scheduling tasks globally at any time.
    2. Any duplicate containers running will hot standbys to take over
       scheduling if/when the first one fails and
       releases the scheduling Redis lock.
5. Mark the container as essential.
6. Set same environment variables as you did with the backend-wsgi service above.

#### 11) The web-frontend service

Finally, this service is used for server side rendering and serving the frontend of
Baserow.

1. Use the `baserow/web-frontend:2.0.6` image with no arguments needed.
2. Map the container port `3000`
3. We recommend 2vCPUs and 4 GB of RAM per container to start with.
4. Mark the container as essential.
5. Set the following *different from the backend services* environment variables

* `BASEROW_PUBLIC_URL`:
  The public URL or IP that will be used to access baserow in your user's browser.
  Always should start with http:// https:// even if accessing via an IP address.
* `PRIVATE_BACKEND_URL`: The web-frontend containers need to be able to send HTTP
  requests to the `backend-wsgi` containers running the rest API.
    * We recommend setting this to your ALB's address and it must start with http:// or
      https://.
    * Ensure the security groups are set up correctly to allow these internal HTTP
      requests.
    * If you've not set `BASEROW_EXTRA_ALLOWED_HOSTS=*` on the `backend-wsgi`
      and `backend-asgi` containers make sure to add the value you've set for this env
      var to `BASEROW_EXTRA_ALLOWED_HOSTS` for those services otherwise they will not
      allow connections from the web-frontend.
* `DOWNLOAD_FILE_VIA_XHR`: Must be set to `1` to work with AWS S3 currently to force
  download links to download files via XHR query to bypass `Content-Disposition: inline`
  . If your files are stored under another origin, you also must add CORS headers to
  your S3 bucket.

#### 13) Create the ECS services

Now make sure to go back and create the ECS services for the  
task definitions you just made. Remember to set 900 second grace
periods in the health check when connecting things up.

> Alternatively you can make a
> single ECS service for all of Baserow's tasks, however you will then need to use
> the API/CLI to connect multiple target groups to this single ECS service as this is
> not possible via the AWS UI currently. You might also need to ensure that
> `backend-asgi` and `backend-wsgi` are exposed on different ports for the target groups
> to route properly to each individually. Set the `BASEROW_BACKEND_PORT` env var
> on both of these services to different values to get them binding to different ports
> inside the container.

1. `backend-wsgi` service connected to the `backend-wsgi` target group
2. `backend-asgi` service connected to the `backend-asgi` target group
3. `web-frontend` service connected to the `web-frontend` target group
4. `celery-worker` service
5. `celery-exportworker` service
6. `celery-beat` service

#### 12) Scaling Options

Most of the time scaling up your `backend-wsgi` tasks and RDS postgres will be your
first port of call for handling more requests. If your realtime collaboration is slowing
down you can scale up the `backend-asgi` and `celery-worker` services. Finally, if you
are having to wait a long time for jobs to start (they will have progress bars in the
Baserow UI stuck at 0%) then you can add more `celery-exportworker` services.

There are also the following env vars that can change the number of worker processes
launched inside each container to vertically scale each one:

1. `BASEROW_AMOUNT_OF_GUNICORN_WORKERS` controls the number of REST API workers (
   the things that do most of the API work) per `gunicorn-wsgi` or `gunicorn` container.
   Defaults to 3. Each extra worker generally takes up around 100-200 MB of RAM.
2. `BASEROW_AMOUNT_OF_WORKERS` controls the number of background task celery runners,
   in the `celery-worker` and `celery-exportworker` containers.

#### 13) Deployment complete

You should now have a fully running Baserow cluster. This deployment method is more
complex to get working so if you need any help please post in
our [community forums](https://community.baserow.io).

The first user to sign-up becomes the first "staff" instance-wide admin user. This user
can then configure Baserow's in-tool settings, active enterprise licenses, promote other
users to being staff etc.

## Upgrading Baserow

Upgrading an ECS/Fargate deployment of Baserow can be done by.

1. Back up/snapshot your RDS Postgres database
2. Stop all existing containers running the old version first to prevent
   users from getting errors whilst accessing old containers during the upgrade.
3. Update your task definitions to have the new image.
4. The first new `baserow/baserow` or `baserow/backend-wsgi/asgi` container to startup
   will
   automatically apply any required database migrations and upgrades.
5. Once these are complete, all the new Baserow containers will start accepting requests
   and your upgrade is complete.

## FAQ

### Fixing the `CROSSSLOT Keys in request don't hash to the same slot` error

If you see this error in your logs it means you have launched Baserow with a Redis which
is in cluster mode. Baserow uses libraries that do not support Redis in cluster mode, so
you will need to provision a new Redis in the non-cluster mode for things to work.
Non-cluster mode Redis can still be scaled and multi-zone, additionally Baserow does not
generally end up with Redis as the bottleneck for requests.

### My ELB Health checks are failing

The first-time migration after a first time deploy or upgrade might take some time so
you might want to try increasing the grace period.

Secondly, Make sure the ELB can connect to the container. Please note that the container
has its internal health check script which will be also calling the health check
endpoint. So the presence of logs showing health check 200 responses doesn't mean your
ELB is the one triggering those.

### I get `CORS errors` when downloading a file from a Baserow file field

Your CORS was not set up properly on the S3 bucket. Please see the example CORS config
above or contact us for support.

### I get `Secure Redis scheme specified (rediss) with no ssl options, defaulting to insecure SSL behavior` warnings

Make sure you have added `?ssl_cert_reqs=required` onto the end of your `REDIS_URL` env
var.
