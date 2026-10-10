"""Bounded retries for local Ollama calls, and a safe classification of provider errors.

Provider error bodies can contain request details, so they are read here only to
pick a category and a retry delay; neither the body nor the message is ever stored.
"""
import math
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable

RETRYABLE_CODES = (429, 408, 500, 502, 503, 504)


def retry_after(value, now: datetime | None = None) -> float | None:
    """Parse a Retry-After value given as seconds or an HTTP date; None if unusable."""
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = (parsedate_to_datetime(value) - (now or datetime.now(timezone.utc))).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0, seconds) if math.isfinite(seconds) else None


def error_metadata(exc: BaseException) -> dict:
    """Classify local HTTP failures without retaining response bodies or exception messages."""
    code = getattr(exc, 'code', None)
    code = code if isinstance(code, int) else None
    headers = getattr(exc, 'headers', {}) or {}
    return dict(error_code=code,
                error_kind='temporary_server_error' if code in RETRYABLE_CODES else 'non_retryable_error',
                retry_after_seconds=retry_after(headers.get('Retry-After')))


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 1    # including the first call
    base_delay: float = 2
    max_delay: float = 30
    max_wait: float = 120    # total backoff per document; pacing between documents is separate
    pace: float = 0         # minimum seconds between request starts

    def __post_init__(self):
        if self.max_attempts < 1 or self.max_attempts > 20:
            raise ValueError('max_attempts must be 1–20')
        delays = (self.base_delay, self.max_delay, self.max_wait, self.pace)
        if any(not math.isfinite(v) or v < 0 for v in delays):
            raise ValueError('Retry delays must be finite and nonnegative')
        if self.base_delay > self.max_delay:
            raise ValueError('base_delay must not exceed max_delay')

    def backoff(self, attempt: int, uniform: Callable[[float, float], float]) -> float:
        """Exponential backoff with jitter in the upper half of the window."""
        ceiling = min(self.max_delay, self.base_delay * 2 ** (attempt - 1))
        return uniform(ceiling / 2, ceiling)


def run_with_retry(call: Callable[[], dict], policy: RetryPolicy, sleep=time.sleep, uniform=random.uniform,
                   on_attempt: Callable[[dict], None] = lambda attempt: None) -> dict:
    """Call until success, a non-retryable error, a stop condition or the budget runs out.

    Returns the last result with the attempt log, total wait and total request time added;
    `stop_reason` is set when the whole run should stop rather than move to the next document.
    """
    attempts, waited = [], 0.0
    for number in range(1, policy.max_attempts + 1):
        result = call()
        attempt = dict(number=number, error=result.get('error'), error_code=result.get('error_code'),
                       error_kind=result.get('error_kind'), seconds=result['seconds'], wait_after_seconds=0)
        attempts.append(attempt)
        on_attempt(attempt)
        if not result['error']:
            break
        stop = None
        if result.get('error_code') not in RETRYABLE_CODES:
            break
        elif number == policy.max_attempts:
            if result.get('error_code') == 429:
                stop = 'rate_limit_retry_budget_exhausted'
        else:
            # Never wait less than the provider asked for, and never past the per-document budget.
            delay = max(policy.backoff(number, uniform), result.get('retry_after_seconds') or 0)
            if waited + delay > policy.max_wait:
                stop = 'server_retry_after_exceeds_wait_budget'
            else:
                attempt['wait_after_seconds'] = delay
                on_attempt(attempt)
                sleep(delay)
                waited += delay
                continue
        if stop:
            result['stop_reason'] = stop
        break
    result['attempts'] = attempts
    result['retry_wait_seconds'] = waited
    result['request_seconds'] = sum(a['seconds'] for a in attempts)
    return result
