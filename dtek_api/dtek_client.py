# Copyright 2026 AX1111YT
# SPDX-License-Identifier: Apache-2.0

import asyncio
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from time import monotonic
from typing import Any
from urllib.parse import urljoin, urlsplit

from curl_cffi.requests import AsyncSession
from curl_cffi.requests.errors import RequestsError

from .errors import DtekBlockedError, DtekError, DtekProtocolError, DtekRateLimitError


BASE_URL = "https://www.dtek-krem.com.ua"
SCHEDULE_URL = f"{BASE_URL}/ua/shutdowns"
FALLBACK_AJAX_URL = f"{BASE_URL}/ua/ajax"
BLOCK_PAGE_MARKERS = ("_Incapsula_Resource", "visid_incap", "incap_ses")
ALLOWED_AJAX_HOSTS = {"www.dtek-krem.com.ua", "dtek-krem.com.ua"}
SCHEDULE_REFRESH_INTERVAL_SECONDS = 300


def _embedded_schedule(html: str, name: str) -> dict[str, Any] | None:
    match = re.search(rf"DisconSchedule\.{name}\s*=\s*", html)
    if match is None:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(html, match.end())
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


class _AjaxUrlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ajax_url: str | None = None
        self.csrf_token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() != "meta":
            return
        attributes = {key.casefold(): value for key, value in attrs}
        if str(attributes.get("name") or "").casefold() == "ajaxurl":
            self.ajax_url = attributes.get("content")
        elif str(attributes.get("name") or "").casefold() == "csrf-token":
            self.csrf_token = attributes.get("content")


class DtekClient:
    """Manage the upstream session and retrieve DTEK catalogs and schedules."""

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds
        self._session: AsyncSession[Any] | None = None
        self._ajax_url: str | None = None
        self.schedule_fact: dict[str, Any] | None = None
        self.schedule_preset: dict[str, Any] | None = None
        self.schedule_fetched_at: datetime | None = None
        self.schedule_data_stale = False
        self._schedule_checked_at = 0.0
        self._discovery_lock = asyncio.Lock()
        self._schedule_refresh_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    def _get_session(self) -> AsyncSession[Any]:
        if self._session is None:
            self._session = AsyncSession(
                timeout=self._timeout_seconds,
                impersonate="chrome120",
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "uk,en-US;q=0.9,en;q=0.8",
                    "Origin": BASE_URL,
                    "Referer": SCHEDULE_URL,
                    "X-Requested-With": "XMLHttpRequest",
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                },
            )
        return self._session

    async def _discover_ajax_url(self) -> str:
        if self._ajax_url is not None:
            return self._ajax_url

        async with self._discovery_lock:
            if self._ajax_url is not None:
                return self._ajax_url
            try:
                response = await self._get_session().get(SCHEDULE_URL)
            except RequestsError as exc:
                raise DtekError("Could not reach the DTEK schedule page.") from exc

            if response.status_code in (401, 403):
                raise DtekBlockedError()
            if response.status_code == 429:
                raise DtekRateLimitError()
            if response.status_code >= 500:
                raise DtekError(f"DTEK returned HTTP {response.status_code}.")

            html = response.text
            self.schedule_fact = _embedded_schedule(html, "fact")
            self.schedule_preset = _embedded_schedule(html, "preset")
            self.schedule_fetched_at = datetime.now(UTC)
            self._schedule_checked_at = monotonic()
            parser = _AjaxUrlParser()
            parser.feed(html)
            if parser.csrf_token:
                self._get_session().headers["X-CSRF-Token"] = parser.csrf_token
            discovered = parser.ajax_url
            ajax_url = (
                urljoin(BASE_URL, discovered) if discovered else FALLBACK_AJAX_URL
            )
            parsed_url = urlsplit(ajax_url)
            # The page supplies this endpoint dynamically; keep requests on DTEK hosts.
            if (
                parsed_url.scheme != "https"
                or parsed_url.hostname not in ALLOWED_AJAX_HOSTS
            ):
                raise DtekProtocolError("DTEK supplied an unexpected AJAX endpoint.")
            self._ajax_url = ajax_url
            return self._ajax_url

    async def _post(self, form: dict[str, str]) -> dict[str, Any]:
        ajax_url = await self._discover_ajax_url()
        try:
            response = await self._get_session().post(ajax_url, data=form)
        except RequestsError as exc:
            raise DtekError("Could not reach the DTEK schedule endpoint.") from exc

        if response.status_code in (401, 403):
            raise DtekBlockedError()
        if response.status_code == 429:
            raise DtekRateLimitError()
        if response.status_code >= 500:
            raise DtekError(f"DTEK returned HTTP {response.status_code}.")
        if response.status_code >= 400:
            if any(marker in response.text for marker in BLOCK_PAGE_MARKERS):
                raise DtekBlockedError()
            raise DtekError(f"DTEK returned HTTP {response.status_code}.")

        try:
            payload = response.json()
        except (ValueError, TypeError) as exc:
            if any(marker in response.text for marker in BLOCK_PAGE_MARKERS):
                raise DtekBlockedError() from exc
            raise DtekProtocolError("DTEK did not return JSON.") from exc

        if not isinstance(payload, dict) or (
            payload.get("result") is False and form.get("method") != "checkDisconUpdate"
        ):
            raise DtekProtocolError("DTEK returned an unexpected response.")
        return payload

    async def refresh_schedule_data(self) -> None:
        await self._discover_ajax_url()
        if self.schedule_fact is None or self.schedule_preset is None:
            return
        if monotonic() - self._schedule_checked_at < SCHEDULE_REFRESH_INTERVAL_SECONDS:
            return

        async with self._schedule_refresh_lock:
            now = monotonic()
            if now - self._schedule_checked_at < SCHEDULE_REFRESH_INTERVAL_SECONDS:
                return
            # Throttle retries after failures as well as successful refreshes.
            self._schedule_checked_at = now
            try:
                payload = await self._post(
                    {
                        "method": "checkDisconUpdate",
                        "update": str(self.schedule_fact.get("update", "")),
                    }
                )
            except DtekError:
                self.schedule_data_stale = True
                return

            fact = payload.get("fact")
            preset = payload.get("preset")
            if payload.get("result") is True:
                if not isinstance(fact, dict) or not isinstance(preset, dict):
                    self.schedule_data_stale = True
                    return
                self.schedule_fact = fact
                self.schedule_preset = preset
            self.schedule_fetched_at = datetime.now(UTC)
            self.schedule_data_stale = False

    async def get_city_streets(self) -> dict[str, list[str]]:
        payload = await self._post({"method": "getStreets"})
        raw = payload.get("streets", payload.get("data"))
        if not isinstance(raw, dict):
            raise DtekProtocolError("The DTEK street catalog was not a mapping.")
        cities = {
            str(city): [str(street) for street in streets if street]
            for city, streets in raw.items()
            if isinstance(streets, list)
        }
        if not cities:
            raise DtekProtocolError("The DTEK street catalog was empty.")
        return cities

    async def get_house_data(self, city: str, street: str) -> dict[str, Any]:
        payload = await self._post(
            {
                "method": "getHomeNum",
                "data[0][name]": "city",
                "data[0][value]": city,
                "data[1][name]": "street",
                "data[1][value]": street,
            }
        )
        if not isinstance(payload.get("data"), (dict, list)):
            raise DtekProtocolError(
                "The DTEK house response did not include address data."
            )
        return payload
