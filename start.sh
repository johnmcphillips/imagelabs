#!/bin/bash
set -e
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

SMOKE_TEST=false
for arg in "$@"; do
  if [ "$arg" == "--smoke-test" ]; then
    SMOKE_TEST=true
  fi
done

printf "${GREEN}Building Docker image ...\n${NC}"
docker build -t thumbnail-proc:latest .
printf "\n"

printf "${GREEN}Creating kind cluster ...\n${NC}"
kind create cluster --name cogent --config kind-config.yaml
printf "\n"

kubectl cluster-info --context kind-cogent
printf "\n"

printf "${GREEN}Loading Docker image into kind cluster ...\n${NC}"
kind load docker-image thumbnail-proc:latest --name cogent
printf "\n"

printf "${GREEN}Installing Prometheus + Grafana ...\n${NC}"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm install monitoring prometheus-community/kube-prometheus-stack \
  --namespace monitoring --create-namespace \
  -f values-prometheus.yaml 2>/dev/null
printf "\n"

printf "${GREEN}Installing Image Processing Helm chart ...\n${NC}"
helm upgrade --install thumbnail-proc ./helm/thumbnail-proc
printf "\n"

printf "${GREEN}Sleep for Thumbnail API pods ...\n${NC}"
kubectl get pods -n default -w &
WATCH_PID=$!
kubectl wait --for=condition=available --timeout=120s deployment --all -n default
kill $WATCH_PID
printf "\n"
sleep 2

printf "${GREEN}Sleep for Prometheus + Grafana pods ...\n${NC}"
kubectl get pods -n monitoring -w &
WATCH_PID=$!
kubectl wait --for=condition=Ready --timeout=120s pod --all -n monitoring
kill $WATCH_PID
printf "\n"
sleep 2

printf "${GREEN}Thumbnail Processor OpenAPI Docs:${NC} http://localhost:30080/docs\n"
printf "${GREEN}Metrics Exposure:${NC} http://localhost:30080/metrics\n"
printf "${GREEN}Prometheus:${NC} http://localhost:9090\n"
printf "${GREEN}Grafana Dashboard:${NC} http://localhost:3000\n"
echo "Username: admin"
echo -n "Password: "
kubectl --namespace monitoring get secrets monitoring-grafana -o jsonpath="{.data.admin-password}" | base64 -d ; echo

printf "${GREEN}\nStarting port forwarding ...\n${NC}"
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80 >/dev/null 2>&1 &
KUBE_PID+=("$!")
kubectl port-forward -n monitoring svc/monitoring-kube-prometheus-prometheus 9090:9090 >/dev/null 2>&1 &
KUBE_PID+=("$!")
printf "${GREEN}\nPort forwarding running ...\n${NC}${RED} Press Ctrl-C to stop and delete cluster.\n${NC}"

shutdown() {
  printf "${GREEN}\nCtrl-C Detected. Shutting down port forwarding and deleting kind cluster ...\n${NC}"
  for pid in "${KUBE_PID[@]}"; do
    kill "$pid" || true
  done
  kind delete cluster --name cogent || true
  exit 0
}
trap shutdown SIGINT SIGTERM SIGSTOP SIGQUIT

# Execute smoke test if flagged
if [ "$SMOKE_TEST" = true ]; then
  printf "${RED}\nFlag --smoke-test enabled detected. Executing test script at test/test.sh ...\n${NC}"
  printf "${RED}\nRunning smoke test: "$2" jobs. Check Grafana for performance.\n${NC}"
  bash test/test.sh "$2" >test/smoke_test.log 2>&1 || true
  tail -n 20 test/smoke_test.log
  printf "${GREEN}\nSmoke test completed. Full log at test/smoke_test.log\n${NC}"
fi

wait
