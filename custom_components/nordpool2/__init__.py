"""GitHub Custom Component."""
import asyncio
import logging

from homeassistant import config_entries, core

DOMAIN = "nordpool2"
REGIONS = ["AT", "BE", "Bergen", "DE-LU", "DK1", "DK2", "EE", "FI", "FR", "Kr.sand", "LT", "LV", "Molde", "NL", "Oslo", "SE1", "SE2", "SE3", "SE4", "SYS", "Tr.heim", "Tromsø"]
CURRENCY_TO_CENTS = {"DKK": "øre", "EUR": "c", "NOK": "øre", "SEK": "öre"}


async def async_setup_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Set up platform from a ConfigEntry."""
    hass.data.setdefault(DOMAIN, {})
    hass_data = dict(entry.data)
    # Registers update listener to update config entry when options are updated.
    unsub_options_update_listener = entry.add_update_listener(options_update_listener)
    # Store a reference to the unsubscribe function to cleanup if an entry is unloaded.
    hass_data["unsub_options_update_listener"] = unsub_options_update_listener

    hass.data[DOMAIN] = hass_data

    # Forward the setup to the sensor platform.
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True


async def options_update_listener(
    hass: core.HomeAssistant, config_entry: config_entries.ConfigEntry
):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry)


async def async_unload_entry(
    hass: core.HomeAssistant, entry: config_entries.ConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[hass.config_entries.async_forward_entry_unload(entry, "sensor")]
        )
    )
    # Remove options_update_listener.
    hass.data[DOMAIN]["unsub_options_update_listener"]()

    # Remove config entry from domain.
    if unload_ok:
        hass.data.pop(DOMAIN)

    return unload_ok


async def async_setup(hass: core.HomeAssistant, config: dict) -> bool:
    """Set up the GitHub Custom component from yaml configuration."""
    hass.data.setdefault(DOMAIN, {})
    return True
