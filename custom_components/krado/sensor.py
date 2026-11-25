"""Krado sensor entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    Platform,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .coordinator import KradoConfigEntry
from .entity import KradoEntity, async_setup_dynamic_entities

_LOGGER = logging.getLogger(__name__)

PLANT_MEASUREMENT_STATUS_LIST = ["critical_low", "low", "good", "high"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KradoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Krado sensors using config entry."""
    async_setup_dynamic_entities(
        hass,
        entry,
        async_add_entities,
        Platform.SENSOR,
        _descriptions_for_plant,
        KradoSensorEntity,
    )


def _descriptions_for_plant(
    plant: dict[str, Any],
) -> tuple[KradoSensorEntityDescription, ...]:
    """Return the sensor descriptions that apply to a plant."""
    return DESCRIPTORS if _has_leaflet(plant) else ()


def _has_leaflet(plant: dict[str, Any]) -> bool:
    """Return whether the plant has a connected leaflet."""
    return bool((plant.get("sensor") or {}).get("isConnected"))


@dataclass(frozen=True, kw_only=True)
class KradoSensorEntityDescription(SensorEntityDescription):
    """Krado sensor entity description"""

    field: str
    is_reading: bool = True
    range_field: str | None = None


DESCRIPTORS = (
    KradoSensorEntityDescription(
        key="battery",
        field="battery",
        device_class=SensorDeviceClass.BATTERY,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KradoSensorEntityDescription(
        key="humidity",
        field="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KradoSensorEntityDescription(
        key="humidity_status",
        field="humidityStatus",
        is_reading=False,
        range_field="humidityRange",
        translation_key="humidity_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=PLANT_MEASUREMENT_STATUS_LIST,
    ),
    KradoSensorEntityDescription(
        key="last_analyzed",
        field="lastAnalyzedAt",
        is_reading=False,
        translation_key="last_analyzed",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KradoSensorEntityDescription(
        key="last_reading",
        field="createdAt",
        translation_key="last_reading",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KradoSensorEntityDescription(
        key="light",
        field="light",
        translation_key="light",
        native_unit_of_measurement="μmol/m²/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
    ),
    KradoSensorEntityDescription(
        key="light_status",
        field="lightStatus",
        is_reading=False,
        range_field="lightRange",
        translation_key="light_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=PLANT_MEASUREMENT_STATUS_LIST,
    ),
    KradoSensorEntityDescription(
        key="moisture",
        field="moisture",
        translation_key="moisture",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KradoSensorEntityDescription(
        key="moisture_status",
        field="moistureStatus",
        is_reading=False,
        range_field="moistureRange",
        translation_key="moisture_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=PLANT_MEASUREMENT_STATUS_LIST,
    ),
    KradoSensorEntityDescription(
        key="signal",
        field="signal",
        translation_key="signal",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KradoSensorEntityDescription(
        key="temperature",
        field="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    KradoSensorEntityDescription(
        key="temperature_status",
        field="temperatureStatus",
        is_reading=False,
        range_field="temperatureRange",
        translation_key="temperature_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=PLANT_MEASUREMENT_STATUS_LIST,
    ),
    KradoSensorEntityDescription(
        key="time_since_last_reading",
        field="createdAt",
        translation_key="time_since_last_reading",
        device_class=SensorDeviceClass.DURATION,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


class KradoSensorEntity(KradoEntity, SensorEntity):
    """Krado sensor entity."""

    entity_description: KradoSensorEntityDescription

    @property
    def available(self) -> bool:
        """Test if entity is available."""
        return super().available and _has_leaflet(self.plant)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the healthy range for status sensors."""
        if not (range_field := self.entity_description.range_field):
            return None
        low, high = self.plant["sensor"][range_field]
        return {"low": low, "high": high}

    @property
    def native_value(self) -> int | str | None:
        """Return the value reported by the sensor."""
        data = self.plant
        if self.entity_description.is_reading:
            data = data["sensor"]["lastReading"]
            if data is None:
                return None
        value = data[self.entity_description.field]
        if value is None:
            return value
        if self.device_class == SensorDeviceClass.DURATION:
            return (datetime.now(UTC) - datetime.fromisoformat(value)).total_seconds()
        if self.device_class == SensorDeviceClass.TIMESTAMP:
            return datetime.fromisoformat(value)
        if isinstance(value, str):
            value = value.lower()
        if self.device_class == SensorDeviceClass.ENUM and value not in self.options:
            _LOGGER.warning("%s has an unknown value: %s", self.name, value)
            self.entity_description.options.append(value)
        return value

    async def async_added_to_hass(self) -> None:
        self._handle_coordinator_update()
        await super().async_added_to_hass()
        if self.device_class == SensorDeviceClass.DURATION:
            self.async_on_remove(
                async_track_time_interval(
                    self.hass, self._update_entity_state, timedelta(minutes=1)
                )
            )

    async def _update_entity_state(self, now: datetime | None = None) -> None:
        """Update the state of the entity."""
        self._handle_coordinator_update()
