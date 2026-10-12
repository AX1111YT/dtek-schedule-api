# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

"""Translate DTEK response payloads into the API's normalized models."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any, TypeVar, get_args
from zoneinfo import ZoneInfo

from .models import ConfirmedDay, Slot, SlotStatus, WeeklyDay


T = TypeVar("T")
KYIV_TIMEZONE = ZoneInfo("Europe/Kyiv")
KNOWN_SLOT_STATUSES = frozenset(get_args(SlotStatus)) - {"unknown"}


def find_case_insensitive_item(mapping: Mapping[Any, T], requested: str) -> T | None:
    if requested in mapping:
        return mapping[requested]

    requested_folded = requested.casefold()
    for key, value in mapping.items():
        if str(key).casefold() == requested_folded:
            return value
    return None


def normalize_group_ids(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value else []
    if isinstance(value, list):
        return [str(group) for group in value if group]
    return []


def house_entries(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    data = payload.get("data")
    result: dict[str, dict[str, Any]] = {}
    if isinstance(data, dict):
        for number, entry in data.items():
            if isinstance(entry, dict):
                result[str(number)] = entry
        return result

    if isinstance(data, list):
        for entry in data:
            if not isinstance(entry, dict):
                continue
            number = next(
                (
                    entry.get(key)
                    for key in ("num", "house_num", "house_number", "name", "id")
                    if entry.get(key) is not None
                ),
                None,
            )
            if number is not None:
                result[str(number)] = entry
    return result


def _time_text(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def normalize_slots(raw_slots: Any, time_zone: Any = None) -> list[Slot]:
    if not isinstance(raw_slots, dict):
        return []

    indices = []
    for key in raw_slots:
        try:
            indices.append(int(key))
        except (TypeError, ValueError):
            continue

    # When DTEK omits explicit ranges, infer the grid from the slot index range.
    interval = 60 if indices and max(indices) <= 24 else 30
    normalized: list[Slot] = []
    for key, raw_status in raw_slots.items():
        try:
            index = int(key)
        except (TypeError, ValueError):
            continue
        if index < 1 or index > 48:
            continue

        original_status = str(raw_status)
        normalized_status = original_status.strip().casefold()
        status = (
            normalized_status
            if normalized_status in KNOWN_SLOT_STATUSES
            else "unknown"
        )
        time_range = time_zone.get(str(index)) if isinstance(time_zone, dict) else None
        if isinstance(time_range, (list, tuple)) and len(time_range) >= 3:
            start, end = str(time_range[1]), str(time_range[2])
        else:
            start_minutes = (index - 1) * interval
            start, end = _time_text(start_minutes), _time_text(start_minutes + interval)

        normalized.append(
            Slot(
                index=index,
                start=start,
                end=end,
                status=status,
                source_status=original_status if status == "unknown" else None,
            )
        )

    return sorted(normalized, key=lambda slot: slot.index)


def confirmed_days(fact: Any, group_id: str, time_zone: Any) -> list[ConfirmedDay]:
    if not isinstance(fact, dict) or not isinstance(fact.get("data"), dict):
        return []

    days: list[ConfirmedDay] = []
    for timestamp, groups in fact["data"].items():
        if not isinstance(groups, dict):
            continue
        raw_slots = find_case_insensitive_item(groups, group_id)
        if not isinstance(raw_slots, dict):
            continue
        try:
            day = datetime.fromtimestamp(int(timestamp), tz=KYIV_TIMEZONE).date()
        except (OverflowError, OSError, TypeError, ValueError):
            continue
        days.append(
            ConfirmedDay(
                date=day.isoformat(),
                slots=normalize_slots(raw_slots, time_zone),
            )
        )

    return sorted(days, key=lambda item: item.date)


def weekly_days(preset: Any, group_id: str) -> tuple[bool, list[WeeklyDay]]:
    if not isinstance(preset, dict):
        return False, []

    groups = preset.get("data")
    group_schedule = (
        find_case_insensitive_item(groups, group_id)
        if isinstance(groups, dict)
        else None
    )
    if not isinstance(group_schedule, dict):
        return bool(preset.get("is_active", False)), []

    day_names = preset.get("days", {})
    time_zone = preset.get("time_zone")
    normalized: list[WeeklyDay] = []
    for day_key, slots in group_schedule.items():
        try:
            weekday = int(day_key)
        except (TypeError, ValueError):
            continue
        if weekday < 1 or weekday > 7:
            continue

        name = None
        if isinstance(day_names, dict):
            name = day_names.get(str(weekday), day_names.get(weekday))
        normalized.append(
            WeeklyDay(
                weekday=weekday,
                name=str(name) if name is not None else None,
                slots=normalize_slots(slots, time_zone),
            )
        )

    active = bool(preset.get("is_active", True)) and bool(normalized)
    return active, sorted(normalized, key=lambda item: item.weekday)
