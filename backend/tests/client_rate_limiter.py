"""In-process stand-in for the Redis bootstrap limiter, for single-process tests."""

from collections import deque
from threading import Lock
from time import monotonic


class InMemoryClientRateLimiter:
    """Track a bounded number of attempts per client in a sliding time window."""

    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts_by_client: dict[str, deque[float]] = {}
        self._lock = Lock()

    async def allow(self, client_address: str) -> bool:
        """Record an allowed attempt, or reject when the client's window is full."""
        now = monotonic()
        with self._lock:
            attempts = self._attempts_by_client.setdefault(client_address, deque())
            while attempts and attempts[0] <= now - self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.max_attempts:
                return False
            attempts.append(now)
            return True
