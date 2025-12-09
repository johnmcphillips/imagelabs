#!/bin/bash
set -e
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Building Docker image ...${NC}"
docker build -t thumbnail-proc:latest .
echo -e "\n"

echo -e "${GREEN}Creating kind cluster ...${NC}"
kind create cluster --name cogent --config kind-config.yaml
echo -e "\n"

kubectl cluster-info --context kind-cogent
echo -e "\n"

echo -e "${GREEN}Loading Docker image into kind cluster ...${NC}"
kind load docker-image thumbnail-proc:latest --name cogent
echo -e "\n"

echo -e "${GREEN}Installing Prometheus + Grafana ...${NC}"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add traefik https://traefik.github.io/charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f values-prometheus.yaml 2>/dev/null
echo -e "\n"

echo -e "${GREEN}Installing Image Processing Helm chart ...${NC}"
helm upgrade --install thumbnail-proc ./helm/thumbnail-proc
echo -e "\n"

echo -e "${GREEN}Sleep for Thumbnail API pods ...${NC}"
kubectl get pods -n default -w &
WATCH_PID=$!
kubectl wait --for=condition=available --timeout=120s deployment --all -n default
kill $WATCH_PID
echo -e "\n"

echo -e "${GREEN}Sleep for Prometheus + Grafana pods ...${NC}"
kubectl get pods -n monitoring -w &
WATCH_PID=$!
kubectl wait --for=condition=Ready --timeout=120s pod -l app.kubernetes.io/name=prometheus -n monitoring
kill $WATCH_PID
echo -e "\n"

echo -e "${GREEN}Thumbnail Processor OpenAPI Docs:${NC} http://localhost:8080/docs"
echo -e "${GREEN}Metrics Exposure:${NC} http://localhost:8080/metrics"
echo -e "${GREEN}Prometheus:${NC} http://localhost:9090"
echo -e "${GREEN}Grafana Dashboard:${NC} http://localhost:3000"
echo "Username: admin"
echo -n "Password: "
kubectl --namespace monitoring get secrets monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo

echo -e "${GREEN}\nStarting port forwarding ...${NC}"
kubectl port-forward svc/thumbnail-proc 8080:8080 &
KUBE_PID=("$!")
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 &
KUBE_PID+=("$!")
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 &
KUBE_PID+=("$!")

shutdown() {
  echo -e "${GREEN}\nCtrl-C Detected. Shutting down port forwarding and deleting kind cluster ...${NC}"
  for pid in "${KUBE_PID[@]}"; do
    kill "$pid" || true
  done
  kind delete cluster --name cogent || true
  exit 0
}
trap shutdown SIGINT SIGTERM

echo -e "${GREEN}Port forwarding running. Press Ctrl-C to stop and delete cluster.${NC}"

wait
