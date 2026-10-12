# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

from dataclasses import dataclass
import os


def _int_setting(name: str, default: int) -> int:
    value = int(os.getenv(name, str(default)))
    if value < 1:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _bool_setting(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean value")


@dataclass(frozen=True, slots=True)
class Settings:
    host: str
    port: int
    api_key: str | None
    upstream_timeout_seconds: float
    schedule_cache_ttl_seconds: int
    schedule_cache_stale_seconds: int
    location_cache_ttl_seconds: int
    location_cache_stale_seconds: int
    cache_max_entries: int
    rate_limit_enabled: bool
    rate_limit: str
    docs_enabled: bool

    @classmethod
    def from_environment(cls) -> "Settings":
        timeout = float(os.getenv("UPSTREAM_TIMEOUT_SECONDS", "15"))
        if timeout <= 0:
            raise ValueError("UPSTREAM_TIMEOUT_SECONDS must be greater than zero")

        api_key = os.getenv("API_KEY", "").strip() or None
        rate_limit = os.getenv("RATE_LIMIT", "60/minute").strip()
        if not rate_limit:
            raise ValueError("RATE_LIMIT must not be empty")

        return cls(
            host=os.getenv("HOST", "127.0.0.1"),
            port=_int_setting("PORT", 8000),
            api_key=api_key,
            upstream_timeout_seconds=timeout,
            schedule_cache_ttl_seconds=_int_setting("SCHEDULE_CACHE_TTL_SECONDS", 600),
            schedule_cache_stale_seconds=_int_setting(
                "SCHEDULE_CACHE_STALE_SECONDS",
                3600,
            ),
            location_cache_ttl_seconds=_int_setting("LOCATION_CACHE_TTL_SECONDS", 3600),
            location_cache_stale_seconds=_int_setting(
                "LOCATION_CACHE_STALE_SECONDS",
                86400,
            ),
            cache_max_entries=_int_setting("CACHE_MAX_ENTRIES", 64),
            rate_limit_enabled=_bool_setting("RATE_LIMIT_ENABLED", False),
            rate_limit=rate_limit,
            docs_enabled=_bool_setting("DOCS_ENABLED", True),
        )


settings = Settings.from_environment()
