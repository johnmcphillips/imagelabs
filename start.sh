#!/bin/bash
set -e
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Building Docker image ...\n${NC}"
docker build -t thumbnail-proc:latest .

echo -e "${GREEN}Creating kind cluster ...\n${NC}"
kind create cluster --name cogent --config kind-config.yaml

echo -e "${GREEN}Loading Docker image into kind cluster ...\n${NC}"
kind load docker-image thumbnail-proc:latest --name cogent

echo -e "${GREEN}Installing Prometheus + Grafana ...\n${NC}"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
#helm repo add grafana https://grafana.github.io/helm-charts
#helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f values-prometheus.yaml 2>/dev/null

# helm install loki grafana/loki-stack \
#   --namespace monitoring \
#   --set grafana.enabled=false \
#   --set loki.isDefaultDatasource=false

# helm install ingress-nginx ingress-nginx/ingress-nginx \
#   --namespace ingress-nginx --create-namespace
# sleep 30

echo -e "${GREEN}Installing Image Processing Helm chart ...\n${NC}"
helm upgrade --install thumbnail-proc ./helm/thumbnail-proc
echo -e "${GREEN}Sleep for deployments...\n${NC}"
sleep 15 # TODO (if pods are not ready, wait)


echo -e "${GREEN}Get Grafana admin password ...\n${NC}"
echo "http://localhost:3000"
echo "Username: admin"
echo -n "Password: "
kubectl --namespace monitoring get secrets monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo

echo -e "${GREEN}Sleep for pods...\n${NC}"
sleep 15 # TODO (if pods are not ready, wait)

echo -e "${GREEN}Setting up port forwarding ...\n${NC}"
kubectl port-forward svc/thumbnail-proc-api 8080:8080 &
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090
#kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80
