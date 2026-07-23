#!/usr/bin/env bash

set -euo pipefail

CLUSTER_NAME="troubleshooter"

if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  kind create cluster --name "$CLUSTER_NAME"
else
  echo "Cluster $CLUSTER_NAME already exists"
fi

kubectl create namespace troubleshoot-demo --dry-run=client -o yaml | kubectl apply -f -

kind get kubeconfig --name "$CLUSTER_NAME" --internal > kind-kubeconfig

chmod 644 kind-kubeconfig

NETWORK_EXISTS=$(docker network ls --format '{{.Name}}' | grep -c '^kind$' || true)
if [ "$NETWORK_EXISTS" -eq 0 ]; then
  echo "Warning: kind docker network not found, check your kind version"
fi

echo "Verifying cluster is reachable..."
kubectl --kubeconfig kind-kubeconfig get nodes || {
  echo "kind-kubeconfig cannot reach the cluster yet, this is expected on first run before docker compose attaches to the kind network"
}

cat <<'EOF'

Done. Next steps:
  kubectl get nodes
  kubectl get pods -A
  kubectl apply -f test-scenarios/
  docker compose up --build

  docker-compose.yml already attaches the backend and worker containers to
  the "kind" docker network (created automatically by kind create cluster),
  so no manual "docker network connect" step is needed. If still get connection errors,
  confirm the network exists with:
  docker network ls | grep kind

  If the backend cannot reach the cluster, attach it to the kind network:
  docker network connect kind troubleshooter-backend

EOF
