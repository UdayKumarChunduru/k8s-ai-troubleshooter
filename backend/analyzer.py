def detect_pattern(evidence: dict) -> str:
    waiting_reasons = []
    terminated_reasons = []

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

    if "OOMKilled" in terminated_reasons:
        return "OOMKilled"
    if any(r in ("ImagePullBackOff", "ErrImagePull") for r in waiting_reasons):
        return "ImagePullBackOff"
    if "CrashLoopBackOff" in waiting_reasons:
        return "CrashLoopBackOff"

    all_running = all(
        c.get("current", {}).get("state") == "running"
        for pod in evidence.get("pods", [])
        for c in pod.get("containers", [])
    )
    if evidence.get("pods") and all_running:
        return "healthy"
    return "unhealthy"
