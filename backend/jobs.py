import logging
import os
import time

import analyzer
import k8s_collector
import llm_client
import storage

logger = logging.getLogger(__name__)

REDIS_URL = os.environ.get("REDIS_URL")

_queue = None
if REDIS_URL:
    try:
        from redis import Redis
        from rq import Queue, Retry

        _redis_conn = Redis.from_url(REDIS_URL)
        _queue = Queue("investigations", connection=_redis_conn)
        _retry = Retry(max=3, interval=[10, 30, 60])
    except Exception:
        logger.exception("REDIS_URL set but rq/redis unavailable, falling back to BackgroundTasks")
        _queue = None


def enqueue(background_tasks, inv_id: int, namespace: str, deployment: str | None,
            cluster_context: str | None = None):
    if _queue is not None:
        _queue.enqueue(run_investigation, inv_id, namespace, deployment, cluster_context, retry=_retry)
    else:
        background_tasks.add_task(run_investigation, inv_id, namespace, deployment, cluster_context)


def run_investigation(
    inv_id: int, namespace: str, deployment: str | None, cluster_context: str | None = None
):

    import metrics

    start = time.monotonic()
    try:
        storage.update_investigation(inv_id, status="collecting")
        evidence = k8s_collector.collect(namespace, deployment, cluster_context)

        pattern = analyzer.detect_pattern(evidence)
        storage.update_investigation(inv_id, status="analyzing", failure_pattern=pattern)

        if pattern == "healthy":
            storage.update_investigation(
                inv_id, status="done",
                root_cause="All containers in the namespace are running with zero restarts. Nothing to fix.",
                confidence=95, fix_commands=[],
            )
            metrics.record_investigation("done", pattern, time.monotonic() - start)
            return

        llm_start = time.monotonic()
        try:
            result = llm_client.analyze(evidence, pattern)
        except Exception:
            metrics.record_llm_error(os.environ.get("LLM_PROVIDER", "openrouter"))
            raise
        finally:
            metrics.record_llm_duration(
                os.environ.get("LLM_PROVIDER", "openrouter"), time.monotonic() - llm_start
            )

        storage.update_investigation(
            inv_id, status="done",
            root_cause=result["root_cause"],
            confidence=result["confidence"],
            fix_commands=result["fix_commands"],
        )
        metrics.record_investigation("done", pattern, time.monotonic() - start)
        logger.info("Investigation %d done, pattern %s, confidence %d",
                    inv_id, pattern, result["confidence"])

    except Exception as exc:
        logger.exception("Investigation %d failed", inv_id)
        storage.update_investigation(inv_id, status="failed", error=str(exc))
        metrics.record_investigation("failed", "unknown", time.monotonic() - start)
        raise
