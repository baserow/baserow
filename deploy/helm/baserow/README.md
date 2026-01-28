# Baserow Helm Chart

Baserow is an open-source no-code database tool and Airtable alternative. It is a modern database tool that allows you to create a database, web-based application, and API without code. It is built on top of Django and Vue.js and is designed to be easily deployed to a platform like Kubernetes.

This chart can have dependencies on other charts, such as PostgreSQL, Redis, Minio, and Caddy. The chart can be configured to use an existing instance of these services or deploy them as part of the Baserow deployment.

## Installing the Chart

To install the chart with the release name `my-baserow` run the following commands:

From repo
```bash
helm repo add baserow-chart https://baserow.github.io/baserow-chart
helm install my-baserow baserow-chart/baserow --namespace baserow --create-namespace --values config.yaml
```

From source code
```bash
helm dependency update
helm install my-baserow . --namespace baserow --create-namespace
helm upgrade my-baserow . --namespace baserow
```

## Minimal configuration

Make the following changes to the values file to deploy the Baserow application with the default configuration.

```yaml
global:
  baserow:
    domain: "your-baserow-domain.com"
    backendDomain: "api.your-baserow-domain.com"
    objectsDomain: "objects.your-baserow-domain.com"
```

## Using existing Postgres and Redis

You can use the following configuration to use an existing Postgres database and Redis cluster.

```yaml
redis:
  enabled: false

postgresql:
  enabled: false
```

Add the following configuration to the backendSecrets to use an existing managed database and Redis cluster. 
```yaml
backendSecrets:
  DATABASE_HOST: "my-baserow-baserow-backend-postgresql"
  DATABASE_PORT: "5432"
  DATABASE_NAME: "baserow"
  DATABASE_USER: "baserow"
  DATABASE_PASSWORD: "password"
  REDIS_HOST: "my-baserow-baserow-backend-redis"
  REDIS_PORT: "6379"
  REDIS_PASSWORD: "password"
```

## Caddy Ingress Configuration

Caddy is a web server that can be used as an ingress controller. When using Caddy, set the ingress configuration to use Caddy as the ingress controller. Make note of the `onDemandAsk` configuration, which is used to trigger on-demand TLS certificates. Pointed here to the health check endpoint of caddy itself to always create new certificates. On production workloads set it to the backend api endpoint to check if the domain exists in the database.

```yaml
caddy:
  enabled: true
  ingressController:
    className: caddy
    config:
      email: "my@email.com"
      proxyProtocol: true
      experimentalSmartSort: false
      onDemandTLS: true
      onDemandAsk: http://:9765/healthz
```

## Autoscaling configuration
For each Baserow component, a HorizontalPodAutoscaler can be configured individually. The following example enables autoscaling on the wsgi backend deployment.

```yaml
baserow-backend-wsgi:
  autoscaling:
    enabled: true
    minReplicas: 2
    maxReplicas: 10 
    targetCPUUtilizationPercentage: 80
    targetMemoryUtilizationPercentage: 80
```

```yaml
      onDemandAsk: "http://my-baserow-baserow-backend-wsgi/api/builder/domains/ask-public-domain-exists/"
```

## AI and Embeddings Configuration

Baserow supports multiple AI providers for generative AI features and the AI assistant. The embeddings service powers semantic search for the AI assistant's documentation lookup feature. For more documentation check the [Baserow AI documentation](/docs/installation/ai-assistant.md).

### Enable AI Assistant

To enable the AI assistant, you need to configure the LLM model and provide the necessary API keys for the chosen provider.

```yaml
global:
  baserow:
    assistantLLMModel: "groq/openai/gpt-oss-120b"

backendSecrets:
  GROQ_API_KEY: "your-groq-api-key"
```

More information about the available providers can be found here: https://baserow.io/docs/installation%2Fai-assistant

### Enable Embeddings Service

The AI assistant uses the embeddings service and requires the LLM model to be configured. You need to enable this next to the global ai configuration.

#### Basic Configuration

```yaml
baserow-embeddings:
  enabled: true
```

## Different Cloud Providers

On different cloud providers, you may need to configure the Object storage, ingress and Load Balancer differently. Below are some examples of how to configure them.

### AWS

#### S3 Config
When deploying to AWS, you can use the following configuration to use S3 for object storage. Make sure to disable minio as it is not needed.

```yaml
minio:
  enabled: false

backendConfigMap:
  AWS_STORAGE_BUCKET_NAME: "my-baserow-baserow-backend-bucket"
  AWS_S3_CUSTOM_DOMAIN: "my-baserow-baserow-backend-bucket"
  AWS_S3_REGION_NAME: "us-east-1"
  AWS_S3_ENDPOINT_URL: "https://s3.us-east-1.amazonaws.com/my-baserow-baserow-backend-bucket"
```

#### AWS Authentication
AWS authentication can be set by service account or environment variables. Below is an example of setting the AWS credentials using the environment variables. 

```yaml
backendSecrets:
  AWS_ACCESS_KEY_ID: "my-access-key"
  AWS_SECRET_ACCESS_KEY: "my-secret-key"
```

When running on EKS you can also use a service account with an IAM role and permissions. For the service account, you can use the following configuration. To create the corresponding IAM role, refer to the AWS documentation. https://docs.aws.amazon.com/eks/latest/userguide/iam-roles-for-service-accounts.html

```yaml
global:
  baserow:
    serviceAccount:
      shared: true
      create: true
      name: baserow
      annotations: {}
```

#### Ingress

When deploying to AWS, you can use the following configuration to create a Network Load Balancer. For more information about the annotations, refer to the AWS documentation. https://docs.aws.amazon.com/eks/latest/userguide/network-load-balancing.html

```yaml
ingress:
  enabled: true

caddy:
  enabled: true
  ingressController:
    className: caddy
    config:
      email: "my@email.com"
      proxyProtocol: true
      experimentalSmartSort: false
      onDemandTLS: true
      onDemandAsk: http://:9765/healthz
  loadBalancer:
    externalTrafficPolicy: "Local"
    annotations:
      service.beta.kubernetes.io/aws-load-balancer-proxy-protocol: "*"
      service.beta.kubernetes.io/aws-load-balancer-scheme: "internet-facing"
      service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: "ip"
      service.beta.kubernetes.io/aws-load-balancer-healthcheck-protocol: "TCP"
      service.beta.kubernetes.io/aws-load-balancer-alpn-policy: "HTTP2Preferred"
```

### Digital ocean

#### Ingress

When deploying to Digital Ocean, you can use the following configuration to create a Load Balancer. For more information about the annotations, refer to the Digital Ocean documentation. https://docs.digitalocean.com/products/kubernetes/how-to/add-load-balancers/

```yaml
ingress:
  enabled: true

caddy:
  enabled: true
  ingressController:
    config:
      email: "my@email.com"
      proxyProtocol: true
      experimentalSmartSort: false
      onDemandTLS: true
      onDemandRateLimitInterval: "2m"
      onDemandRateLimitBurst: 5
      onDemandAsk: http://:9765/healthz
  loadBalancer:
    externalTrafficPolicy: "Local"
    annotations:
      service.beta.kubernetes.io/do-loadbalancer-protocol: "http"
      service.beta.kubernetes.io/do-loadbalancer-algorithm: "round_robin"
      service.beta.kubernetes.io/do-loadbalancer-tls-ports: "443"
      service.beta.kubernetes.io/do-loadbalancer-tls-passthrough: "true"
      service.beta.kubernetes.io/do-loadbalancer-redirect-http-to-https: "true"
      service.beta.kubernetes.io/do-loadbalancer-enable-proxy-protocol: "true"
```


## Parameters

### Global parameters

| Name                                                               | Description                                                                             | Value                   |
| ------------------------------------------------------------------ | --------------------------------------------------------------------------------------- | ----------------------- |
| `global.baserow.imageRegistry`                                     | Global Docker image registry                                                            | `baserow`               |
| `global.baserow.imagePullSecrets`                                  | Global Docker registry secret names as an array                                         | `[]`                    |
| `global.baserow.image.tag`                                         | Global Docker image tag                                                                 | `2.0.6`                |
| `global.baserow.serviceAccount.shared`                             | Set to true to share the service account between all application components.            | `true`                  |
| `global.baserow.serviceAccount.create`                             | Set to true to create a service account to share between all application components.    | `true`                  |
| `global.baserow.serviceAccount.name`                               | Configure a name for service account to share between all application components.       | `baserow`               |
| `global.baserow.serviceAccount.annotations`                        | Configure annotations for the shared service account.                                   | `{}`                    |
| `global.baserow.serviceAccount.automountServiceAccountToken`       | Automount the service account token to the pods.                                        | `false`                 |
| `global.baserow.backendConfigMap`                                  | Configure a name for the backend configmap.                                             | `backend-config`        |
| `global.baserow.backendSecret`                                     | Configure a name for the backend secret.                                                | `backend-secret`        |
| `global.baserow.frontendConfigMap`                                 | Configure a name for the frontend configmap.                                            | `frontend-config`       |
| `global.baserow.sharedConfigMap`                                   | Configure a name for the shared configmap.                                              | `shared-config`         |
| `global.baserow.envFrom`                                           | Configure secrets or configMaps to be used as environment variables for all components. | `[]`                    |
| `global.baserow.domain`                                            | Configure the domain for the frontend application.                                      | `cluster.local`         |
| `global.baserow.backendDomain`                                     | Configure the domain for the backend application.                                       | `api.cluster.local`     |
| `global.baserow.objectsDomain`                                     | Configure the domain for the external facing minio api.                                 | `objects.cluster.local` |
| `global.baserow.containerSecurityContext.enabled`                  | Enabled containers' Security Context                                                    | `false`                 |
| `global.baserow.containerSecurityContext.seLinuxOptions`           | Set SELinux options in container                                                        | `{}`                    |
| `global.baserow.containerSecurityContext.runAsUser`                | Set containers' Security Context runAsUser                                              | `""`                    |
| `global.baserow.containerSecurityContext.runAsGroup`               | Set containers' Security Context runAsGroup                                             | `""`                    |
| `global.baserow.containerSecurityContext.runAsNonRoot`             | Set container's Security Context runAsNonRoot                                           | `""`                    |
| `global.baserow.containerSecurityContext.privileged`               | Set container's Security Context privileged                                             | `false`                 |
| `global.baserow.containerSecurityContext.readOnlyRootFilesystem`   | Set container's Security Context readOnlyRootFilesystem                                 | `false`                 |
| `global.baserow.containerSecurityContext.allowPrivilegeEscalation` | Set container's Security Context allowPrivilegeEscalation                               | `false`                 |
| `global.baserow.containerSecurityContext.capabilities.drop`        | List of capabilities to be dropped                                                      | `[]`                    |
| `global.baserow.containerSecurityContext.capabilities.add`         | List of capabilities to be added                                                        | `[]`                    |
| `global.baserow.containerSecurityContext.seccompProfile.type`      | Set container's Security Context seccomp profile                                        | `""`                    |
| `global.baserow.securityContext.enabled`                           | Enable security context                                                                 | `false`                 |
| `global.baserow.securityContext.fsGroupChangePolicy`               | Set filesystem group change policy                                                      | `Always`                |
| `global.baserow.securityContext.sysctls`                           | Set kernel settings using the sysctl interface                                          | `[]`                    |
| `global.baserow.securityContext.supplementalGroups`                | Set filesystem extra groups                                                             | `[]`                    |
| `global.baserow.securityContext.fsGroup`                           | Group ID for the pod                                                                    | `""`                    |

### Baserow Configuration

| Name                | Description               | Value  |
| ------------------- | ------------------------- | ------ |
| `generateJwtSecret` | Generate a new JWT secret | `true` |

### Shared ConfigMap Configuration

| Name              | Description                                                       | Value |
| ----------------- | ----------------------------------------------------------------- | ----- |
| `sharedConfigMap` | Additional configuration for the shared ConfigMap, key value map. | `{}`  |

### Frontend ConfigMap Configuration

| Name                                      | Description                          | Value |
| ----------------------------------------- | ------------------------------------ | ----- |
| `frontendConfigMap.DOWNLOAD_FILE_VIA_XHR` | Set to "1" to download files via XHR | `1`   |

### backend Secrets Configuration

| Name             | Description                                                      | Value |
| ---------------- | ---------------------------------------------------------------- | ----- |
| `backendSecrets` | Additional configuration for the backend Secrets, key value map. | `{}`  |

### backend ConfigMap Configuration

| Name                                                              | Description                                                | Value   |
| ----------------------------------------------------------------- | ---------------------------------------------------------- | ------- |
| `backendConfigMap.DONT_UPDATE_FORMULAS_AFTER_MIGRATION`           | Set to "yes" to disable updating formulas after migration  | `yes`   |
| `backendConfigMap.SYNC_TEMPLATES_ON_STARTUP`                      | Set to "false" to disable syncing templates on startup     | `false` |
| `backendConfigMap.MIGRATE_ON_STARTUP`                             | Set to "false" to disable migration on startup             | `false` |
| `backendConfigMap.BASEROW_TRIGGER_SYNC_TEMPLATES_AFTER_MIGRATION` | Set to "true" to trigger syncing templates after migration | `true`  |

### Migration Job Configuration

| Name                                                          | Description                                               | Value     |
| ------------------------------------------------------------- | --------------------------------------------------------- | --------- |
| `migration.enabled`                                           | Enabled the migration job                                 | `true`    |
| `migration.image.repository`                                  | Migration job Docker image repository                     | `backend` |
| `migration.priorityClassName`                                 | Kubernetes priority class name for the migration job      | `""`      |
| `migration.nodeSelector`                                      | Node labels for pod assignment                            | `{}`      |
| `migration.tolerations`                                       | Tolerations for pod assignment                            | `[]`      |
| `migration.affinity`                                          | Affinity settings for pod assignment                      | `[]`      |
| `migration.extraEnv`                                          | Extra environment variables for the migration job         | `[]`      |
| `migration.envFrom`                                           | ConfigMaps or Secrets to be used as environment variables | `[]`      |
| `migration.volumes`                                           | Volumes for the migration job                             | `[]`      |
| `migration.volumeMounts`                                      | Volume mounts for the migration job                       | `[]`      |
| `migration.securityContext.enabled`                           | Enable security context                                   | `false`   |
| `migration.securityContext.fsGroupChangePolicy`               | Set filesystem group change policy                        | `""`      |
| `migration.securityContext.sysctls`                           | Set kernel settings using the sysctl interface            | `""`      |
| `migration.securityContext.supplementalGroups`                | Set filesystem extra groups                               | `""`      |
| `migration.securityContext.fsGroup`                           | Group ID for the pod                                      | `""`      |
| `migration.containerSecurityContext.enabled`                  | Enabled containers' Security Context                      | `false`   |
| `migration.containerSecurityContext.seLinuxOptions`           | Set SELinux options in container                          | `{}`      |
| `migration.containerSecurityContext.runAsUser`                | Set containers' Security Context runAsUser                | `""`      |
| `migration.containerSecurityContext.runAsGroup`               | Set containers' Security Context runAsGroup               | `""`      |
| `migration.containerSecurityContext.runAsNonRoot`             | Set container's Security Context runAsNonRoot             | `""`      |
| `migration.containerSecurityContext.privileged`               | Set container's Security Context privileged               | `false`   |
| `migration.containerSecurityContext.readOnlyRootFilesystem`   | Set container's Security Context readOnlyRootFilesystem   | `false`   |
| `migration.containerSecurityContext.allowPrivilegeEscalation` | Set container's Security Context allowPrivilegeEscalation | `false`   |
| `migration.containerSecurityContext.capabilities.drop`        | List of capabilities to be dropped                        | `[]`      |
| `migration.containerSecurityContext.capabilities.add`         | List of capabilities to be added                          | `[]`      |
| `migration.containerSecurityContext.seccompProfile.type`      | Set container's Security Context seccomp profile          | `""`      |

### Baserow Backend ASGI Configuration

| Name                                                                 | Description                                                                                  | Value                                                                                   |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `baserow-backend-asgi.image.repository`                              | Docker image repository for the ASGI server.                                                 | `backend`                                                                               |
| `baserow-backend-asgi.args`                                          | Arguments passed to the ASGI server.                                                         | `["gunicorn"]`                                                                          |
| `baserow-backend-asgi.livenessProbe.exec.command`                    | The command used to check the liveness of the ASGI server.                                   | `["/bin/bash","-c","/baserow/backend/docker/docker-entrypoint.sh backend-healthcheck"]` |
| `baserow-backend-asgi.livenessProbe.failureThreshold`                | Number of times the probe can fail before the container is restarted.                        | `3`                                                                                     |
| `baserow-backend-asgi.livenessProbe.initialDelaySeconds`             | Delay before the liveness probe is initiated after the container starts.                     | `120`                                                                                   |
| `baserow-backend-asgi.livenessProbe.periodSeconds`                   | How often (in seconds) to perform the probe.                                                 | `30`                                                                                    |
| `baserow-backend-asgi.livenessProbe.successThreshold`                | Minimum consecutive successes for the probe to be considered successful after having failed. | `1`                                                                                     |
| `baserow-backend-asgi.livenessProbe.timeoutSeconds`                  | Number of seconds after which the probe times out.                                           | `5`                                                                                     |
| `baserow-backend-asgi.readinessProbe.exec.command`                   | The command used to check the readiness of the ASGI server.                                  | `["/bin/bash","-c","/baserow/backend/docker/docker-entrypoint.sh backend-healthcheck"]` |
| `baserow-backend-asgi.readinessProbe.failureThreshold`               | Number of times the probe can fail before the container is restarted.                        | `3`                                                                                     |
| `baserow-backend-asgi.readinessProbe.initialDelaySeconds`            | Delay before the readiness probe is initiated after the container starts.                    | `120`                                                                                   |
| `baserow-backend-asgi.readinessProbe.periodSeconds`                  | How often (in seconds) to perform the probe.                                                 | `30`                                                                                    |
| `baserow-backend-asgi.readinessProbe.successThreshold`               | Minimum consecutive successes for the probe to be considered successful after having failed. | `1`                                                                                     |
| `baserow-backend-asgi.readinessProbe.timeoutSeconds`                 | Number of seconds after which the probe times out.                                           | `5`                                                                                     |
| `baserow-backend-asgi.autoscaling.enabled`                           | Enable autoscaling                                                                           | `false`                                                                                 |
| `baserow-backend-asgi.autoscaling.minReplicas`                       | Minimum number of replicas                                                                   | `2`                                                                                     |
| `baserow-backend-asgi.autoscaling.maxReplicas`                       | Maximum number of replicas                                                                   | `10`                                                                                    |
| `baserow-backend-asgi.autoscaling.targetCPUUtilizationPercentage`    | Target CPU utilization percentage for autoscaling                                            | `80`                                                                                    |
| `baserow-backend-asgi.autoscaling.targetMemoryUtilizationPercentage` | Target memory utilization percentage for autoscaling                                         | `80`                                                                                    |

### Baserow Backend WSGI Configuration

| Name                                                                 | Description                                                                                  | Value                                                                                   |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| `baserow-backend-wsgi.image.repository`                              | Docker image repository for the WSGI server.                                                 | `backend`                                                                               |
| `baserow-backend-wsgi.args`                                          | Arguments passed to the WSGI server.                                                         | `["gunicorn-wsgi","--timeout","120"]`                                                   |
| `baserow-backend-wsgi.livenessProbe.exec.command`                    | The command used to check the liveness of the WSGI server.                                   | `["/bin/bash","-c","/baserow/backend/docker/docker-entrypoint.sh backend-healthcheck"]` |
| `baserow-backend-wsgi.livenessProbe.failureThreshold`                | Number of times the probe can fail before the container is restarted.                        | `3`                                                                                     |
| `baserow-backend-wsgi.livenessProbe.initialDelaySeconds`             | Delay before the liveness probe is initiated after the container starts.                     | `120`                                                                                   |
| `baserow-backend-wsgi.livenessProbe.periodSeconds`                   | How often (in seconds) to perform the probe.                                                 | `30`                                                                                    |
| `baserow-backend-wsgi.livenessProbe.successThreshold`                | Minimum consecutive successes for the probe to be considered successful after having failed. | `1`                                                                                     |
| `baserow-backend-wsgi.livenessProbe.timeoutSeconds`                  | Number of seconds after which the probe times out.                                           | `5`                                                                                     |
| `baserow-backend-wsgi.readinessProbe.exec.command`                   | The command used to check the readiness of the wsgi server.                                  | `["/bin/bash","-c","/baserow/backend/docker/docker-entrypoint.sh backend-healthcheck"]` |
| `baserow-backend-wsgi.readinessProbe.failureThreshold`               | Number of times the probe can fail before the container is restarted.                        | `3`                                                                                     |
| `baserow-backend-wsgi.readinessProbe.initialDelaySeconds`            | Delay before the readiness probe is initiated after the container starts.                    | `120`                                                                                   |
| `baserow-backend-wsgi.readinessProbe.periodSeconds`                  | How often (in seconds) to perform the probe.                                                 | `30`                                                                                    |
| `baserow-backend-wsgi.readinessProbe.successThreshold`               | Minimum consecutive successes for the probe to be considered successful after having failed. | `1`                                                                                     |
| `baserow-backend-wsgi.readinessProbe.timeoutSeconds`                 | Number of seconds after which the probe times out.                                           | `5`                                                                                     |
| `baserow-backend-wsgi.autoscaling.enabled`                           | Enable autoscaling                                                                           | `false`                                                                                 |
| `baserow-backend-wsgi.autoscaling.minReplicas`                       | Minimum number of replicas                                                                   | `2`                                                                                     |
| `baserow-backend-wsgi.autoscaling.maxReplicas`                       | Maximum number of replicas                                                                   | `10`                                                                                    |
| `baserow-backend-wsgi.autoscaling.targetCPUUtilizationPercentage`    | Target CPU utilization percentage for autoscaling                                            | `80`                                                                                    |
| `baserow-backend-wsgi.autoscaling.targetMemoryUtilizationPercentage` | Target memory utilization percentage for autoscaling                                         | `80`                                                                                    |

### Baserow Web Frontend Configuration

| Name                                                             | Description                                                                                  | Value          |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------- |
| `baserow-frontend.image.repository`                              | Docker image repository for the Web Frontend server.                                         | `web-frontend` |
| `baserow-frontend.args`                                          | Arguments passed to the Web Frontend server.                                                 | `["nuxt"]`     |
| `baserow-frontend.workingDir`                                    | Working Directory for the container.                                                         | `""`           |
| `baserow-frontend.livenessProbe.httpGet.path`                    | The path to check for the liveness probe.                                                    | `/_health`     |
| `baserow-frontend.livenessProbe.httpGet.port`                    | The port to check for the liveness probe.                                                    | `3000`         |
| `baserow-frontend.livenessProbe.httpGet.scheme`                  | The scheme to use for the liveness probe.                                                    | `HTTP`         |
| `baserow-frontend.livenessProbe.failureThreshold`                | Number of times the probe can fail before the container is restarted.                        | `3`            |
| `baserow-frontend.livenessProbe.initialDelaySeconds`             | Delay before the liveness probe is initiated after the container starts.                     | `5`            |
| `baserow-frontend.livenessProbe.periodSeconds`                   | How often (in seconds) to perform the probe.                                                 | `30`           |
| `baserow-frontend.livenessProbe.successThreshold`                | Minimum consecutive successes for the probe to be considered successful after having failed. | `1`            |
| `baserow-frontend.livenessProbe.timeoutSeconds`                  | Number of seconds after which the probe times out.                                           | `5`            |
| `baserow-frontend.readinessProbe.httpGet.path`                   | The path to check for the readiness probe.                                                   | `/_health`     |
| `baserow-frontend.readinessProbe.httpGet.port`                   | The port to check for the readiness probe.                                                   | `3000`         |
| `baserow-frontend.readinessProbe.httpGet.scheme`                 | The scheme to use for the readiness probe.                                                   | `HTTP`         |
| `baserow-frontend.readinessProbe.failureThreshold`               | Number of times the probe can fail before the container is restarted.                        | `3`            |
| `baserow-frontend.readinessProbe.initialDelaySeconds`            | Delay before the readiness probe is initiated after the container starts.                    | `5`            |
| `baserow-frontend.readinessProbe.periodSeconds`                  | How often (in seconds) to perform the probe.                                                 | `30`           |
| `baserow-frontend.readinessProbe.successThreshold`               | Minimum consecutive successes for the probe to be considered successful after having failed. | `1`            |
| `baserow-frontend.readinessProbe.timeoutSeconds`                 | Number of seconds after which the probe times out.                                           | `5`            |
| `baserow-frontend.mountConfiguration.backend`                    | If enabled, all the backend service configurations and secrets will be mounted.              | `false`        |
| `baserow-frontend.mountConfiguration.frontend`                   | If enabled, all the frontend service configurations and secrets will be mounted.             | `true`         |
| `baserow-frontend.service.targetPort`                            | The port the Web Frontend server listens on.                                                 | `3000`         |
| `baserow-frontend.autoscaling.enabled`                           | Enable autoscaling                                                                           | `false`        |
| `baserow-frontend.autoscaling.minReplicas`                       | Minimum number of replicas                                                                   | `2`            |
| `baserow-frontend.autoscaling.maxReplicas`                       | Maximum number of replicas                                                                   | `10`           |
| `baserow-frontend.autoscaling.targetCPUUtilizationPercentage`    | Target CPU utilization percentage for autoscaling                                            | `80`           |
| `baserow-frontend.autoscaling.targetMemoryUtilizationPercentage` | Target memory utilization percentage for autoscaling                                         | `80`           |

### Baserow Celery beat Configuration

| Name                                          | Description                                                            | Value             |
| --------------------------------------------- | ---------------------------------------------------------------------- | ----------------- |
| `baserow-celery-beat-worker.image.repository` | Docker image repository for the Celery beat worker.                    | `backend`         |
| `baserow-celery-beat-worker.args`             | Arguments passed to the Celery beat worker.                            | `["celery-beat"]` |
| `baserow-celery-beat-worker.replicaCount`     | Number of replicas for the Celery beat worker.                         | `1`               |
| `baserow-celery-beat-worker.service.create`   | Set to false to disable creating a service for the Celery beat worker. | `false`           |

### Baserow Celery export worker Configuration

| Name                                            | Description                                                            | Value                     |
| ----------------------------------------------- | ---------------------------------------------------------------------- | ------------------------- |
| `baserow-celery-export-worker.image.repository` | Docker image repository for the Celery export worker.                  | `backend`                 |
| `baserow-celery-export-worker.args`             | Arguments passed to the Celery export worker.                          | `["celery-exportworker"]` |
| `baserow-celery-export-worker.replicaCount`     | Number of replicas for the Celery export worker.                       | `1`                       |
| `baserow-celery-export-worker.service.create`   | Set to false to disable creating a service for the Celery beat worker. | `false`                   |

### Baserow Celery worker Configuration

| Name                                                       | Description                                                                                  | Value                                                                                         |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `baserow-celery-worker.image.repository`                   | Docker image repository for the Celery worker.                                               | `backend`                                                                                     |
| `baserow-celery-worker.args`                               | Arguments passed to the Celery worker.                                                       | `["celery-worker"]`                                                                           |
| `baserow-celery-worker.replicaCount`                       | Number of replicas for the Celery worker.                                                    | `1`                                                                                           |
| `baserow-celery-worker.service.create`                     | Set to false to disable creating a service for the Celery beat worker.                       | `false`                                                                                       |
| `baserow-celery-worker.livenessProbe.exec.command`         | The command used to check the liveness of the WSGI server.                                   | `["/bin/bash","-c","/baserow/backend/docker/docker-entrypoint.sh celery-worker-healthcheck"]` |
| `baserow-celery-worker.livenessProbe.failureThreshold`     | Number of times the probe can fail before the container is restarted.                        | `3`                                                                                           |
| `baserow-celery-worker.livenessProbe.initialDelaySeconds`  | Delay before the liveness probe is initiated after the container starts.                     | `10`                                                                                          |
| `baserow-celery-worker.livenessProbe.periodSeconds`        | How often (in seconds) to perform the probe.                                                 | `30`                                                                                          |
| `baserow-celery-worker.livenessProbe.successThreshold`     | Minimum consecutive successes for the probe to be considered successful after having failed. | `1`                                                                                           |
| `baserow-celery-worker.livenessProbe.timeoutSeconds`       | Number of seconds after which the probe times out.                                           | `10`                                                                                          |
| `baserow-celery-worker.readinessProbe.exec.command`        | The command used to check the readiness of the wsgi server.                                  | `["/bin/bash","-c","/baserow/backend/docker/docker-entrypoint.sh celery-worker-healthcheck"]` |
| `baserow-celery-worker.readinessProbe.failureThreshold`    | Number of times the probe can fail before the container is restarted.                        | `3`                                                                                           |
| `baserow-celery-worker.readinessProbe.initialDelaySeconds` | Delay before the readiness probe is initiated after the container starts.                    | `10`                                                                                          |
| `baserow-celery-worker.readinessProbe.periodSeconds`       | How often (in seconds) to perform the probe.                                                 | `30`                                                                                          |
| `baserow-celery-worker.readinessProbe.successThreshold`    | Minimum consecutive successes for the probe to be considered successful after having failed. | `1`                                                                                           |
| `baserow-celery-worker.readinessProbe.timeoutSeconds`      | Number of seconds after which the probe times out.                                           | `10`                                                                                          |

### Baserow Celery Flower Configuration

| Name                                     | Description                                                    | Value               |
| ---------------------------------------- | -------------------------------------------------------------- | ------------------- |
| `baserow-celery-flower.enabled`          | Set to true to enable the Celery Flower monitoring tool.       | `false`             |
| `baserow-celery-flower.image.repository` | Docker image repository for the Celery Flower monitoring tool. | `backend`           |
| `baserow-celery-flower.args`             | Arguments passed to the Celery Flower monitoring tool.         | `["celery-flower"]` |
| `baserow-celery-flower.replicaCount`     | Number of replicas for the Celery Flower monitoring tool.      | `1`                 |

### Baserow Embeddings Configuration

| Name                                                            | Description                                                     | Value                      |
| --------------------------------------------------------------- | --------------------------------------------------------------- | -------------------------- |
| `baserow-embeddings.enabled`                                    | Set to true to enable the Baserow Embeddings service.           | `false`                    |
| `baserow-embeddings.assistantLLMModel`                          | The LLM model to use for the Embeddings service.                | `groq/openai/gpt-oss-120b` |
| `baserow-embeddings.image.repository`                           | Docker image repository for the Embeddings service.             | `embeddings`               |
| `baserow-embeddings.resources`                                  | Resource requests and limits for the Embeddings service.        |                            |
| `baserow-embeddings.autoscaling.enabled`                        | Enable autoscaling for the Embeddings service.                  | `false`                    |
| `baserow-embeddings.autoscaling.minReplicas`                    | Minimum number of replicas for autoscaling.                     | `1`                        |
| `baserow-embeddings.autoscaling.maxReplicas`                    | Maximum number of replicas for autoscaling.                     | `3`                        |
| `baserow-embeddings.autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization percentage for autoscaling.              | `80`                       |
| `baserow-embeddings.service.port`                               | Service port for the Embeddings service.                        | `80`                       |
| `baserow-embeddings.service.targetPort`                         | Target port for the Embeddings service.                         | `80`                       |
| `baserow-embeddings.readinessProbe.initialDelaySeconds`         | Initial delay for readiness probe.                              | `10`                       |
| `baserow-embeddings.readinessProbe.periodSeconds`               | Period for readiness probe.                                     | `10`                       |
| `baserow-embeddings.readinessProbe.timeoutSeconds`              | Timeout for readiness probe.                                    | `5`                        |
| `baserow-embeddings.livenessProbe.initialDelaySeconds`          | Initial delay for liveness probe.                               | `10`                       |
| `baserow-embeddings.livenessProbe.periodSeconds`                | Period for liveness probe.                                      | `10`                       |
| `baserow-embeddings.livenessProbe.timeoutSeconds`               | Timeout for liveness probe.                                     | `5`                        |
| `baserow-embeddings.pdb.create`                                 | Enable/disable a Pod Disruption Budget creation.                | `false`                    |
| `baserow-embeddings.pdb.minAvailable`                           | Minimum number/percentage of pods that should remain scheduled. | `75%`                      |

### Ingress Configuration

| Name                                              | Description                                | Value                                     |
| ------------------------------------------------- | ------------------------------------------ | ----------------------------------------- |
| `ingress.enabled`                                 | Enable the Ingress resource                | `true`                                    |
| `ingress.annotations.kubernetes.io/ingress.class` | Ingress class annotation                   | `{"kubernetes.io/ingress.class":"caddy"}` |
| `ingress.tls`                                     | TLS configuration for the Ingress resource | `[]`                                      |

### Redis Configuration

| Name                        | Description                                                     | Value        |
| --------------------------- | --------------------------------------------------------------- | ------------ |
| `redis.enabled`             | Enable the Redis database                                       | `true`       |
| `redis.architecture`        | The Redis architecture                                          | `standalone` |
| `redis.auth.enabled`        | Enable Redis authentication                                     | `true`       |
| `redis.auth.password`       | The password for the Redis database                             | `baserow`    |
| `redis.auth.existingSecret` | The name of an existing secret containing the database password | `""`         |

### PostgreSQL Configuration

| Name                             | Description                                                     | Value     |
| -------------------------------- | --------------------------------------------------------------- | --------- |
| `postgresql.enabled`             | Enable the PostgreSQL database                                  | `true`    |
| `postgresql.auth.database`       | The name of the database                                        | `baserow` |
| `postgresql.auth.existingSecret` | The name of an existing secret containing the database password | `""`      |
| `postgresql.auth.password`       | The password for the database                                   | `baserow` |
| `postgresql.auth.username`       | The username for the database                                   | `baserow` |

### Minio Configuration

| Name                                 | Description                                      | Value                                            |
| ------------------------------------ | ------------------------------------------------ | ------------------------------------------------ |
| `minio.enabled`                      | Enable the Minio object storage service          | `true`                                           |
| `minio.networkPolicy.enabled`        | Enable the Minio network policy                  | `false`                                          |
| `minio.disableWebUI`                 | Disable the Minio web UI                         | `true`                                           |
| `minio.provisioning.enabled`         | Enable the Minio provisioning service            | `true`                                           |
| `minio.provisioning.buckets[0].name` | Name of the bucket to create                     | `baserow`                                        |
| `minio.provisioning.extraCommands`   | List of extra commands to run after provisioning | `mc anonymous set download provisioning/baserow` |

### Caddy Configuration

| Name                                                   | Description                                                          | Value                  |
| ------------------------------------------------------ | -------------------------------------------------------------------- | ---------------------- |
| `caddy.enabled`                                        | Enable the Caddy ingress controller                                  | `true`                 |
| `caddy.ingressController.className`                    | Ingress class name which caddy will look for on ingress annotations. | `caddy`                |
| `caddy.ingressController.config.email`                 | Email address to use for Let's Encrypt certificates                  | `my@email.com`         |
| `caddy.ingressController.config.proxyProtocol`         | Enable the PROXY protocol                                            | `true`                 |
| `caddy.ingressController.config.experimentalSmartSort` | Enable experimental smart sorting                                    | `false`                |
| `caddy.ingressController.config.onDemandTLS`           | Enable on-demand TLS                                                 | `true`                 |
| `caddy.ingressController.config.onDemandAsk`           | URL to check for on-demand TLS                                       | `http://:9765/healthz` |
| `caddy.loadBalancer.externalTrafficPolicy`             | External traffic policy for the load balancer                        | `Local`                |
| `caddy.loadBalancer.annotations`                       | Annotations for the load balancer                                    | `{}`                   |
