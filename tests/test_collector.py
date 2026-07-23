import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import k8s_collector  # noqa: E402


def _container_status(name="app", waiting=None, terminated=None, running=None,
                       restart_count=0, ready=True, last_terminated=None):
    return SimpleNamespace(
        name=name,
        restart_count=restart_count,
        ready=ready,
        state=SimpleNamespace(waiting=waiting, terminated=terminated, running=running),
        last_state=SimpleNamespace(terminated=last_terminated) if last_terminated else SimpleNamespace(terminated=None),
    )


@patch("k8s_collector.config")
@patch("k8s_collector.client")
def test_collect_returns_pods_and_deployments(mock_client_module, mock_config):
    mock_core = MagicMock()
    mock_apps = MagicMock()
    mock_client_module.CoreV1Api.return_value = mock_core
    mock_client_module.AppsV1Api.return_value = mock_apps
    mock_client_module.ApiException = Exception

    mock_apps.list_namespaced_deployment.return_value = SimpleNamespace(items=[
        SimpleNamespace(
            metadata=SimpleNamespace(name="web"),
            spec=SimpleNamespace(replicas=3),
            status=SimpleNamespace(ready_replicas=1, conditions=[]),
        )
    ])

    waiting = SimpleNamespace(reason="CrashLoopBackOff", message="back-off restarting failed container")
    pod = SimpleNamespace(
        metadata=SimpleNamespace(name="web-abc123"),
        status=SimpleNamespace(
            phase="Running",
            reason=None,
            container_statuses=[_container_status(waiting=waiting, restart_count=4, ready=False)],
        ),
        spec=SimpleNamespace(node_selector=None),
    )
    mock_core.list_namespaced_pod.return_value = SimpleNamespace(items=[pod])
    mock_core.list_namespaced_event.return_value = SimpleNamespace(items=[])
    mock_core.read_namespaced_pod_log.return_value = "log line"

    evidence = k8s_collector.collect("default")

    assert evidence["namespace"] == "default"
    assert evidence["deployments"][0]["name"] == "web"
    assert evidence["deployments"][0]["ready"] == 1
    assert evidence["pods"][0]["containers"][0]["current"]["reason"] == "CrashLoopBackOff"
    assert evidence["pods"][0]["containers"][0]["logs"] == "log line"


@patch("k8s_collector.config")
@patch("k8s_collector.client")
def test_collect_filters_by_deployment_name(mock_client_module, mock_config):
    mock_core = MagicMock()
    mock_apps = MagicMock()
    mock_client_module.CoreV1Api.return_value = mock_core
    mock_client_module.AppsV1Api.return_value = mock_apps
    mock_client_module.ApiException = Exception

    mock_apps.list_namespaced_deployment.return_value = SimpleNamespace(items=[
        SimpleNamespace(metadata=SimpleNamespace(name="web"), spec=SimpleNamespace(replicas=1),
                        status=SimpleNamespace(ready_replicas=1, conditions=[])),
        SimpleNamespace(metadata=SimpleNamespace(name="worker"), spec=SimpleNamespace(replicas=1),
                        status=SimpleNamespace(ready_replicas=1, conditions=[])),
    ])
    mock_core.list_namespaced_pod.return_value = SimpleNamespace(items=[])
    mock_core.list_namespaced_event.return_value = SimpleNamespace(items=[])

    evidence = k8s_collector.collect("default", deployment="worker")

    assert len(evidence["deployments"]) == 1
    assert evidence["deployments"][0]["name"] == "worker"


@patch("k8s_collector.config")
def test_collect_uses_named_context(mock_config):
    with patch("k8s_collector.client") as mock_client_module:
        mock_core = MagicMock()
        mock_apps = MagicMock()
        mock_client_module.CoreV1Api.return_value = mock_core
        mock_client_module.AppsV1Api.return_value = mock_apps
        mock_apps.list_namespaced_deployment.return_value = SimpleNamespace(items=[])
        mock_core.list_namespaced_pod.return_value = SimpleNamespace(items=[])
        mock_core.list_namespaced_event.return_value = SimpleNamespace(items=[])

        k8s_collector.collect("default", cluster_context="prod-cluster")

        mock_config.load_kube_config.assert_called_once()
        _, kwargs = mock_config.load_kube_config.call_args
        assert kwargs.get("context") == "prod-cluster"
