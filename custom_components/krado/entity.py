"""Krado entity."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import KradoConfigEntry, KradoCoordinator


class KradoEntity(CoordinatorEntity[KradoCoordinator]):
    """Base class for Krado entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: KradoCoordinator,
        description: EntityDescription,
        plant_id: str,
    ) -> None:
        """Construct a Krado entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self.plant_id = plant_id

        plant = self.plant
        sensor = plant["sensor"]

        self._attr_unique_id = unique_id(plant_id, description.key)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, plant_id)},
            name=plant["name"],
            manufacturer="Krado",
            model="leaflet" if sensor["isConnected"] else plant["kind"],
            serial_number=sensor["serialNumber"],
            sw_version=sensor["firmwareVersion"],
        )

    @property
    def plant(self) -> dict[str, Any]:
        """Get plant data.

        Only call this while the entity is available; the plant may have been
        removed from the account since the last update.
        """
        plant = self.coordinator.get_plant(self.plant_id)
        assert plant is not None
        return plant

    @property
    def available(self) -> bool:
        """Test if entity is available."""
        return (
            super().available and self.coordinator.get_plant(self.plant_id) is not None
        )


def unique_id(plant_id: str, key: str) -> str:
    """Return the unique id for a plant entity."""
    return f"{plant_id}-{key}"


def async_setup_dynamic_entities[DescriptionT: EntityDescription](
    hass: HomeAssistant,
    entry: KradoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    platform: Platform,
    descriptions_for_plant: Callable[[dict[str, Any]], Iterable[DescriptionT]],
    entity_factory: Callable[[KradoCoordinator, DescriptionT, str], KradoEntity],
) -> None:
    """Keep a platform's entities in sync with the plants the API returns.

    On every coordinator update, entities for new plants (or plants that newly
    qualify, such as a newly connected leaflet) are added and entities that no
    longer apply are removed from the entity registry.
    """
    coordinator = entry.runtime_data
    entity_registry = er.async_get(hass)

    # Start from what is already registered so entities that went stale while
    # Home Assistant was stopped are cleaned up on the first pass.
    known: set[str] = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id)
        if entity.domain == platform
    }
    added: set[str] = set()

    @callback
    def _async_sync_entities() -> None:
        if not coordinator.last_update_success:
            return

        wanted: dict[str, tuple[DescriptionT, str]] = {
            unique_id(plant["id"], description.key): (description, plant["id"])
            for plant in coordinator.data
            for description in descriptions_for_plant(plant)
        }

        if new_entities := [
            entity_factory(coordinator, description, plant_id)
            for uid, (description, plant_id) in wanted.items()
            if uid not in added
        ]:
            added.update(wanted.keys() - added)
            async_add_entities(new_entities)

        for uid in (known | added) - wanted.keys():
            if entity_id := entity_registry.async_get_entity_id(platform, DOMAIN, uid):
                entity_registry.async_remove(entity_id)
            added.discard(uid)

        known.clear()
        known.update(wanted)

    _async_sync_entities()
    entry.async_on_unload(coordinator.async_add_listener(_async_sync_entities))
