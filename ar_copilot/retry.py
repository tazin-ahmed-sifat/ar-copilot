"""Bounded retries and safe classification of provider error metadata."""
import math
import re
import json
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

def retry_after(value, now=None):
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        try:
            seconds = (parsedate_to_datetime(value) - (now or datetime.now(timezone.utc))).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return None
    return max(0, seconds) if math.isfinite(seconds) else None

def error_metadata(exc):
    """Inspect privately; persist only categories/numbers, never exception bodies."""
    code = getattr(exc, 'code', None)
    code = code if isinstance(code, int) else None
    body = getattr(exc, 'details', {})
    body = body if isinstance(body, dict) else {}
    error = body.get('error', body)
    private_text = json.dumps(error).lower() + str(getattr(exc, 'message', '')).lower()
    response = getattr(exc, 'response', None)
    headers = getattr(response, 'headers', {}) or {}
    delay = retry_after(headers.get('Retry-After') or headers.get('retry-after'))
    details = error.get('details', []) if isinstance(error, dict) else []
    for detail in details:
        if isinstance(detail, dict) and 'RetryInfo' in detail.get('@type', ''):
            raw = detail.get('retryDelay')
            if isinstance(raw, str) and raw.endswith('s'):
                hint = retry_after(raw[:-1])
            elif isinstance(raw, dict):
                hint = retry_after(float(raw.get('seconds', 0)) + float(raw.get('nanos', 0))/1e9)
            else:
                hint = None
            if hint is not None:
                delay = max(delay or 0, hint)
    if code == 429:
        if any(word in private_text for word in ('perday', 'per_day', 'daily', 'quota_exceeded')):
            kind = 'daily_quota_exhausted'
        elif re.search(r'limit\s*[:=]\s*0\b|"quotavalue"\s*:\s*"?0\b', private_text):
            kind = 'zero_quota'
        else:
            kind = 'temporary_or_unknown_rate_limit'
    elif code == 402:
        kind = 'credits_exhausted'
    elif code in (408, 500, 502, 503, 504):
        kind = 'temporary_server_error'
    else:
        kind = 'non_retryable_error'
    return dict(error_code=code, error_kind=kind, retry_after_seconds=delay)

@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4  # Initial call included.
    base_delay: float = 2
    max_delay: float = 30
    max_wait: float = 120  # Total backoff waits per document; pacing is separate.
    pace: float = 12  # Minimum spacing between request starts.

    def __post_init__(self):
        if self.max_attempts < 1 or self.max_attempts > 20:
            raise ValueError('max_attempts must be 1–20')
        if any(not math.isfinite(v) or v < 0 for v in (self.base_delay,self.max_delay,self.max_wait,self.pace)):
            raise ValueError('Retry delays must be finite and nonnegative')
        if self.base_delay > self.max_delay:
            raise ValueError('base_delay must not exceed max_delay')

def run_with_retry(call, policy, sleep=time.sleep, uniform=random.uniform,
                   on_attempt=lambda attempt: None):
    attempts, waited = [], 0.0
    for number in range(1, policy.max_attempts+1):
        result = call()
        attempt = dict(number=number, error=result.get('error'), error_code=result.get('error_code'),
            error_kind=result.get('error_kind'), seconds=result['seconds'], wait_after_seconds=0)
        attempts.append(attempt)
        on_attempt(attempt)
        kind = result.get('error_kind')
        stop = None
        if not result['error']:
            break
        if kind in ('daily_quota_exhausted','zero_quota','credits_exhausted'):
            stop = kind
        elif result.get('error_code') not in (429,408,500,502,503,504):
            break
        elif number == policy.max_attempts:
            stop = 'rate_limit_retry_budget_exhausted' if result.get('error_code')==429 else None
        else:
            ceiling = min(policy.max_delay, policy.base_delay * 2**(number-1))
            delay = max(uniform(ceiling/2, ceiling), result.get('retry_after_seconds') or 0)
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
