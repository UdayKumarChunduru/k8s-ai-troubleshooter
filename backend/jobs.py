import logging

import analyzer
import k8s_collector
import llm_client
import storage

logger = logging.getLogger(__name__)


def run_investigation(inv_id: int, namespace: str, deployment: str | None):
    try:
        storage.update_investigation(inv_id, status="collecting")
        evidence = k8s_collector.collect(namespace, deployment)

        pattern = analyzer.detect_pattern(evidence)
        storage.update_investigation(inv_id, status="analyzing", failure_pattern=pattern)

        if pattern == "healthy":
            storage.update_investigation(
                inv_id, status="done",
                root_cause="All containers in the namespace are running with zero restarts. Nothing to fix.",
                confidence=95, fix_commands=[],
            )
            return

        result = llm_client.analyze(evidence, pattern)
        storage.update_investigation(
            inv_id, status="done",
            root_cause=result["root_cause"],
            confidence=result["confidence"],
            fix_commands=result["fix_commands"],
        )
        logger.info("Investigation %d done, pattern %s, confidence %d",
                    inv_id, pattern, result["confidence"])

    except Exception as exc:
        logger.exception("Investigation %d failed", inv_id)
        storage.update_investigation(inv_id, status="failed", error=str(exc))
