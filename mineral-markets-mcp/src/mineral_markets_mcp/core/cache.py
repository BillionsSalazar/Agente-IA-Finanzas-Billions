"""Caché TTL en memoria para respuestas de conectores.

Cada método decorado obtiene su propio `TTLCache` (aislado por función), con
tamaño y TTL configurables. Pensado para reducir llamadas repetidas a APIs de
pago/rate-limited dentro de una misma ventana de tiempo, no como caché
persistente entre reinicios del servidor.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from cachetools import TTLCache
from cachetools.keys import hashkey

F = TypeVar("F", bound=Callable[..., Any])


def cached(ttl_seconds: float, maxsize: int = 256) -> Callable[[F], F]:
    def decorator(func: F) -> F:
        store: TTLCache = TTLCache(maxsize=maxsize, ttl=ttl_seconds)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            key = hashkey(*args, **kwargs)
            if key in store:
                return store[key]
            result = func(*args, **kwargs)
            store[key] = result
            return result

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorator
