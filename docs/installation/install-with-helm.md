# Install with Helm

## Official Helm chart

The official Helm chart of Baserow can be found here
https://artifacthub.io/packages/helm/baserow-chart/baserow. By default, it includes
everything you need like PostgreSQL, Redis, MinIO for S3, and Caddy for automatic SSL
certificates. Here you can also documentation for all the configuration possibilities
like using an external PostgreSQL server, how to setup Caddy with various Cloud
providers, add environment variables, and more.

### Prerequisites

Before installing Baserow with Helm, ensure you have:

1. **Kubernetes Cluster**: A running Kubernetes cluster (v1.19+)
2. **Helm**: Helm 3.x installed ([installation guide](https://helm.sh/docs/intro/install/))
3. **kubectl**: Configured to access your cluster
4. **Domains**: Three DNS records (or subdomains) pointing to your cluster:
   - Main domain (e.g., `baserow.example.com`)
   - Backend API domain (e.g., `api.baserow.example.com`)
   - Objects/media domain (e.g., `objects.baserow.example.com`)

### Installation

#### Step 1: Add the Helm repository

First, add the Baserow Helm chart repository:

```bash
helm repo add baserow-chart https://baserow.github.io/baserow-chart
helm repo update
```

#### Step 2: Create configuration file

Create a `config.yaml` file with the minimum configuration that defines the domains
you would like it to run on:

```yaml
global:
  baserow:
    domain: "your-baserow-domain.com"
    backendDomain: "api.your-baserow-domain.com"
    objectsDomain: "objects.your-baserow-domain.com"
```

#### Step 3: Install the chart

To install the chart with the release name `my-baserow`, run:

```bash
helm install my-baserow baserow-chart/baserow \
  --namespace baserow \
  --create-namespace \
  --values config.yaml
```

From source code

```
helm dependency update
helm install my-baserow ./chart/baserow \
  --namespace baserow \
  --create-namespace \
  --values config.yaml
helm upgrade my-baserow ./chart/baserow \
  --namespace baserow \
  --values config.yaml
```

#### Step 4: Verify installation

Check the deployment status:

```bash
# Check pod status
kubectl get pods -n baserow

# Check services
kubectl get services -n baserow

# Check ingress
kubectl get ingress -n baserow
```

Wait for all pods to be in `Running` state. This may take several minutes on first install.

#### Step 5: Access Baserow

Once all pods are running, access Baserow at the domain you configured.

### Upgrading

#### Check current version

Before upgrading, check your current installed version:

```bash
helm list -n baserow
```

#### Update Helm repository

Ensure you have the latest chart versions:

```bash
helm repo update baserow-chart
```

#### Check available versions

To see available chart versions:

```bash
helm search repo baserow-chart/baserow --versions
```

#### Upgrade to latest version

To upgrade to the latest Baserow version using the latest chart:

```bash
helm upgrade my-baserow baserow-chart/baserow \
  --namespace baserow \
  --values config.yaml
```

#### Upgrade to specific version

You can specify a particular Baserow version by updating your `config.yaml`:

```yaml
global:
  baserow:
    image: 2.0.6
```

Or specify the chart version directly:

```bash
helm upgrade my-baserow baserow-chart/baserow \
  --namespace baserow \
  --values config.yaml \
  --version 1.0.36
```

#### Verify upgrade

After upgrading, verify the new version is running:

```bash
# Check pod status
kubectl get pods -n baserow

# Check Baserow version
kubectl logs -n baserow deployment/my-baserow-baserow-backend-wsgi | grep "Baserow"
```

#### Rollback if needed

If the upgrade fails, you can rollback to the previous version:

```bash
# List release history
helm history my-baserow -n baserow

# Rollback to previous revision
helm rollback my-baserow -n baserow

# Or rollback to specific revision
helm rollback my-baserow 1 -n baserow
```

### Configuring AI Features

Baserow supports multiple AI providers for generative AI features and the AI assistant. To enable AI capabilities, you need to configure the embeddings service and AI providers.

#### Enable AI Assistant with Embeddings

Add to your `config.yaml`:

```yaml
baserow-embeddings:
  enabled: true
  assistantLLMModel: "groq/openai/gpt-oss-120b"

backendSecrets:
  GROQ_API_KEY: "your-groq-api-key"
```

#### Configure Additional AI Providers

To enable AI field with multiple providers:

```yaml
backendSecrets:
  # OpenAI
  BASEROW_OPENAI_API_KEY: "sk-..."
  BASEROW_OPENAI_MODELS: "gpt-3.5-turbo,gpt-4o"

  # Anthropic
  BASEROW_ANTHROPIC_API_KEY: "sk-ant-..."
  BASEROW_ANTHROPIC_MODELS: "claude-3-5-sonnet-20241022"

  # Mistral
  BASEROW_MISTRAL_API_KEY: "..."
  BASEROW_MISTRAL_MODELS: "mistral-large-latest"
```

For self-hosted Ollama:

```yaml
backendConfigMap:
  BASEROW_OLLAMA_HOST: "http://ollama-service:11434"
  BASEROW_OLLAMA_MODELS: "llama2,mistral"
```

See the [official Helm chart documentation](https://github.com/baserow/baserow/blob/develop/deploy/helm/baserow/README.md) for detailed AI configuration options.

### Testing Baserow with Minikube

[Minikube](https://minikube.sigs.k8s.io/) is an excellent way to run a local Kubernetes cluster for testing and development. This guide will walk you through setting up Minikube and deploying Baserow using the official Helm chart.

#### Prerequisites

1. Install [Minikube](https://minikube.sigs.k8s.io/docs/start/)
2. Install [Helm](https://helm.sh/docs/intro/install/)
3. Install [kubectl](https://kubernetes.io/docs/tasks/tools/)

#### Step 1: Start Minikube

Start Minikube with recommended resources for Baserow:

```bash
# Start with 4GB RAM and 2 CPUs (adjust based on your system)
minikube start --memory=4096 --cpus=2

# Verify cluster is running
kubectl cluster-info
kubectl get nodes
```

#### Step 2: Enable required addons

Enable the ingress addon for routing traffic:

```bash
minikube addons enable ingress

# Verify ingress controller is running
kubectl get pods -n ingress-nginx
```

#### Step 3: Configure local DNS

For local testing, you'll need to configure local DNS or use `/etc/hosts`. Get your Minikube IP:

```bash
minikube ip
```

Add entries to your `/etc/hosts` file (replace `<MINIKUBE_IP>` with the actual IP):

```bash
<MINIKUBE_IP> baserow.local
<MINIKUBE_IP> api.baserow.local
<MINIKUBE_IP> objects.baserow.local
```

#### Step 4: Create Baserow configuration

Create a `config.yaml` file for local testing:

```yaml
global:
  baserow:
    domain: "baserow.local"
    backendDomain: "api.baserow.local"
    objectsDomain: "objects.baserow.local"

# Disable Caddy since we're using Minikube ingress
caddy:
  enabled: false

# Use smaller resource requests for local testing
baserow-backend-wsgi:
  resources:
    requests:
      memory: "256Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"

baserow-backend-asgi:
  resources:
    requests:
      memory: "256Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"

baserow-frontend:
  resources:
    requests:
      memory: "256Mi"
      cpu: "100m"
    limits:
      memory: "512Mi"
      cpu: "500m"

# Configure ingress for Minikube
ingress:
  enabled: true
  className: "nginx"
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
```

#### Step 5: Install Baserow

Add the Baserow Helm repository and install:

```bash
# Add Baserow chart repository
helm repo add baserow-chart https://baserow.github.io/baserow-chart
helm repo update

# Install Baserow
helm install baserow baserow-chart/baserow \
  --namespace baserow \
  --create-namespace \
  --values config.yaml
```

#### Step 6: Monitor deployment

Watch the pods come up:

```bash
# Watch all pods
kubectl get pods -n baserow -w

# Check deployment status
kubectl get deployments -n baserow

# Check services
kubectl get services -n baserow

# Check ingress
kubectl get ingress -n baserow
```

Wait until all pods show `Running` status. This may take 5-10 minutes on first deployment.

#### Step 7: Access Baserow

Once all pods are running, access Baserow at:
- Frontend: http://baserow.local
- API: http://api.baserow.local
- Objects: http://objects.baserow.local

#### Step 8: Test the deployment

```bash
# Port-forward to access directly (alternative to ingress)
kubectl port-forward -n baserow svc/baserow-baserow-frontend 8000:80

# Access at http://localhost:8000
```

#### Troubleshooting

**Pods not starting:**
```bash
# Check pod logs
kubectl logs -n baserow <pod-name>

# Describe pod for events
kubectl describe pod -n baserow <pod-name>
```

**Out of resources:**
```bash
# Increase Minikube resources
minikube stop
minikube delete
minikube start --memory=8192 --cpus=4
```

**Ingress not working:**
```bash
# Check ingress controller
kubectl get pods -n ingress-nginx

# Check ingress configuration
kubectl describe ingress -n baserow
```

#### Cleanup

When done testing, you can clean up:

```bash
# Uninstall Baserow
helm uninstall baserow -n baserow

# Delete namespace
kubectl delete namespace baserow

# Stop Minikube
minikube stop

# Delete Minikube cluster
minikube delete
```


## Alternative Community Maintained Helm Chart

Find the community Baserow [helm chart here](https://artifacthub.io/packages/helm/christianhuth/baserow)
maintained by [Christian Huth](https://github.com/christianhuth).

We recommend that you:

1. Run the chart with ingress enabled:
    1. `backend.ingress.enabled=true`
    2. `frontend.ingress.enabled=true`
2. Make sure you configure two domains, one for the backend api API one for the frontend
   server.
    1. Set `config.publicFrontendUrl=https://your-baserow-servers-domain.com`
    2. Set `config.publicBackendUrl=https://api.your-baserow-servers-domain.com`
3. Configure all the relevant `backend.config.aws` variables to upload and serve user
   files in a S3 compatible service of your own choosing.
