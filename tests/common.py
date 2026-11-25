"""Shared test helpers for Krado."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from freezegun.api import FrozenDateTimeFactory

from homeassistant.core import HomeAssistant

# Home Assistant publishes the test package itself from 2026.11; older versions
# use the community package.
try:
    from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
except ImportError:
    from pytest_homeassistant_custom_component.common import (
        MockConfigEntry,
        async_fire_time_changed,
    )

__all__ = ["MockConfigEntry", "advance_poll", "make_plant"]

POLL_INTERVAL = timedelta(minutes=5)


def make_plant(
    plant_id: str, *, leaflet: bool = True, illustration: bool = True
) -> dict[str, Any]:
    """Return a plant as the Krado API returns it."""
    return {
        "id": plant_id,
        "name": f"Plant {plant_id}",
        "kind": "monstera",
        "lightStatus": "good",
        "moistureStatus": "good",
        "temperatureStatus": "good",
        "humidityStatus": "good",
        "lastAnalyzedAt": "2026-11-25T00:00:00+00:00",
        "plantClassification": (
            {"illustrationUrl": f"https://example.com/{plant_id}.png"}
            if illustration
            else None
        ),
        "sensor": {
            "isConnected": leaflet,
            "serialNumber": f"SN-{plant_id}" if leaflet else None,
            "firmwareVersion": "1.0.0" if leaflet else None,
            "humidityRange": [30, 60],
            "lightRange": [100.0, 400.0],
            "moistureRange": [20, 80],
            "temperatureRange": [60, 85],
            "lastReading": (
                {
                    "battery": 90,
                    "humidity": 50,
                    "light": 150.5,
                    "moisture": 40,
                    "signal": 70,
                    "temperature": 72,
                    "createdAt": "2026-11-25T00:00:00+00:00",
                }
                if leaflet
                else None
            ),
        },
    }


async def advance_poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Move time forward past the next coordinator poll."""
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
