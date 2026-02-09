# Install with K8S

## Official Baserow Helm Chart

We recommend you use the [official baserow helm chart](./install-with-helm.md) to
install Baserow on K8S.

## Raw K8S starting point

See below for a starting point for a K8S configuration file which deploys a production
ready Baserow.

It assumes you want the most performant version of Baserow possible and
so deploys separate wsgi and asgi backend services, separate async task workers etc.

You will need to also provide a redis and postgres instance configured using the
environment variables below. See [Configuring Baserow](./configuration.md) for more
details on these variables.

You should also set up and configure Baserow to use an S3 compatible storage service
for uploading and serving user uploaded files.

## Example baserow.yml

```yaml
# A secret containing all the required Baserow settings.
apiVersion: v1
kind: Secret
metadata:
  name: YOUR_ENV_SECRET_REF
type: Opaque
stringData:
  SECRET_KEY: "TODO"
  PRIVATE_BACKEND_URL: "http://backend-wsgi"
  PUBLIC_BACKEND_URL: "TODO"
  PUBLIC_WEB_FRONTEND_URL: "TODO"
  DATABASE_HOST: "TODO"
  DATABASE_USER: "TODO"
  DATABASE_PASSWORD: "TODO"
  DATABASE_PORT: "TODO"
  DATABASE_NAME: "TODO"
  REDIS_HOST: "TODO"
  REDIS_PORT: "TODO"
  REDIS_USER: "TODO"
  REDIS_PASSWORD: "TODO"
  REDIS_PROTOCOL: "TODO rediss or redis"
  BASEROW_AMOUNT_OF_GUNICORN_WORKERS: "5"
  # S3 Compatible storage is recommended with K8S to get the exports and file storage working
  # See the docs for more info https://baserow.io/docs/installation%2Fconfiguration#user-file-upload-configuration
  AWS_ACCESS_KEY_ID: "TODO"
  AWS_SECRET_ACCESS_KEY: "TODO"
  AWS_STORAGE_BUCKET_NAME: "TODO"

# An example ingress controller routing to the correct services
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: balancer
  annotations:
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "route"
    nginx.ingress.kubernetes.io/session-cookie-expires: "172800"
    nginx.ingress.kubernetes.io/session-cookie-max-age: "172800"
    nginx.ingress.kubernetes.io/proxy-body-size: 20m
    kubernetes.io/ingress.class: nginx
    # removed ssl settings, add in your own desired ones
spec:
  # TODO a tsl block
  rules:
    - host: REPLACE_WITH_YOUR_BACKEND_HOST
      http:
        paths:
          - pathType: Prefix
            path: "/ws/"
            backend:
              service:
                name: backend-asgi
                port:
                  number: 80
          - pathType: Prefix
            path: "/"
            backend:
              service:
                name: backend-wsgi
                port:
                  number: 80
    - host: REPLACE_WITH_YOUR_WEB_FRONTEND_HOST
      http:
        paths:
          - pathType: Prefix
            path: "/"
            backend:
              service:
                name: web-frontend
                port:
                  number: 80

---
apiVersion: v1
kind: Service
metadata:
  name: backend-asgi
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8000
  selector:
    app: backend-asgi
---
apiVersion: v1
kind: Service
metadata:
  name: backend-wsgi
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 8000
  selector:
    app: backend-wsgi
---
apiVersion: v1
kind: Service
metadata:
  name: web-frontend
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: 3000
  selector:
    app: web-frontend

# The backend ASGI worker handling websockets
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend-asgi
  labels:
    app: backend-asgi
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend-asgi
  template:
    metadata:
      labels:
        app: backend-asgi
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 1
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - backend-asgi
                topologyKey: "kubernetes.io/hostname"
      containers:
        - name: backend-asgi
          image: baserow/backend:2.0.6
          workingDir: /baserow
          args:
            - "gunicorn"
          ports:
            - containerPort: 8000
              name: backend-asgi
          imagePullPolicy: Always
          readinessProbe:
            exec:
              command:
                - curl
                - --fail
                - --silent
                - http://localhost:8000/api/_health/
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 5
            successThreshold: 1
          envFrom:
            - secretRef:
                name: YOUR_ENV_SECRET_REF
      imagePullSecrets:
        - name: YOUR_PULL_SECRETS

# The backend WSGI worker handling normal http api requests 
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend-wsgi
  labels:
    app: backend-wsgi
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend-wsgi
  template:
    metadata:
      labels:
        app: backend-wsgi
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 1
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - backend-wsgi
                topologyKey: "kubernetes.io/hostname"
      containers:
        - name: backend-wsgi
          image: baserow/backend:2.0.6
          workingDir: /baserow
          args:
            - "gunicorn-wsgi"
            - "--timeout"
            - "60"
          ports:
            - containerPort: 8000
              name: backend-wsgi
          imagePullPolicy: Always
          readinessProbe:
            exec:
              command:
                - curl
                - --fail
                - --silent
                - http://localhost:8000/api/_health/
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 5
            successThreshold: 1
          envFrom:
            - secretRef:
                name: YOUR_ENV_SECRET_REF
      imagePullSecrets:
        - name: YOUR_PULL_SECRETS
# A set of celery workers handling realtime events, cleanup, async tasks etc. 
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: backend-worker
  labels:
    app: backend-worker
spec:
  replicas: 2
  selector:
    matchLabels:
      app: backend-worker
  template:
    metadata:
      labels:
        app: backend-worker
    spec:
      # Set affinities to ensure the different replicas end up on different nodes.
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 1
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - backend-worker
                topologyKey: "kubernetes.io/hostname"
      containers:
        - name: backend-worker
          image: baserow/backend:2.0.6
          args:
            - "celery-worker"
          imagePullPolicy: Always
          readinessProbe:
            exec:
              command:
                - /bin/bash
                - -c
                - /baserow/backend/docker/docker-entrypoint.sh celery-worker-healthcheck
            initialDelaySeconds: 10
            timeoutSeconds: 10
            periodSeconds: 10
          envFrom:
            - secretRef:
                name: YOUR_ENV_SECRET_REF
        - name: backend-export-worker
          image: baserow/backend:2.0.6
          args:
            - "celery-exportworker"
          imagePullPolicy: Always
          readinessProbe:
            exec:
              command:
                - /bin/bash
                - -c
                - /baserow/backend/docker/docker-entrypoint.sh celery-exportworker-healthcheck
            initialDelaySeconds: 10
            timeoutSeconds: 10
            periodSeconds: 10
          envFrom:
            - secretRef:
                name: YOUR_ENV_SECRET_REF
        - name: backend-beat-worker
          image: baserow/backend:2.0.6
          args:
            - "celery-beat"
          imagePullPolicy: Always
          envFrom:
            - secretRef:
                name: YOUR_ENV_SECRET_REF
      imagePullSecrets:
        - name: YOUR_PULL_SECRETS
# A web-frontend SSR server which renders the initial html/js when a client visits.
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-frontend
  labels:
    app: web-frontend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-frontend
  template:
    metadata:
      labels:
        app: web-frontend
    spec:
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 1
              podAffinityTerm:
                labelSelector:
                  matchExpressions:
                    - key: app
                      operator: In
                      values:
                        - web-frontend
                topologyKey: "kubernetes.io/hostname"
      containers:
        - name: web-frontend
          image: baserow/web-frontend:2.0.6
          args:
            - nuxt
          ports:
            - containerPort: 3000
              name: web-frontend
          imagePullPolicy: Always
          readinessProbe:
            httpGet:
              path: /_health
              port: 3000
            initialDelaySeconds: 5
            periodSeconds: 5
            successThreshold: 1
          envFrom:
            - secretRef:
                name: YOUR_ENV_SECRET_REF
      imagePullSecrets:
        - name: YOUR_PULL_SECRETS
```
