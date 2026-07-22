"""Reintentos con backoff exponencial (tenacity) para llamadas a APIs externas.

No reintenta `ConnectorNotConfiguredError` (no es un fallo transitorio) ni
`SymbolNotFoundError` (reintentar no cambia el resultado) — solo errores de
red/API (`ConnectorAPIError`, `httpx` transport errors).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from mineral_markets_mcp.core.exceptions import ConnectorAPIError

F = TypeVar("F", bound=Callable)

RETRYABLE_EXCEPTIONS = (ConnectorAPIError, httpx.TransportError, httpx.TimeoutException)


def with_retry(max_attempts: int = 3) -> Callable[[F], F]:
    return retry(
        reraise=True,
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
        retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
    )
