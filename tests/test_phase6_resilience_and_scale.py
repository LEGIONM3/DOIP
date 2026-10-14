"""Phase 6 Comprehensive Test Suite: Resilience, Caching & Scalability.

Tests:
- Circuit Breaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Exponential backoff retry decorators with jitter
- CacheManager TTL expiration, LRU eviction, and namespace isolation
- BatchProcessor high-throughput buffering and flushes
- StreamPartitioner deterministic key distribution
- ScalabilityBenchmark high-throughput performance validation
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.resilience import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    retry_with_backoff,
    resilience_manager,
)
from app.cache import CacheManager, cached
from app.scalability import BatchProcessor, StreamPartitioner, ScalabilityBenchmark


# ---------------------------------------------------------------------------
# 1. Circuit Breaker Tests
# ---------------------------------------------------------------------------
def test_circuit_breaker_normal_execution():
    cb = CircuitBreaker(name="test_cb_normal", failure_threshold=3, recovery_timeout=0.2)
    assert cb.state == CircuitState.CLOSED

    res = cb.execute(lambda x: x * 2, 5)
    assert res == 10
    assert cb.failure_count == 0


def test_circuit_breaker_trip_and_recovery():
    cb = CircuitBreaker(name="test_cb_trip", failure_threshold=2, recovery_timeout=0.1, half_open_max_calls=2)

    def failing_call():
        raise ValueError("Service unavailable")

    # First failure
    with pytest.raises(ValueError):
        cb.execute(failing_call)
    assert cb.failure_count == 1
    assert cb.state == CircuitState.CLOSED

    # Second failure trips breaker to OPEN
    with pytest.raises(ValueError):
        cb.execute(failing_call)
    assert cb.state == CircuitState.OPEN
    assert cb.total_tripped_count == 1

    # Call while OPEN without fallback raises CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        cb.execute(lambda: "should not run")

    # Call while OPEN with fallback returns fallback result
    fallback_res = cb.execute(lambda: "should not run", fallback=lambda: "degraded_fallback")
    assert fallback_res == "degraded_fallback"

    # Wait for recovery timeout to transition to HALF_OPEN
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN

    # Two successful canary calls restore CLOSED state
    r1 = cb.execute(lambda: "canary_1")
    assert r1 == "canary_1"
    assert cb.state == CircuitState.HALF_OPEN

    r2 = cb.execute(lambda: "canary_2")
    assert r2 == "canary_2"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


# ---------------------------------------------------------------------------
# 2. Exponential Backoff Retry Tests
# ---------------------------------------------------------------------------
def test_retry_with_backoff_success_after_transient():
    call_counts = {"count": 0}

    @retry_with_backoff(max_retries=3, base_delay=0.01, max_delay=0.05, jitter=False)
    def flaky_service():
        call_counts["count"] += 1
        if call_counts["count"] < 3:
            raise ConnectionError("Transient network glitch")
        return "SUCCESS"

    result = flaky_service()
    assert result == "SUCCESS"
    assert call_counts["count"] == 3


def test_retry_with_backoff_exhaustion():
    @retry_with_backoff(max_retries=2, base_delay=0.01, max_delay=0.02, jitter=False)
    def permanent_failure():
        raise RuntimeError("Permanent failure")

    with pytest.raises(RuntimeError):
        permanent_failure()


# ---------------------------------------------------------------------------
# 3. High-Throughput Cache Tests
# ---------------------------------------------------------------------------
def test_cache_manager_lru_and_ttl():
    cache = CacheManager(max_size_per_namespace=3)

    # Set and get
    cache.set("key1", "val1", namespace="test_ns")
    assert cache.get("key1", namespace="test_ns") == "val1"
    assert cache.get("nonexistent", namespace="test_ns") is None

    # TTL expiration
    cache.set("ttl_key", "expiring", namespace="test_ns", ttl=0.05)
    assert cache.get("ttl_key", namespace="test_ns") == "expiring"
    time.sleep(0.08)
    assert cache.get("ttl_key", namespace="test_ns") is None

    # LRU eviction test (capacity = 3)
    cache.clear("test_ns")
    cache.set("a", 1, namespace="test_ns")
    cache.set("b", 2, namespace="test_ns")
    cache.set("c", 3, namespace="test_ns")
    # Access 'a' so 'b' becomes least recently used
    _ = cache.get("a", namespace="test_ns")
    # Inserting 'd' must evict 'b'
    cache.set("d", 4, namespace="test_ns")
    assert cache.get("a", namespace="test_ns") == 1
    assert cache.get("b", namespace="test_ns") is None  # Evicted
    assert cache.get("c", namespace="test_ns") == 3
    assert cache.get("d", namespace="test_ns") == 4

    stats = cache.get_stats()
    assert stats["hits"] > 0
    assert stats["evictions"] >= 1


def test_cached_decorator():
    invocations = {"count": 0}

    @cached(namespace="math_test", ttl=10.0)
    def compute_heavy(n: int) -> int:
        invocations["count"] += 1
        return n * n

    val1 = compute_heavy(5)
    val2 = compute_heavy(5)
    assert val1 == 25
    assert val2 == 25
    assert invocations["count"] == 1  # Second call served from cache


# ---------------------------------------------------------------------------
# 4. Scalability & Batch Processing Tests
# ---------------------------------------------------------------------------
def test_batch_processor():
    flushed_batches = []
    processor = BatchProcessor(
        batch_size=5,
        flush_interval_secs=0.5,
        flush_handler=lambda batch: flushed_batches.append(batch),
    )

    for i in range(12):
        processor.add(f"item_{i}")
    processor.flush()

    assert processor.total_processed == 12
    assert len(flushed_batches) == 3
    assert len(flushed_batches[0]) == 5
    assert len(flushed_batches[1]) == 5
    assert len(flushed_batches[2]) == 2


def test_stream_partitioner():
    partitioner = StreamPartitioner(num_partitions=4)

    pid1 = partitioner.route("UNIT-ALPHA", {"speed": 40})
    pid2 = partitioner.route("UNIT-ALPHA", {"speed": 42})
    # Same key routes to same partition
    assert pid1 == pid2

    items = partitioner.consume(pid1, max_items=10)
    assert len(items) == 2
    assert items[0]["key"] == "UNIT-ALPHA"


def test_scalability_benchmark_throughput():
    result = ScalabilityBenchmark.benchmark_batch_throughput(num_items=5000)
    assert result["status"] == "PASS"
    assert result["total_items"] == 5000
    assert result["throughput_items_per_sec"] > 5000  # High-throughput threshold
