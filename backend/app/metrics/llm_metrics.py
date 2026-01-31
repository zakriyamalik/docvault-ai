from prometheus_client import Counter, Histogram

# Define explicit metrics with labels
LLM_QUERY_COUNT = Counter(
    'llm_query_count',
    'Number of LLM queries processed',
    ['provider']
)

LLM_RESPONSE_TIME = Histogram(
    'llm_response_time_seconds',
    'LLM response time in seconds',
    ['provider']
)

def record_metric(name: str, value: float = 1, labels: dict = None):
    labels = labels or {}
    if name == 'llm_query_count':
        LLM_QUERY_COUNT.labels(**labels).inc(value)
    elif name == 'llm_response_time':
        LLM_RESPONSE_TIME.labels(**labels).observe(value)
    else:
        raise ValueError(f"Unknown metric name: {name}")
