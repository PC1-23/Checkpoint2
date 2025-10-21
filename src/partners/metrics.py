"""Simple thread-safe in-memory metrics for demo/CI purposes.

Provides a tiny counter store used by the ingest worker to expose counts.
Not intended as a production metrics system; replace with Prometheus client if needed.
"""
from threading import Lock
from typing import Dict

_lock = Lock()
_counters: Dict[str, int] = {
    "enqueued": 0,
    "processed": 0,
    "failed": 0,
    "retried": 0,
}


def incr(name: str, n: int = 1) -> None:
    with _lock:
        _counters.setdefault(name, 0)
        _counters[name] += n


def get_metrics() -> Dict[str, int]:
    with _lock:
        return dict(_counters)
