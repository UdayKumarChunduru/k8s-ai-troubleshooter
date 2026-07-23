from prometheus_client import Counter, Histogram

investigation_total = Counter(
    "investigation_total",
    "Investigations completed, by outcome and detected failure pattern",
    ["status", "pattern"],
)

investigation_duration_seconds = Histogram(
    "investigation_duration_seconds",
    "End to end time from job start to done/failed, in seconds",
)

llm_call_duration_seconds = Histogram(
    "llm_call_duration_seconds",
    "Time spent waiting on the LLM provider, in seconds",
    ["provider"],
)

llm_call_errors_total = Counter(
    "llm_call_errors_total",
    "LLM calls that raised an exception, by provider",
    ["provider"],
)


def record_investigation(status: str, pattern: str, duration_seconds: float):
    investigation_total.labels(status=status, pattern=pattern).inc()
    investigation_duration_seconds.observe(duration_seconds)


def record_llm_duration(provider: str, duration_seconds: float):
    llm_call_duration_seconds.labels(provider=provider).observe(duration_seconds)


def record_llm_error(provider: str):
    llm_call_errors_total.labels(provider=provider).inc()
