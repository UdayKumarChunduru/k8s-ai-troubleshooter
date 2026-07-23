#!/usr/bin/env bash

set -euo pipefail

CLUSTER_NAME="troubleshooter"

if ! kind get clusters | grep -q "^${CLUSTER_NAME}$"; then
  kind create cluster --name "$CLUSTER_NAME" --config - <<'EOF'
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  apiServerAddress: "0.0.0.0"
nodes:
  - role: control-plane
EOF
else
  echo "Cluster $CLUSTER_NAME already exists"
fi

kubectl create namespace troubleshoot-demo --dry-run=client -o yaml | kubectl apply -f -

kubectl config set-context --current --namespace=troubleshoot-demo

kind get kubeconfig --name "$CLUSTER_NAME" | python3 -c "
import sys
print(sys.stdin.read().replace('127.0.0.1', 'host.docker.internal'))
" > kind-kubeconfig

chmod 644 kind-kubeconfig

echo "Verifying the cluster is reachable from the host..."
kubectl get nodes

cat <<'EOF'

Done. Next steps:
  kubectl get nodes
  kubectl get pods -A
  kubectl apply -f test-scenarios/
  docker compose up --build

  kind-kubeconfig points at host.docker.internal, which only resolves
  inside a container that has the extra_hosts entry docker-compose.yml
  already sets (host.docker.internal:host-gateway). It will NOT resolve
  from the host shell; for host-side access, use the normal kubeconfig
  (kubectl already works against it because kind configures it
  automatically).

  docker-compose.yml already attaches the backend and worker containers to
  the "kind" docker network (created automatically by kind create cluster),
  so no manual "docker network connect" step is needed. If connection errors
  still occur, confirm the network exists with:
  docker network ls | grep kind

  If the backend cannot reach the cluster, attach it to the kind network:
  docker network connect kind troubleshooter-backend
EOF
