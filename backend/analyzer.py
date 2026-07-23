WAITING_ORDER = [
    ("ImagePullBackOff", ("ImagePullBackOff", "ErrImagePull")),
    ("ConfigError", ("CreateContainerConfigError",)),
    ("CrashLoopBackOff", ("CrashLoopBackOff",)),
]


def detect_pattern(evidence: dict) -> str:
    waiting_reasons = []
    terminated_reasons = []
    not_ready_containers = []

    for pod in evidence.get("pods", []):
        for c in pod.get("containers", []):
            current = c.get("current", {})
            if current.get("state") == "waiting" and current.get("reason"):
                waiting_reasons.append(current["reason"])
            if current.get("state") == "terminated" and current.get("reason"):
                terminated_reasons.append(current["reason"])
            last = c.get("last_terminated", {})
            if last.get("reason"):
                terminated_reasons.append(last["reason"])
            if c.get("ready") is False and current.get("state") == "running":
                not_ready_containers.append(c)

    init_waiting_reasons = []
    init_terminated_bad = False
    for pod in evidence.get("pods", []):
        for ic in pod.get("init_containers", []):
            current = ic.get("current", {})
            if current.get("state") == "waiting" and current.get("reason"):
                init_waiting_reasons.append(current["reason"])
            if current.get("state") == "terminated" and current.get("exit_code", 0) not in (0, None):
                init_terminated_bad = True

    event_reasons = [ev.get("reason", "") for ev in evidence.get("events", [])]
    event_messages = " ".join(ev.get("message", "") or "" for ev in evidence.get("events", []))

    if init_terminated_bad or any(
        r in ("CrashLoopBackOff", "Error") for r in init_waiting_reasons
    ):
        return "InitContainerError"

    if "OOMKilled" in terminated_reasons:
        return "OOMKilled"

    if "Evicted" in event_reasons or any(
        pod.get("phase") == "Failed" and pod.get("reason") == "Evicted"
        for pod in evidence.get("pods", [])
    ):
        return "Evicted"

    node_not_ready_hints = ("node is not ready", "nodenotready", "node was not ready")
    if _has_event(evidence, ("NodeNotReady", "TaintManagerEviction"), ()) or any(
        h in event_messages.lower() for h in node_not_ready_hints
    ):
        return "NodeNotReady"

    for pod in evidence.get("pods", []):
        if pod.get("phase") == "Pending":
            if _has_event(evidence, ("FailedScheduling",), ("Insufficient cpu", "Insufficient memory")):
                return "Pending/ResourcePressure"
            selector_hints = ("node(s) didn't match", "node affinity",
                              "didn't match pod's node affinity", "node(s) had taint")
            if _has_event(evidence, ("FailedScheduling",), selector_hints):
                return "Pending/NodeSelector"
            if _has_event(evidence, ("FailedScheduling",), ()):
                return "Pending/ResourcePressure"

    if _has_event(evidence, ("FailedMount", "FailedAttachVolume"), ()):
        return "FailedMount"

    pdb_hints = ("PodDisruptionBudget", "disruption budget")
    if _has_event(evidence, ("FailedCreate", "FailedRollout"), pdb_hints):
        return "PodDisruptionBudget"

    has_liveness_event = _has_event(evidence, ("Unhealthy",), ("Liveness probe failed",))
    has_readiness_event = _has_event(evidence, ("Unhealthy",), ("Readiness probe failed",))
    has_restarts = any(
        c.get("restarts", 0) > 0 for pod in evidence.get("pods", []) for c in pod.get("containers", [])
    )
    if has_liveness_event and has_restarts:
        return "LivenessProbe"
    if has_readiness_event or (not_ready_containers and _has_event(evidence, ("Unhealthy",), ())):
        return "ReadinessProbe"

    for reason, triggers in WAITING_ORDER:
        if any(r in triggers for r in waiting_reasons):
            return reason

    hpa_reasons = ("FailedGetScale", "FailedComputeMetricsReplicas", "InvalidMetricSourceType")
    if _has_event(evidence, hpa_reasons, ()):
        return "HPA/ScalingFailed"
    if "metrics server" in event_messages.lower() or "unable to get metrics" in event_messages.lower():
        return "HPA/ScalingFailed"

    all_running = all(
        c.get("current", {}).get("state") == "running"
        for pod in evidence.get("pods", [])
        for c in pod.get("containers", [])
    )
    if evidence.get("pods") and all_running and not not_ready_containers:
        return "healthy"
    return "unhealthy"


def _has_event(evidence: dict, reasons: tuple, message_substrings: tuple) -> bool:
    for ev in evidence.get("events", []):
        reason = ev.get("reason") or ""
        message = (ev.get("message") or "").lower()
        if reasons and reason not in reasons:
            continue
        if message_substrings:
            if any(sub.lower() in message for sub in message_substrings):
                return True
        elif reasons:
            return True
    return False
