# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

from datetime import UTC, datetime
from typing import Any

from .cache import AsyncTTLCache, CacheResult
from .dtek_client import DtekClient
from .errors import HouseNotFoundError
from .models import (
    Address,
    ConfirmedSchedule,
    CurrentOutage,
    HouseSummary,
    ScheduleData,
    ScheduleResponse,
    WeeklyForecast,
)
from .normalization import (
    confirmed_days,
    find_case_insensitive_item,
    house_entries,
    normalize_group_ids,
    weekly_days,
)
from .settings import Settings


REGION_KEY = "krem"
REGION_NAME = "DTEK Kyiv Regional Networks"
REGION_SCHEDULE_URL = "https://www.dtek-krem.com.ua/ua/shutdowns"


class ScheduleService:
    """Resolve addresses and combine DTEK data into API responses."""

    def __init__(self, client: DtekClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._cache = AsyncTTLCache(settings.cache_max_entries)

    async def _catalog(self) -> CacheResult[dict[str, list[str]]]:
        return await self._cache.get_or_load(
            ("catalog", REGION_KEY),
            self._client.get_city_streets,
            ttl_seconds=self._settings.location_cache_ttl_seconds,
            stale_seconds=self._settings.location_cache_stale_seconds,
        )

    async def _house_data(self, city: str, street: str) -> CacheResult[dict[str, Any]]:
        key = ("houses", REGION_KEY, city, street)
        return await self._cache.get_or_load(
            key,
            lambda: self._client.get_house_data(city, street),
            ttl_seconds=self._settings.schedule_cache_ttl_seconds,
            stale_seconds=self._settings.schedule_cache_stale_seconds,
        )

    async def cities(self, query: str | None) -> tuple[list[str], bool]:
        result = await self._catalog()
        names = sorted(result.value, key=str.casefold)
        if query:
            needle = query.casefold()
            names = [name for name in names if needle in name.casefold()]
        return names, result.stale

    async def streets(self, city: str, query: str | None) -> tuple[list[str], bool]:
        result = await self._catalog()
        streets = find_case_insensitive_item(result.value, city)
        if not isinstance(streets, list):
            return [], result.stale
        names = sorted(streets, key=str.casefold)
        if query:
            needle = query.casefold()
            names = [name for name in names if needle in name.casefold()]
        return names, result.stale

    async def houses(
        self,
        city: str,
        street: str,
        query: str | None,
    ) -> tuple[list[HouseSummary], bool]:
        result = await self._house_data(city, street)
        entries = house_entries(result.value)
        houses = []
        for number, entry in entries.items():
            groups = normalize_group_ids(entry.get("sub_type_reason"))
            houses.append(
                HouseSummary(
                    number=number,
                    groups=groups,
                    multiple_groups=len(groups) > 1,
                    excluded_from_schedule=not groups,
                )
            )
        houses.sort(key=lambda house: (house.number.casefold(), house.number))
        if query:
            needle = query.casefold()
            houses = [house for house in houses if needle in house.number.casefold()]
        return houses, result.stale

    def _schedule_data(self, group_id: str, house_data: dict[str, Any]) -> ScheduleData:
        preset = self._client.schedule_preset or house_data.get("preset")
        fact = self._client.schedule_fact or house_data.get("fact")

        if isinstance(preset, dict):
            active, days = weekly_days(preset, group_id)
            weekly_forecast = WeeklyForecast(active=active, days=days)
            time_zone = preset.get("time_zone")
        else:
            weekly_forecast = None
            time_zone = None

        confirmed_schedule = None
        if isinstance(fact, dict):
            source_updated_at = fact.get("update")
            if source_updated_at is None:
                source_updated_at = house_data.get("updateTimestamp")
            confirmed_schedule = ConfirmedSchedule(
                source_updated_at=(
                    str(source_updated_at) if source_updated_at is not None else None
                ),
                days=confirmed_days(fact, group_id, time_zone),
            )

        return ScheduleData(
            weekly_forecast=weekly_forecast,
            confirmed=confirmed_schedule,
        )

    async def schedule(
        self,
        city: str,
        street: str,
        house_number: str,
    ) -> ScheduleResponse:
        await self._client.refresh_schedule_data()
        result = await self._house_data(city, street)
        entries = house_entries(result.value)
        entry = find_case_insensitive_item(entries, house_number)
        if not isinstance(entry, dict):
            raise HouseNotFoundError(house_number)

        groups = normalize_group_ids(entry.get("sub_type_reason"))
        if len(groups) > 1:
            address_status = "multiple_groups"
            group_id = None
            schedules = ScheduleData(weekly_forecast=None, confirmed=None)
        elif not groups:
            address_status = "excluded"
            group_id = None
            schedules = ScheduleData(weekly_forecast=None, confirmed=None)
        else:
            address_status = "scheduled"
            group_id = groups[0]
            schedules = self._schedule_data(group_id, result.value)

        schedule_fetched_at = self._client.schedule_fetched_at
        fetched_at = (
            min(result.fetched_at, schedule_fetched_at)
            if schedule_fetched_at
            else result.fetched_at
        )
        now = datetime.now(UTC)
        return ScheduleResponse(
            source="dtek",
            timezone="Europe/Kyiv",
            fetched_at=fetched_at.isoformat(),
            stale=result.stale or self._client.schedule_data_stale,
            age_seconds=max(0, int((now - fetched_at).total_seconds())),
            address=Address(
                region=REGION_KEY,
                city=city,
                street=street,
                house_number=house_number,
                groups=groups,
                group=group_id,
                status=address_status,
            ),
            current_outage=CurrentOutage(
                reported=bool(entry.get("sub_type") or entry.get("start_date")),
                subtype=str(entry["sub_type"]) if entry.get("sub_type") else None,
                outage_type=str(entry["type"]) if entry.get("type") else None,
                starts_at=str(entry["start_date"]) if entry.get("start_date") else None,
                ends_at=str(entry["end_date"]) if entry.get("end_date") else None,
            ),
            schedules=schedules,
        )
