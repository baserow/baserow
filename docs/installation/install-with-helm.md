# Install with Helm

## Official Helm chart

The official Helm chart of Baserow can be found here
https://artifacthub.io/packages/helm/baserow-chart/baserow. By default, it includes
everything you need like PostgreSQL, Redis, MinIO for S3, and Caddy for automatic SSL
certificates. Here you can also documentation for all the configuration possibilities
like using an external PostgreSQL server, how to setup Caddy with various Cloud
providers, add environment variables, and more.

### Installation

Create a `config.yaml` file with the minimum configuration that defines the domains
you would like it to run on.

```
global:
  baserow:
    domain: "your-baserow-domain.com"
    backendDomain: "api.your-baserow-domain.com"
    objectsDomain: "objects.your-baserow-domain.com"
```

To install the chart with the release name `my-baserow` run the following commands:

```
helm repo add baserow-chart https://baserow.gitlab.io/baserow-chart
helm install my-baserow baserow-chart/baserow --namespace baserow --create-namespace --values config.yaml
```

### Upgrading

You can change the Baserow version you're running by updating your `config.yaml`
file directly.

```
global:
  baserow:
    image: 1.30.1
```

Or use the latest Helm chart default. Then run the following command to upgrade your
installation.

```
helm upgrade my-baserow baserow-chart/baserow --namespace baserow --values config.yaml
```

## Community Maintained Helm Chart

Find the community
Baserow [helm chart here](https://artifacthub.io/packages/helm/christianhuth/baserow)
maintained
by [Christian Huth](https://github.com/christianhuth).

We recommend that you:

1. Run the chart with ingress enabled:
    2. `backend.ingress.enabled=true`
    3. `frontend.ingress.enabled=true`
4. Make sure you configure two domains, one for the backend api API one for the frontend
   server.
    5. Set `config.publicFrontendUrl=https://your-baserow-servers-domain.com`
    5. Set `config.publicBackendUrl=https://api.your-baserow-servers-domain.com`
6. Configure all the relevant `backend.config.aws` variables to upload and serve user
   files in a S3 compatible service of your own choosing.

### Deploying Baserow using Helm and K3S

[K3S](https://k3s.io/) is an easy way of getting a local K8S cluster running locally for
testing and development. This guide will walk you through setting it K3S with Baserow
using the community helm chart above.

1. Install [K3S](https://docs.k3s.io/quick-start)
2. Install [Helm](https://helm.sh/docs/helm/helm_install/)
3. Configure Helm to use your K3S cluster:

```bash
# From https://devops.stackexchange.com/questions/16043/error-error-loading-config-file-etc-rancher-k3s-k3s-yaml-open-etc-rancher 
export KUBECONFIG=~/.kube/config
mkdir ~/.kube 2> /dev/null
# Make sure you aren't overriding an existing k8s configuration in ~/.kube/config
(set -o noclobber; sudo k3s kubectl config view --raw > "$KUBECONFIG")
chmod 600 "$KUBECONFIG"
# Check you can access the cluster
helm ls --all-namespaces
# You should see something like
# NAME	NAMESPACE	REVISION	UPDATED	STATUS	CHART	APP VERSION
```

4. Install Baserow using Helm

```bash
helm repo add christianknell https://christianknell.github.io/helm-charts
helm repo update
helm install 1.5.3 christianknell/baserow
# Finally follow the printed instructions.
```
