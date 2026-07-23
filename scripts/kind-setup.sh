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

NETWORK_EXISTS=$(docker network ls --format '{{.Name}}' | grep -c '^kind$' || true)
if [ "$NETWORK_EXISTS" -eq 0 ]; then
  echo "Warning: kind docker network not found, check your kind version"
fi

cat <<'EOF'

Done. Next steps:
  kubectl get nodes
  kubectl get pods -A
  kubectl apply -f test-scenarios/
  docker compose up --build

  If the backend cannot reach the cluster, attach it to the kind network:
  docker network connect kind troubleshooter-backend

EOF
