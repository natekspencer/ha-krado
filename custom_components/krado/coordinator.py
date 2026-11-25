"""Krado coordinator."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN
from .pykrado import Krado, UnauthorizedError

type KradoConfigEntry = ConfigEntry[KradoCoordinator]

_LOGGER = logging.getLogger(__name__)


class KradoCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Krado data update coordinator."""

    config_entry: KradoConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: KradoConfigEntry, client: Krado
    ) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=5),
            always_update=False,
        )
        self.client = client

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            async with asyncio.timeout(10):
                data = await self.client.query_plants()
        except UnauthorizedError as err:
            raise ConfigEntryAuthFailed(err) from err
        except Exception as ex:
            raise UpdateFailed("Couldn't read from Krado") from ex
        if data is None:
            raise ConfigEntryAuthFailed
        return data

    def get_plant(self, plant_id: str) -> dict[str, Any] | None:
        """Return the plant with the given id, if it is still returned by the API."""
        return next(
            (plant for plant in self.data or [] if plant["id"] == plant_id), None
        )
