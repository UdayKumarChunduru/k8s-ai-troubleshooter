import os

from kubernetes import client, config

LOG_TAIL_LINES = int(os.environ.get("LOG_TAIL_LINES", "60"))


def _load_config():
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config(config_file=os.environ.get("KUBECONFIG"))


def collect(namespace: str, deployment: str | None = None) -> dict:
    _load_config()
    core = client.CoreV1Api()
    apps = client.AppsV1Api()

    evidence = {"namespace": namespace, "deployments": [], "pods": [], "events": []}

    deps = apps.list_namespaced_deployment(namespace).items
    if deployment:
        deps = [d for d in deps if d.metadata.name == deployment]
    for d in deps:
        evidence["deployments"].append({
            "name": d.metadata.name,
            "desired": d.spec.replicas,
            "ready": d.status.ready_replicas or 0,
            "conditions": [
                {"type": c.type, "status": c.status, "message": c.message}
                for c in (d.status.conditions or [])
            ],
        })

    pods = core.list_namespaced_pod(namespace).items
    for pod in pods:
        pod_info = {
            "name": pod.metadata.name,
            "phase": pod.status.phase,
            "containers": [],
        }
        for cs in pod.status.container_statuses or []:
            state = {}
            if cs.state.waiting:
                state = {"state": "waiting", "reason": cs.state.waiting.reason,
                         "message": cs.state.waiting.message}
            elif cs.state.terminated:
                state = {"state": "terminated", "reason": cs.state.terminated.reason,
                         "exit_code": cs.state.terminated.exit_code}
            elif cs.state.running:
                state = {"state": "running"}

            last_state = {}
            if cs.last_state and cs.last_state.terminated:
                last_state = {"reason": cs.last_state.terminated.reason,
                              "exit_code": cs.last_state.terminated.exit_code}

            container = {
                "name": cs.name,
                "restarts": cs.restart_count,
                "current": state,
                "last_terminated": last_state,
                "logs": "",
                "previous_logs": "",
            }

            healthy = state.get("state") == "running" and cs.restart_count == 0
            if not healthy:
                container["logs"] = _logs(core, namespace, pod.metadata.name, cs.name, previous=False)
                if cs.restart_count > 0:
                    container["previous_logs"] = _logs(core, namespace, pod.metadata.name, cs.name, previous=True)

            pod_info["containers"].append(container)
        evidence["pods"].append(pod_info)

    events = core.list_namespaced_event(namespace).items
    for ev in events[-30:]:
        if ev.type != "Normal":
            evidence["events"].append({
                "reason": ev.reason,
                "message": ev.message,
                "object": f"{ev.involved_object.kind}/{ev.involved_object.name}",
                "count": ev.count,
            })

    return evidence


def _logs(core, namespace, pod, container, previous):
    try:
        return core.read_namespaced_pod_log(
            name=pod, namespace=namespace, container=container,
            tail_lines=LOG_TAIL_LINES, previous=previous,
        )
    except client.ApiException:
        return ""
