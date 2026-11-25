"""Krado image entity."""

from __future__ import annotations

from typing import Any

from homeassistant.components.image import ImageEntity, ImageEntityDescription
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import KradoConfigEntry, KradoCoordinator
from .entity import KradoEntity, async_setup_dynamic_entities


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KradoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Krado images using config entry."""
    async_setup_dynamic_entities(
        hass,
        entry,
        async_add_entities,
        Platform.IMAGE,
        _descriptions_for_plant,
        KradoImageEntity,
    )


IMAGE = ImageEntityDescription(key="image", name=None)


def _illustration_url(plant: dict[str, Any]) -> str | None:
    """Return the plant's illustration URL, if any."""
    return (plant.get("plantClassification") or {}).get("illustrationUrl")


def _descriptions_for_plant(
    plant: dict[str, Any],
) -> tuple[ImageEntityDescription, ...]:
    """Return the image descriptions that apply to a plant."""
    return (IMAGE,) if _illustration_url(plant) else ()


class KradoImageEntity(KradoEntity, ImageEntity):
    """Krado image entity."""

    def __init__(
        self,
        coordinator: KradoCoordinator,
        description: ImageEntityDescription,
        plant_id: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, description, plant_id)
        ImageEntity.__init__(self, coordinator.hass)

    @property
    def image_url(self) -> str | None:
        """Return URL of image."""
        if (plant := self.coordinator.get_plant(self.plant_id)) is None:
            return None
        return _illustration_url(plant)
