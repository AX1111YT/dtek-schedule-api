# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

from fastapi import APIRouter, HTTPException, Query, Request

from .errors import HouseNotFoundError
from .models import (
    CityResults,
    HouseResults,
    Region,
    ScheduleResponse,
    StreetResults,
)
from .rate_limit import limiter
from .settings import settings
from .service import REGION_KEY, REGION_NAME, REGION_SCHEDULE_URL, ScheduleService


router = APIRouter()


def _service(request: Request) -> ScheduleService:
    return request.app.state.schedule_service


def _require_region(region: str) -> None:
    if region.casefold() != REGION_KEY:
        raise HTTPException(status_code=404, detail="Region is not supported.")


@router.get("/v1/regions", response_model=list[Region])
@limiter.shared_limit(settings.rate_limit, scope="api")
async def regions(request: Request) -> list[Region]:
    return [Region(key=REGION_KEY, name=REGION_NAME, schedule_url=REGION_SCHEDULE_URL)]


@router.get("/v1/locations/cities", response_model=CityResults)
@limiter.shared_limit(settings.rate_limit, scope="api")
async def cities(
    request: Request,
    region: str = REGION_KEY,
    q: str | None = Query(default=None, max_length=100),
) -> CityResults:
    _require_region(region)
    names, stale = await _service(request).cities(q)
    return CityResults(region=REGION_KEY, cities=names, stale=stale)


@router.get("/v1/locations/streets", response_model=StreetResults)
@limiter.shared_limit(settings.rate_limit, scope="api")
async def streets(
    request: Request,
    city: str = Query(min_length=1, max_length=200),
    region: str = REGION_KEY,
    q: str | None = Query(default=None, max_length=100),
) -> StreetResults:
    _require_region(region)
    names, stale = await _service(request).streets(city, q)
    return StreetResults(region=REGION_KEY, city=city, streets=names, stale=stale)


@router.get("/v1/locations/houses", response_model=HouseResults)
@limiter.shared_limit(settings.rate_limit, scope="api")
async def houses(
    request: Request,
    city: str = Query(min_length=1, max_length=200),
    street: str = Query(min_length=1, max_length=200),
    region: str = REGION_KEY,
    q: str | None = Query(default=None, max_length=50),
) -> HouseResults:
    _require_region(region)
    entries, stale = await _service(request).houses(city, street, q)
    return HouseResults(
        region=REGION_KEY,
        city=city,
        street=street,
        houses=entries,
        stale=stale,
    )


@router.get("/v1/schedule", response_model=ScheduleResponse)
@limiter.shared_limit(settings.rate_limit, scope="api")
async def schedule(
    request: Request,
    city: str = Query(min_length=1, max_length=200),
    street: str = Query(min_length=1, max_length=200),
    house_number: str = Query(min_length=1, max_length=50),
    region: str = REGION_KEY,
) -> ScheduleResponse:
    _require_region(region)
    try:
        return await _service(request).schedule(city, street, house_number)
    except HouseNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="House was not found on this street.",
        ) from exc
