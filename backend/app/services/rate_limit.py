from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from datetime import date

from fastapi import Request


class SlidingWindowLimiter:
    def __init__(self, per_hour: int, per_day: int):
        self.per_hour = per_hour
        self.per_day = per_day
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, int]:
        now = time.time() if now is None else now
        with self._lock:
            events = self._events[key]
            day_cutoff = now - 86400
            while events and events[0] < day_cutoff:
                events.popleft()

            hour_count = sum(1 for timestamp in events if timestamp >= now - 3600)
            if hour_count >= self.per_hour:
                retry = int(3600 - (now - min(t for t in events if t >= now - 3600))) + 1
                return False, max(retry, 1)
            if len(events) >= self.per_day:
                retry = int(86400 - (now - events[0])) + 1
                return False, max(retry, 1)

            events.append(now)
            if len(self._events) > 5_000:
                self._prune(now)
            return True, 0

    def _prune(self, now: float) -> None:
        cutoff = now - 86400
        empty = [key for key, events in self._events.items() if not events or events[-1] < cutoff]
        for key in empty:
            self._events.pop(key, None)


class LLMBudget:
    def __init__(self, max_requests_per_day: int, monthly_allowance_usd: float):
        self.max_requests_per_day = max_requests_per_day
        self.monthly_allowance_usd = monthly_allowance_usd
        self._day = date.today()
        self._requests = 0
        self._allowance_used = 0.0
        self._lock = threading.Lock()

    def _rollover(self) -> None:
        today = date.today()
        if today != self._day:
            self._day = today
            self._requests = 0

    def check(self) -> tuple[bool, str]:
        with self._lock:
            self._rollover()
            if self._requests >= self.max_requests_per_day:
                return False, "daily_request_limit"
            if self.monthly_allowance_usd > 0 and self._allowance_used >= 0.8 * self.monthly_allowance_usd:
                return False, "monthly_allowance_guard"
            return True, "ok"

    def record(self, allowance_usd: float = 0.0) -> None:
        with self._lock:
            self._rollover()
            self._requests += 1
            if allowance_usd > 0:
                self._allowance_used += allowance_usd

    @property
    def requests_today(self) -> int:
        with self._lock:
            self._rollover()
            return self._requests

    @property
    def allowance_used(self) -> float:
        with self._lock:
            return round(self._allowance_used, 4)


def client_ip(request: Request, trust_proxy: bool) -> str:
    if trust_proxy:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # Use the right-most hop: that is the address appended by the
            # trusted reverse proxy. The left-most value is client-controlled
            # and can be spoofed to evade rate limits.
            return forwarded.split(",")[-1].strip()
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip.strip()
    return request.client.host if request.client else "unknown"
