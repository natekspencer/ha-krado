"""Tests for setting up Krado and keeping its devices and entities in sync."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest

from custom_components.krado.const import DOMAIN
from custom_components.krado.sensor import DESCRIPTORS
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .common import MockConfigEntry, advance_poll, make_plant

# Every sensor, plus the plant illustration.
ENTITIES_PER_LEAFLET_PLANT = len(DESCRIPTORS) + 1


async def setup_integration(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set up the config entry."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def device_plant_ids(hass: HomeAssistant, entry: MockConfigEntry) -> set[str]:
    """Return the plant ids of the entry's devices."""
    return {
        identifier
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )
        for domain, identifier in device.identifiers
        if domain == DOMAIN
    }


def entity_unique_ids(
    hass: HomeAssistant, entry: MockConfigEntry, plant_id: str
) -> set[str]:
    """Return the unique ids of a plant's registered entities."""
    return {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        if entity.unique_id.startswith(f"{plant_id}-")
    }


@pytest.mark.usefixtures("mock_krado")
async def test_setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Plants with a leaflet get sensors; plants without one only get an image."""
    await setup_integration(hass, config_entry)

    assert config_entry.state is ConfigEntryState.LOADED
    assert device_plant_ids(hass, config_entry) == {"a", "b"}
    assert len(entity_unique_ids(hass, config_entry, "a")) == ENTITIES_PER_LEAFLET_PLANT
    assert entity_unique_ids(hass, config_entry, "b") == {"b-image"}

    humidity = hass.states.get("sensor.plant_a_humidity")
    assert humidity.state == "50"
    status = hass.states.get("sensor.plant_a_humidity_status")
    assert status.state == "good"
    assert status.attributes["low"] == 30
    assert status.attributes["high"] == 60


@pytest.mark.usefixtures("mock_krado")
async def test_new_plant_and_leaflet_added(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    plants: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A new plant, or a newly connected leaflet, is added without a reload."""
    await setup_integration(hass, config_entry)

    plants[:] = [make_plant("a"), make_plant("b"), make_plant("c")]
    await advance_poll(hass, freezer)

    assert device_plant_ids(hass, config_entry) == {"a", "b", "c"}
    for plant_id in ("b", "c"):
        assert (
            len(entity_unique_ids(hass, config_entry, plant_id))
            == ENTITIES_PER_LEAFLET_PLANT
        )
        assert hass.states.get(f"sensor.plant_{plant_id}_humidity").state == "50"


@pytest.mark.usefixtures("mock_krado")
async def test_removed_plant_cleaned_up(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    plants: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A plant the API no longer returns loses its device and entities."""
    await setup_integration(hass, config_entry)

    plants[:] = [make_plant("b", leaflet=False)]
    await advance_poll(hass, freezer)

    assert device_plant_ids(hass, config_entry) == {"b"}
    assert not entity_unique_ids(hass, config_entry, "a")
    assert hass.states.get("sensor.plant_a_humidity") is None
    assert hass.states.get("image.plant_a") is None


@pytest.mark.usefixtures("mock_krado")
async def test_disconnected_leaflet_cleaned_up(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    plants: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """A disconnected leaflet loses its sensors, and gets them back on reconnect."""
    await setup_integration(hass, config_entry)

    plants[:] = [make_plant("a", leaflet=False), make_plant("b", leaflet=False)]
    await advance_poll(hass, freezer)

    assert device_plant_ids(hass, config_entry) == {"a", "b"}
    assert entity_unique_ids(hass, config_entry, "a") == {"a-image"}
    assert hass.states.get("sensor.plant_a_humidity") is None

    plants[:] = [make_plant("a"), make_plant("b", leaflet=False)]
    await advance_poll(hass, freezer)

    assert len(entity_unique_ids(hass, config_entry, "a")) == ENTITIES_PER_LEAFLET_PLANT
    assert hass.states.get("sensor.plant_a_humidity").state == "50"


async def test_failed_update_keeps_everything(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    mock_krado: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A failed poll makes entities unavailable but doesn't remove them."""
    await setup_integration(hass, config_entry)

    mock_krado.query_plants.side_effect = Exception("API down")
    await advance_poll(hass, freezer)

    assert device_plant_ids(hass, config_entry) == {"a", "b"}
    assert len(entity_unique_ids(hass, config_entry, "a")) == ENTITIES_PER_LEAFLET_PLANT
    assert hass.states.get("sensor.plant_a_humidity").state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_krado")
async def test_stale_while_stopped_cleaned_up_on_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    plants: list[dict[str, Any]],
) -> None:
    """Plants and leaflets removed while the entry was unloaded are cleaned up."""
    await setup_integration(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)

    plants[:] = [make_plant("b", leaflet=False)]
    await setup_integration(hass, config_entry)

    assert device_plant_ids(hass, config_entry) == {"b"}
    assert not entity_unique_ids(hass, config_entry, "a")
    assert entity_unique_ids(hass, config_entry, "b") == {"b-image"}


@pytest.mark.usefixtures("mock_krado")
async def test_account_without_plants_loads(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    plants: list[dict[str, Any]],
    freezer: FrozenDateTimeFactory,
) -> None:
    """An account with no plants loads, and picks up its first plant later."""
    plants.clear()
    await setup_integration(hass, config_entry)
    assert config_entry.state is ConfigEntryState.LOADED

    plants.append(make_plant("a"))
    await advance_poll(hass, freezer)

    assert device_plant_ids(hass, config_entry) == {"a"}


async def test_unload_closes_client(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_krado: MagicMock
) -> None:
    """Unloading the entry closes the API client."""
    await setup_integration(hass, config_entry)
    assert await hass.config_entries.async_unload(config_entry.entry_id)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    mock_krado.close.assert_awaited_once()
