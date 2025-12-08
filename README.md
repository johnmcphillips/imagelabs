# ImageLabs

Thumbnail creation assignment

User can submit an image to an API endpoint. \
The API should:

- Save the original image
- Initiate long-running job to generate 100x100 thumbnail
- User recieves job ID as response

User should be able to:

- Check job status (processing, succeeded, failed)
- Fetch the thumbnail once succeeded
- List all submitted jobs
- Fetch debugging logs, metrics, monitoring

## Reasoning

## Architecture

## Automated Setup
This will run through Docker, Kind, and Helm installations
```bash
./start.sh
```
Clean up
```kind
kind delete cluster --name cogent
```

## Manual Setup

- Build the Python FastAPI services

```docker
docker build -t thumbnail-proc:latest .
```

- Create Kind Cluster

```kind
kind create cluster --name cogent --config kind-config.yaml
```

- Load Image

```kind
kind load docker-image thumbnail-proc:latest --name cogent
```

- Install Thumbnail Processor Helm chart

```helm
helm upgrade --install thumbnail-proc ./helm/thumbnail-proc
```

- Install Prometheus + Grafana
```helm
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f values-prometheus.yaml
```

- Port forward to svc

```kubectl
kubectl port-forward svc/thumbnail-proc-api 8080:8080 &
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090
```
