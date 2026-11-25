"""Support for Krado."""

from __future__ import annotations

from homeassistant.const import CONF_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN
from .coordinator import KradoConfigEntry, KradoCoordinator
from .pykrado import Krado

PLATFORMS = [
    Platform.IMAGE,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: KradoConfigEntry) -> bool:
    """Set up Krado from a config entry."""
    client = Krado(entry.data[CONF_TOKEN])
    coordinator = KradoCoordinator(hass, entry, client)
    entry.async_on_unload(client.close)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    @callback
    def _async_remove_stale_devices() -> None:
        """Remove devices for plants the API no longer returns."""
        if not coordinator.last_update_success:
            return
        plant_ids = {plant["id"] for plant in coordinator.data}
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            if not any(
                domain == DOMAIN and identifier in plant_ids
                for domain, identifier in device.identifiers
            ):
                device_registry.async_remove_device(device.id)

    _async_remove_stale_devices()
    entry.async_on_unload(coordinator.async_add_listener(_async_remove_stale_devices))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: KradoConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: KradoConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow manual removal of a device only once its plant is gone."""
    coordinator = entry.runtime_data
    return not any(
        domain == DOMAIN and coordinator.get_plant(identifier)
        for domain, identifier in device_entry.identifiers
    )
