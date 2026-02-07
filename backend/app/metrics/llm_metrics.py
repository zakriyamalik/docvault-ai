# app/metrics/llm_metrics.py

try:
    from prometheus_client import Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Define dummy classes for type hints
    Counter = None
    Histogram = None


class NoOpCounter:
    """No-op counter for when prometheus is not available."""
    def __init__(self, *args, **kwargs):
        pass
    
    def labels(self, **kwargs):
        return self
    
    def inc(self, amount=1):
        pass


class NoOpHistogram:
    """No-op histogram for when prometheus is not available."""
    def __init__(self, *args, **kwargs):
        pass
    
    def labels(self, **kwargs):
        return self
    
    def observe(self, amount):
        pass
    
    def time(self):
        """Context manager that does nothing."""
        from contextlib import contextmanager
        
        @contextmanager
        def dummy_timer():
            yield
        
        return dummy_timer()


# Define metrics (real or no-op based on availability)
if PROMETHEUS_AVAILABLE:
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
else:
    # Use no-op implementations
    LLM_QUERY_COUNT = NoOpCounter()
    LLM_RESPONSE_TIME = NoOpHistogram()


def record_metric(name: str, value: float = 1, labels: dict = None):
    """
    Record a metric. Silently does nothing if prometheus is not available.
    
    Args:
        name: Metric name ('llm_query_count' or 'llm_response_time')
        value: Value to record
        labels: Dict of label values (must include 'provider')
    """
    labels = labels or {}
    
    # Silently skip if prometheus not available
    if not PROMETHEUS_AVAILABLE:
        return
    
    if name == 'llm_query_count':
        LLM_QUERY_COUNT.labels(**labels).inc(value)
    elif name == 'llm_response_time':
        LLM_RESPONSE_TIME.labels(**labels).observe(value)
    else:
        raise ValueError(f"Unknown metric name: {name}")