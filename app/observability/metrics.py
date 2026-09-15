"""
Observability helpers for Voxevia.

This module provides simple application metrics and timing helpers.

The goal is to measure:
- operation duration
- successful operations
- failed operations

This module does not store permanent business data.
Permanent call information remains in Supabase.
"""

import time
from contextlib import contextmanager
from typing import Iterator

from app.observability.logging_config import get_logger


logger = get_logger("metrics")


@contextmanager
def measure_time(
    operation: str,
    call_id: str | None = None,
) -> Iterator[None]:
    """
    Measure how long an operation takes.

    Example:

        with measure_time("patient_lookup", call_id):
            ...

    A structured log is generated when the operation finishes.
    """

    if not operation.strip():
        raise ValueError(
            "operation cannot be empty."
        )

    start_time = time.perf_counter()

    try:
        yield

    except Exception as exc:
        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.error(
            "operation_failed",
            operation=operation,
            call_id=call_id,
            duration_ms=round(duration_ms, 2),
            error=str(exc),
        )

        raise

    else:
        duration_ms = (
            time.perf_counter() - start_time
        ) * 1000

        logger.info(
            "operation_completed",
            operation=operation,
            call_id=call_id,
            duration_ms=round(duration_ms, 2),
        )