import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import analyzer  # noqa: E402


def _pod(containers, phase="Running", reason=None):
    return {"name": "p", "phase": phase, "reason": reason, "containers": containers}


def _container(state="running", reason=None, restarts=0, ready=True, last_reason=None):
    current = {"state": state}
    if reason:
        current["reason"] = reason
    return {
        "name": "c",
        "restarts": restarts,
        "ready": ready,
        "current": current,
        "last_terminated": {"reason": last_reason} if last_reason else {},
    }


def test_oomkilled():
    evidence = {
        "pods": [_pod([_container(state="waiting", reason="CrashLoopBackOff",
                                   restarts=3, last_reason="OOMKilled")])],
        "events": [],
    }
    assert analyzer.detect_pattern(evidence) == "OOMKilled"


def test_imagepullbackoff():
    evidence = {
        "pods": [_pod([_container(state="waiting", reason="ImagePullBackOff")])],
        "events": [],
    }
    assert analyzer.detect_pattern(evidence) == "ImagePullBackOff"


def test_errimagepull_maps_to_imagepullbackoff():
    evidence = {
        "pods": [_pod([_container(state="waiting", reason="ErrImagePull")])],
        "events": [],
    }
    assert analyzer.detect_pattern(evidence) == "ImagePullBackOff"


def test_crashloopbackoff():
    evidence = {
        "pods": [_pod([_container(state="waiting", reason="CrashLoopBackOff", restarts=5)])],
        "events": [],
    }
    assert analyzer.detect_pattern(evidence) == "CrashLoopBackOff"


def test_pending_resource_pressure():
    evidence = {
        "pods": [_pod([], phase="Pending")],
        "events": [
            {"reason": "FailedScheduling",
             "message": "0/3 nodes are available: 3 Insufficient cpu.",
             "object": "Pod/p", "count": 1}
        ],
    }
    assert analyzer.detect_pattern(evidence) == "Pending/ResourcePressure"


def test_pending_node_selector():
    evidence = {
        "pods": [_pod([], phase="Pending")],
        "events": [
            {"reason": "FailedScheduling",
             "message": "0/3 nodes are available: 3 node(s) didn't match Pod's node affinity/selector.",
             "object": "Pod/p", "count": 1}
        ],
    }
    assert analyzer.detect_pattern(evidence) == "Pending/NodeSelector"


def test_evicted():
    evidence = {
        "pods": [_pod([], phase="Failed", reason="Evicted")],
        "events": [],
    }
    assert analyzer.detect_pattern(evidence) == "Evicted"


def test_readiness_probe():
    evidence = {
        "pods": [_pod([_container(state="running", ready=False)])],
        "events": [
            {"reason": "Unhealthy", "message": "Readiness probe failed: HTTP probe failed with code 500",
             "object": "Pod/p", "count": 4}
        ],
    }
    assert analyzer.detect_pattern(evidence) == "ReadinessProbe"


def test_liveness_probe():
    evidence = {
        "pods": [_pod([_container(state="running", restarts=2)])],
        "events": [
            {"reason": "Unhealthy", "message": "Liveness probe failed: Get http://10.0.0.1:8080/healthz: dial tcp timeout",
             "object": "Pod/p", "count": 6}
        ],
    }
    assert analyzer.detect_pattern(evidence) == "LivenessProbe"


def test_pod_disruption_budget():
    evidence = {
        "pods": [_pod([_container()])],
        "events": [
            {"reason": "FailedRollout", "message": "Cannot evict pod as it would violate the pod's disruption budget.",
             "object": "Deployment/app", "count": 1}
        ],
    }
    assert analyzer.detect_pattern(evidence) == "PodDisruptionBudget"


def test_hpa_scaling_failed():
    evidence = {
        "pods": [_pod([_container()])],
        "events": [
            {"reason": "FailedGetScale", "message": "unable to fetch metrics from resource metrics API",
             "object": "HorizontalPodAutoscaler/app", "count": 3}
        ],
    }
    assert analyzer.detect_pattern(evidence) == "HPA/ScalingFailed"


def test_healthy():
    evidence = {
        "pods": [_pod([_container()])],
        "events": [],
    }
    assert analyzer.detect_pattern(evidence) == "healthy"


def test_unhealthy_fallback():
    evidence = {
        "pods": [_pod([_container(state="terminated", reason="Error")])],
        "events": [],
    }
    assert analyzer.detect_pattern(evidence) == "unhealthy"
