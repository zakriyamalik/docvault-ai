# app/llm/circuit_breaker.py
import time
from typing import Dict

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_time: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_time = recovery_time  # seconds
        self.failure_count: Dict[str, int] = {}
        self.last_failure_time: Dict[str, float] = {}

    def record_failure(self, provider: str):
        self.failure_count[provider] = self.failure_count.get(provider, 0) + 1
        self.last_failure_time[provider] = time.time()

    def can_call(self, provider: str) -> bool:
        count = self.failure_count.get(provider, 0)
        last_time = self.last_failure_time.get(provider, 0)

        if count < self.failure_threshold:
            return True

        if time.time() - last_time > self.recovery_time:
            # reset after recovery time
            self.failure_count[provider] = 0
            return True

        return False

    def record_success(self, provider: str):
        self.failure_count[provider] = 0
        self.last_failure_time[provider] = 0

    def is_open(self, provider: str) -> bool:
        """Return True if the circuit is currently open for the given provider."""
        return not self.can_call(provider)


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open and calls are blocked."""
    pass
