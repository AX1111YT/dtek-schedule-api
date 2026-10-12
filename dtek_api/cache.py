# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

import asyncio
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Hashable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Generic, TypeVar, cast


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class CacheResult(Generic[T]):
    value: T
    fetched_at: datetime
    stale: bool


@dataclass(frozen=True, slots=True)
class _Entry(Generic[T]):
    value: T
    fetched_at: datetime
    fresh_until: float
    stale_until: float


class AsyncTTLCache:
    def __init__(self, max_entries: int) -> None:
        self._max_entries = max_entries
        self._entries: OrderedDict[Hashable, _Entry[Any]] = OrderedDict()
        self._inflight: dict[Hashable, asyncio.Task[Any]] = {}
        self._lock = asyncio.Lock()

    async def get_or_load(
        self,
        key: Hashable,
        loader: Callable[[], Awaitable[T]],
        *,
        ttl_seconds: int,
        stale_seconds: int,
    ) -> CacheResult[T]:
        """Coalesce concurrent misses and use stale data if a refresh fails."""
        now = monotonic()
        async with self._lock:
            entry = self._entries.get(key)
            if entry is not None and now < entry.fresh_until:
                self._entries.move_to_end(key)
                return CacheResult(cast(T, entry.value), entry.fetched_at, False)

            pending = self._inflight.get(key)
            if pending is None:
                pending = asyncio.create_task(loader())
                self._inflight[key] = pending

        try:
            value = await asyncio.shield(pending)
        except Exception:
            async with self._lock:
                if self._inflight.get(key) is pending:
                    self._inflight.pop(key, None)
                old_entry = self._entries.get(key)
                if old_entry is not None and monotonic() < old_entry.stale_until:
                    self._entries.move_to_end(key)
                    return CacheResult(
                        cast(T, old_entry.value),
                        old_entry.fetched_at,
                        True,
                    )
            raise

        fetched_at = datetime.now(UTC)
        stored_at = monotonic()
        async with self._lock:
            if self._inflight.get(key) is pending:
                self._inflight.pop(key, None)
            self._entries[key] = _Entry(
                value=value,
                fetched_at=fetched_at,
                fresh_until=stored_at + ttl_seconds,
                stale_until=stored_at + ttl_seconds + stale_seconds,
            )
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

        return CacheResult(value, fetched_at, False)
