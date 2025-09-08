# app/services/metrics.py

import logging
import threading
import time
from collections import defaultdict

log = logging.getLogger(__name__)


class Metrics:
    """
    Thread-safe metrics collector for counters, gauges, and simple timers.
    - Counters: monotonically increasing (increment/add)
    - Gauges: set/retrieve instantaneous values
    - Timers: record durations (seconds) via context manager or explicit observe
    """
    __slots__ = ('_lock', '_counters', '_gauges', '_timers_count', '_timers_sum', '_timers_min', '_timers_max')

    def __init__(self):
        self._lock = threading.RLock()
        self._counters = defaultdict(int)
        self._gauges = {}
        self._timers_count = defaultdict(int)
        self._timers_sum = defaultdict(float)
        self._timers_min = {}
        self._timers_max = {}

    # ---- Counters ----

    def increment(self, name, value=1):
        try:
            with self._lock:
                self._counters[str(name)] += int(value)
        except Exception as exc:
            log.error("metrics.increment error for %s: %s", name, exc)

    def add(self, name, value):
        self.increment(name, value)

    def get(self, name):
        with self._lock:
            return self._counters.get(str(name), 0)

    def reset(self, name=None):
        try:
            with self._lock:
                if name is None:
                    self._counters.clear()
                    self._gauges.clear()
                    self._timers_count.clear()
                    self._timers_sum.clear()
                    self._timers_min.clear()
                    self._timers_max.clear()
                else:
                    self._counters.pop(str(name), None)
                    self._gauges.pop(str(name), None)
                    self._timers_count.pop(str(name), None)
                    self._timers_sum.pop(str(name), None)
                    self._timers_min.pop(str(name), None)
                    self._timers_max.pop(str(name), None)
        except Exception as exc:
            log.error("metrics.reset error for %s: %s", name, exc)

    # ---- Gauges ----

    def set_gauge(self, name, value):
        try:
            with self._lock:
                self._gauges[str(name)] = float(value)
        except Exception as exc:
            log.error("metrics.set_gauge error for %s: %s", name, exc)

    def gauge(self, name):
        with self._lock:
            return self._gauges.get(str(name), 0.0)

    # ---- Timers ----

    def observe_timer(self, name, seconds):
        key = str(name)
        try:
            with self._lock:
                self._timers_count[key] += 1
                self._timers_sum[key] += float(seconds)
                mn = self._timers_min.get(key)
                mx = self._timers_max.get(key)
                if mn is None or seconds < mn:
                    self._timers_min[key] = float(seconds)
                if mx is None or seconds > mx:
                    self._timers_max[key] = float(seconds)
        except Exception as exc:
            log.error("metrics.observe_timer error for %s: %s", name, exc)

    class _TimerCtx:
        __slots__ = ('_metrics', '_name', '_start')

        def __init__(self, metrics, name):
            self._metrics = metrics
            self._name = str(name)
            self._start = None

        def __enter__(self):
            self._start = time.perf_counter()
            return self

        def __exit__(self, exc_type, exc, tb):
            end = time.perf_counter()
            self._metrics.observe_timer(self._name, end - self._start)
            # Do not suppress exceptions
            return False

    def timer(self, name):
        """
        Usage:
            with METRICS.timer("rss.fetch"):
                fetch()
        """
        return Metrics._TimerCtx(self, name)

    # ---- Snapshot ----

    def snapshot(self):
        """
        Return a point-in-time snapshot of all metrics.
        Structure:
        {
            "counters": {name: int, ...},
            "gauges": {name: float, ...},
            "timers": {
                name: {"count": n, "sum": s, "avg": a, "min": m, "max": x},
                ...
            }
        }
        """
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            timers = {}
            for k, cnt in self._timers_count.items():
                total = self._timers_sum.get(k, 0.0)
                mn = self._timers_min.get(k)
                mx = self._timers_max.get(k)
                avg = (total / cnt) if cnt else 0.0
                timers[k] = {
                    "count": cnt,
                    "sum": total,
                    "avg": avg,
                    "min": mn if mn is not None else 0.0,
                    "max": mx if mx is not None else 0.0,
                }
            return {
                "counters": counters,
                "gauges": gauges,
                "timers": timers,
            }


# Module-level singleton for convenience across the app
METRICS = Metrics()
__all__ = ("Metrics", "METRICS")
