# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

from typing import Literal

from pydantic import BaseModel


SlotStatus = Literal[
    "yes",
    "no",
    "maybe",
    "first",
    "second",
    "mfirst",
    "msecond",
    "unknown",
]


class Region(BaseModel):
    key: str
    name: str
    schedule_url: str


class CityResults(BaseModel):
    region: str
    cities: list[str]
    stale: bool


class StreetResults(BaseModel):
    region: str
    city: str
    streets: list[str]
    stale: bool


class HouseSummary(BaseModel):
    number: str
    groups: list[str]
    multiple_groups: bool
    excluded_from_schedule: bool


class HouseResults(BaseModel):
    region: str
    city: str
    street: str
    houses: list[HouseSummary]
    stale: bool


class Address(BaseModel):
    region: str
    city: str
    street: str
    house_number: str
    groups: list[str]
    group: str | None
    status: Literal["scheduled", "excluded", "multiple_groups"]


class CurrentOutage(BaseModel):
    reported: bool
    subtype: str | None
    outage_type: str | None
    starts_at: str | None
    ends_at: str | None


class Slot(BaseModel):
    index: int
    start: str
    end: str
    status: SlotStatus
    source_status: str | None = None


class WeeklyDay(BaseModel):
    weekday: int
    name: str | None
    slots: list[Slot]


class ConfirmedDay(BaseModel):
    date: str
    slots: list[Slot]


class WeeklyForecast(BaseModel):
    active: bool
    days: list[WeeklyDay]


class ConfirmedSchedule(BaseModel):
    source_updated_at: str | None
    days: list[ConfirmedDay]


class ScheduleData(BaseModel):
    weekly_forecast: WeeklyForecast | None
    confirmed: ConfirmedSchedule | None


class ScheduleResponse(BaseModel):
    source: Literal["dtek"]
    timezone: Literal["Europe/Kyiv"]
    fetched_at: str
    stale: bool
    age_seconds: int
    address: Address
    current_outage: CurrentOutage
    schedules: ScheduleData
