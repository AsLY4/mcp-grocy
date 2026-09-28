"""Connectivity sensor for the mcp-grocy app/server."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_MCP_ENTRY_ID, CONF_SLUG, DOMAIN
from .coordinator import McpGrocyConfigEntry, McpGrocyCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: McpGrocyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the health sensor."""
    async_add_entities([McpGrocyServerBinarySensor(entry.runtime_data)])


class McpGrocyServerBinarySensor(CoordinatorEntity[McpGrocyCoordinator], BinarySensorEntity):
    """On when GET / of the server answers {"status": "ok"}."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_has_entity_name = True
    _attr_translation_key = "server"

    def __init__(self, coordinator: McpGrocyCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        entry = coordinator.entry
        slug = entry.data.get(CONF_SLUG)
        self._attr_unique_id = f"{entry.entry_id}_server"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="miguelangel-nubla",
            model="mcp-grocy",
            entry_type=DeviceEntryType.SERVICE,
            # Deep link to the app page in the Home Assistant UI.
            configuration_url=f"homeassistant://hassio/addon/{slug}/info" if slug else None,
        )

    @property
    def is_on(self) -> bool:
        """Return True when the MCP server is reachable."""
        return self.coordinator.data.reachable

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose versions and app state for dashboards/automations."""
        data = self.coordinator.data
        entry = self.coordinator.entry
        attrs: dict[str, Any] = {
            "url": entry.data[CONF_URL],
            "server_version": data.server_version,
            "mcp_entry_id": entry.data.get(CONF_MCP_ENTRY_ID),
        }
        if data.app is not None:
            attrs.update(
                {
                    "app_slug": data.app.slug,
                    "app_state": data.app.state,
                    "app_version": data.app.version,
                    "app_update_available": data.app.update_available,
                }
            )
        return attrs
