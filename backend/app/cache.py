"""High-Throughput In-Memory Caching Engine for DOIP.

Provides LRU eviction, TTL expiration, namespace segregation,
and thread-safe fast access for tactical routing, vector retrieval,
and graph traversals.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger("doip.cache")


class CacheEntry:
    """Internal cache entry wrapper with access metadata."""

    __slots__ = ("value", "expires_at", "last_accessed", "hits", "access_seq")

    def __init__(self, value: Any, ttl: Optional[float] = None, access_seq: int = 0) -> None:
        self.value = value
        now = time.time()
        self.expires_at = (now + ttl) if ttl is not None else None
        self.last_accessed = now
        self.access_seq = access_seq
        self.hits = 0

    def is_expired(self) -> bool:
        return self.expires_at is not None and time.time() > self.expires_at


class CacheManager:
    """Thread-safe LRU/TTL Cache with namespace partitioning."""

    _instance: Optional[CacheManager] = None

    def __init__(self, max_size_per_namespace: int = 1000) -> None:
        self.max_size = max_size_per_namespace
        self._stores: Dict[str, Dict[str, CacheEntry]] = {}
        self._lock = threading.Lock()
        self._seq: int = 0
        self._stats: Dict[str, Dict[str, int]] = {
            "global": {"hits": 0, "misses": 0, "evictions": 0, "sets": 0}
        }

    @classmethod
    def get_instance(cls) -> CacheManager:
        if cls._instance is None:
            cls._instance = CacheManager()
        return cls._instance

    def _get_namespace_store(self, namespace: str) -> Dict[str, CacheEntry]:
        if namespace not in self._stores:
            self._stores[namespace] = {}
        return self._stores[namespace]

    def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """Retrieve cached value if present and unexpired."""
        with self._lock:
            store = self._get_namespace_store(namespace)
            entry = store.get(key)
            if entry is None:
                self._stats["global"]["misses"] += 1
                return None

            if entry.is_expired():
                del store[key]
                self._stats["global"]["misses"] += 1
                return None

            self._seq += 1
            entry.last_accessed = time.time()
            entry.access_seq = self._seq
            entry.hits += 1
            self._stats["global"]["hits"] += 1
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        namespace: str = "default",
        ttl: Optional[float] = None,
    ) -> None:
        """Store value with optional TTL and LRU eviction if full."""
        with self._lock:
            self._seq += 1
            store = self._get_namespace_store(namespace)
            if len(store) >= self.max_size and key not in store:
                # Evict entry with smallest access_seq
                lru_key = min(store.keys(), key=lambda k: store[k].access_seq)
                del store[lru_key]
                self._stats["global"]["evictions"] += 1

            store[key] = CacheEntry(value, ttl=ttl, access_seq=self._seq)
            self._stats["global"]["sets"] += 1

    def delete(self, key: str, namespace: str = "default") -> bool:
        with self._lock:
            store = self._get_namespace_store(namespace)
            if key in store:
                del store[key]
                return True
            return False

    def clear(self, namespace: Optional[str] = None) -> None:
        with self._lock:
            if namespace:
                if namespace in self._stores:
                    self._stores[namespace].clear()
            else:
                self._stores.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_entries = sum(len(s) for s in self._stores.values())
            hits = self._stats["global"]["hits"]
            misses = self._stats["global"]["misses"]
            total_reqs = hits + misses
            hit_ratio = round(hits / total_reqs, 3) if total_reqs > 0 else 0.0

            return {
                "total_entries": total_entries,
                "namespaces": list(self._stores.keys()),
                "hits": hits,
                "misses": misses,
                "hit_ratio": hit_ratio,
                "evictions": self._stats["global"]["evictions"],
                "total_sets": self._stats["global"]["sets"],
            }

    stats = get_stats


def cached(namespace: str = "default", ttl: Optional[float] = 60.0) -> Callable:
    """Function memoization decorator using CacheManager."""

    def decorator(func: Callable) -> Callable:
        cache = CacheManager.get_instance()

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key_parts = [func.__name__] + [str(a) for a in args] + [f"{k}={v}" for k, v in sorted(kwargs.items())]
            cache_key = ":".join(key_parts)

            cached_val = cache.get(cache_key, namespace=namespace)
            if cached_val is not None:
                return cached_val

            result = func(*args, **kwargs)
            cache.set(cache_key, result, namespace=namespace, ttl=ttl)
            return result

        return wrapper

    return decorator


# Global singleton
cache_manager = CacheManager.get_instance()
cache_mgr = cache_manager
