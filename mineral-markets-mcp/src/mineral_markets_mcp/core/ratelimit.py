"""Limitador de tasa simple (token bucket) por conector, thread-safe.

Suficiente para respetar los límites de llamadas/segundo de las APIs premium
sin depender de un servicio externo (Redis, etc.) — el servidor corre como un
único proceso por sesión MCP.
"""

from __future__ import annotations

import threading
import time


class RateLimiter:
    def __init__(self, calls_per_second: float) -> None:
        self._min_interval = 1.0 / calls_per_second if calls_per_second > 0 else 0.0
        self._lock = threading.Lock()
        self._last_call = 0.0

    def acquire(self) -> None:
        if self._min_interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_call
            wait_time = self._min_interval - elapsed
            if wait_time > 0:
                time.sleep(wait_time)
            self._last_call = time.monotonic()
