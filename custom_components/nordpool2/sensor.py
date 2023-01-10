"""Nordpool sensor platform."""
from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta, datetime
import logging
from typing import Any

from operator import itemgetter
from statistics import mean

from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_point_in_utc_time, async_track_time_change
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
import voluptuous as vol
import pytz

from . import DOMAIN, REGIONS, CURRENCY_TO_CENTS

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional("region", default="SE3"): vol.In(REGIONS),
        vol.Optional("currency", default="SEK"): vol.In(CURRENCY_TO_CENTS.keys()),
    }
)

async def async_setup_entry(
    hass: core.HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: Callable,
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN]
    sensor = NordpoolSensor(hass, config)
    async_add_entities([sensor], update_before_add=True)


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the sensor platform."""
    sensor = NordpoolSensor(hass, config)
    async_add_entities([sensor], update_before_add=True)


class NordpoolerSensor(Entity):
    """Nordpool Sensor class."""

    @property
    def name(self):
        """Return the name of the sensor."""
        return fDOMAIN

    @property
    def state(self):
        """Return the state of the sensor."""
        return "body"


class NordpoolSensor(Entity):
    """Representation of a GitHub Repo sensor."""

    def __init__(self, hass, config):
        super().__init__()
        self.today = []
        self.tomorrow = []
        self.hass = hass
        self.session = async_get_clientsession(hass)
        self.config = config
        self.attrs: dict[str, Any] = {}
        self._state = None
        self._available = False
    
    @property
    def should_poll(self) -> bool:
        return False

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return "nordpool"

    @property
    def unique_id(self) -> str:
        """Return the unique ID of the sensor."""
        return ("nordpool_%s_%s" % (
            self.config["region"],
            self.config["currency"],
        )).lower()

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement this sensor expresses itself in."""
        return "%s/kWh"%(CURRENCY_TO_CENTS[self.config["currency"]],)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    @property
    def state(self) -> str | None:
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.attrs

    @staticmethod
    def stockholm_now() -> datetime:
        return datetime.now(pytz.utc).astimezone(pytz.timezone('Europe/Stockholm'))

    async def async_fetch_nordpool_data(self, *args, **kwargs) -> None:
        _LOGGER.debug("Fetching Nordpool data")
        # Treat everything in Stockholm time zone (same as Nordpool API)
        stockholm_midnight = self.stockholm_now().replace(hour=0,minute=0,second=0,microsecond=0)

        # Today's and tomorrow's date as strings used in the API
        stockholm_today = self.stockholm_now().strftime('%d-%m-%Y')
        stockholm_tomorrow = (self.stockholm_now() + timedelta(days=1)).strftime('%d-%m-%Y')

        # Result arrays
        today, tomorrow = [], []

        # To the brittle part
        try:
            # Fetch data
            url = "https://www.nordpoolgroup.com/api/marketdata/page/29?currency=%s&endDate=%s&entityName=%s"%(self.config["currency"], stockholm_tomorrow, self.config["region"])
            async with self.session.get(url) as resp:
                data = await resp.json()

            # Dance with the data
            for i, row in enumerate(data["data"]["Rows"]):
                if i < 24:
                    for col in row["Columns"]:
                        if col["Name"] == stockholm_today:
                            today.append({
                                "start": stockholm_midnight + timedelta(hours=i),
                                "value": float(col["Value"].replace(" ", "").replace(",", ".")) / 10,
                                "end": stockholm_midnight + timedelta(hours=i+1),
                            })
                        elif col["Name"] == stockholm_tomorrow:
                            tomorrow.append({
                                "start": stockholm_midnight + timedelta(hours=i, days=1),
                                "value": float(col["Value"].replace(" ", "").replace(",", ".")) / 10,
                                "end": stockholm_midnight + timedelta(hours=i+1, days=1),
                            })
        except Exception as err:
            _LOGGER.exception(f"Nordpool data fetch failed {err=}, {type(err)=}")

        self.today, self.tomorrow = today, tomorrow
        if self.today:
            self._available = True
            self.update_state()
            self.schedule_nordpool_data_fetch()
        else:
            # If something failed, try again in five minutes
            _LOGGER.info("Resceduling data fetch because today's data was False")
            self.async_call_later(self.hass, self.async_fetch_nordpool_data, timedelta(minutes=5))

    def format_hourly_array(self, arr) -> list:
        return [
            {
                "value": "%.3f"%(e["value"],),
                "start": e["start"].isoformat(),
                "end": e["end"].isoformat(),
            }
            for e in arr
        ]

    def update_state(self) -> None:
        now = self.stockholm_now()
        for row in self.today:
            if row.get("start") <= now and row.get("end") > now:
                self._state = "%.3f"%(row.get("value"),)
                break
        self.attrs = {
            "avg_today": "%.3f"%(mean(map(itemgetter("value"), self.today)) if self.today else 0.,),
            "avg_tomorrow": "%.3f"%(mean(map(itemgetter("value"), self.tomorrow)) if self.tomorrow else 0.,),
            "today": self.format_hourly_array(self.today),
            "tomorrow": self.format_hourly_array(self.tomorrow),
        }
        self.schedule_update_ha_state()

    async def hourly_cb(self, *args, **kwargs) -> None:
        # Passed last end of today, it's midnight
        if self.stockholm_now() >= self.today[-1]["end"]:
            self.today = self.tomorrow
            self.tomorrow = []
        self.update_state()

    def schedule_hourly_cb(self) -> None:
        async_track_time_change(self.hass, self.hourly_cb, minute=0, second=0)

    def schedule_nordpool_data_fetch(self) -> None:
        """Schedule a callback for fetching Nordpool data for next time the time in Stockholm is 13:00"""
        now = self.stockholm_now()
        # Chosen to not coincide with an hourly callback, data is often published before 13:00
        fetch_time = {"hour": 12, "minute": 51, "second": 0, "microsecond": 0}
        next_data_time = self.stockholm_now().replace(**fetch_time)
        if next_data_time < now:
            next_data_time += timedelta(days=1)
            next_data_time = next_data_time.replace(**fetch_time)
        next_data_time_utc = next_data_time.astimezone(pytz.utc)
        _LOGGER.debug("Scheduling nordpool fetch for " + str(next_data_time_utc))
        async_track_point_in_utc_time(self.hass, self.async_fetch_nordpool_data, next_data_time_utc)

    async def async_added_to_hass(self):
        """Connect to dispatcher listening for entity data notifications."""
        await super().async_added_to_hass()
        # Fetch initial data, schedules next fetch as a side effect
        await self.async_fetch_nordpool_data()
        # Schedule hourly callback
        self.schedule_hourly_cb()
