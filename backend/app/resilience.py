"""Enterprise Resilience & Fault Tolerance Layer for DOIP.

Implements production-grade patterns:
1. Circuit Breaker (CLOSED -> OPEN -> HALF_OPEN states)
2. Exponential Backoff with Jitter Retries
3. Fail-Soft Graceful Degradation & Fallback Handlers
4. Subsystem Health & Recovery Monitoring
"""

from __future__ import annotations

import enum
import functools
import logging
import random
import time
from typing import Any, Callable, Dict, Optional, TypeVar

from app.time_utils import utc_iso

logger = logging.getLogger("doip.resilience")

F = TypeVar("F", bound=Callable[..., Any])


class CircuitState(str, enum.Enum):
    CLOSED = "CLOSED"        # Normal operation: traffic flows through
    OPEN = "OPEN"            # Tripped: fast fail / return fallback
    HALF_OPEN = "HALF_OPEN"  # Testing recovery with canary calls


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is rejected by an open circuit breaker."""

    def __init__(self, breaker_name: str, retry_after_secs: float) -> None:
        super().__init__(
            f"Circuit breaker '{breaker_name}' is OPEN. Retry after {retry_after_secs:.1f}s."
        )
        self.breaker_name = breaker_name
        self.retry_after_secs = retry_after_secs


class CircuitBreaker:
    """Thread-safe circuit breaker protecting services from cascading failure."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count: int = 0
        self.success_count: int = 0
        self.last_failure_time: float = 0.0
        self.last_state_change: float = time.time()
        self.total_tripped_count: int = 0

    def _update_state(self) -> None:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                self.last_state_change = now
                logger.info(
                    "Circuit breaker '%s' transition to HALF_OPEN (probing recovery).",
                    self.name,
                )

    def record_success(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_state_change = time.time()
                logger.info(
                    "Circuit breaker '%s' recovered: transition to CLOSED.", self.name
                )
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self, exc: Exception) -> None:
        self.last_failure_time = time.time()
        self.failure_count += 1
        logger.warning(
            "Circuit breaker '%s' recorded failure (%d/%d): %s",
            self.name,
            self.failure_count,
            self.failure_threshold,
            exc,
        )
        if self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN):
            if self.failure_count >= self.failure_threshold or self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.total_tripped_count += 1
                self.last_state_change = self.last_failure_time
                logger.error(
                    "Circuit breaker '%s' TRIPPED to OPEN. Traffic blocked for %.1fs.",
                    self.name,
                    self.recovery_timeout,
                )

    def can_execute(self) -> bool:
        self._update_state()
        return self.state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)

    def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        fallback: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute callable through circuit breaker guard with optional fallback."""
        if not self.can_execute():
            remaining = max(0.0, self.recovery_timeout - (time.time() - self.last_failure_time))
            if fallback is not None:
                logger.info(
                    "Circuit breaker '%s' OPEN: routing to fallback handler.", self.name
                )
                return fallback(*args, **kwargs)
            raise CircuitBreakerOpenError(self.name, remaining)

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(e)
            if fallback is not None:
                logger.info(
                    "Circuit breaker '%s' failure: routing to fallback handler.", self.name
                )
                return fallback(*args, **kwargs)
            raise

    def get_status(self) -> Dict[str, Any]:
        self._update_state()
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "total_tripped_count": self.total_tripped_count,
            "uptime_in_state_secs": round(time.time() - self.last_state_change, 1),
            "checked_at": utc_iso(),
        }


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    backoff_factor: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """Decorator for exponential backoff retries with full jitter."""

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempts = 0
            delay = base_delay
            while True:
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    attempts += 1
                    if attempts > max_retries:
                        logger.error(
                            "Function '%s' failed after %d retries: %s",
                            func.__name__,
                            max_retries,
                            e,
                        )
                        raise
                    sleep_time = delay
                    if jitter:
                        sleep_time = random.uniform(0, delay)
                    logger.warning(
                        "Retry %d/%d for '%s' after %.3fs due to: %s",
                        attempts,
                        max_retries,
                        func.__name__,
                        sleep_time,
                        e,
                    )
                    time.sleep(sleep_time)
                    delay = min(delay * backoff_factor, max_delay)

        return wrapper  # type: ignore

    return decorator


class ResilienceManager:
    """Central registry of circuit breakers and system resilience policies."""

    _instance: Optional[ResilienceManager] = None

    def __init__(self) -> None:
        self._breakers: Dict[str, CircuitBreaker] = {}
        # Pre-register critical subsystem breakers
        self.get_breaker("llm_inference", failure_threshold=3, recovery_timeout=15.0)
        self.get_breaker("vision_worker", failure_threshold=4, recovery_timeout=20.0)
        self.get_breaker("db_primary", failure_threshold=5, recovery_timeout=10.0)
        self.get_breaker("federation_mesh", failure_threshold=3, recovery_timeout=30.0)

    @classmethod
    def get_instance(cls) -> ResilienceManager:
        if cls._instance is None:
            cls._instance = ResilienceManager()
        return cls._instance

    def get_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> CircuitBreaker:
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
            )
        return self._breakers[name]

    def get_all_status(self) -> Dict[str, Any]:
        return {name: b.get_status() for name, b in self._breakers.items()}

    def reset_breaker(self, name: str) -> bool:
        if name in self._breakers:
            b = self._breakers[name]
            b.state = CircuitState.CLOSED
            b.failure_count = 0
            b.success_count = 0
            return True
        return False

    def reset_all(self) -> None:
        for b in self._breakers.values():
            b.state = CircuitState.CLOSED
            b.failure_count = 0
            b.success_count = 0


# Global singleton
resilience_manager = ResilienceManager.get_instance()
resilience_mgr = resilience_manager
