"""MCP Grocy: thin companion integration for the mcp-grocy Home Assistant app.

It does three things and nothing else:
* receives the app's Supervisor discovery message and hands the URL to the core
  `mcp` integration (which is what actually exposes the tools to Assist),
* keeps that core entry in sync (URL changes) and removes it when the app goes away,
* exposes one connectivity sensor for the app/server health.
"""

from __future__ import annotations

import logging

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import CONF_MANAGED_MCP_ENTRY, CONF_MCP_ENTRY_ID, DOMAIN
from .coordinator import McpGrocyConfigEntry, McpGrocyCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: McpGrocyConfigEntry) -> bool:
    """Set up MCP Grocy from a config entry."""
    coordinator = McpGrocyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await _async_sync_core_entry(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_sync_core_entry(hass: HomeAssistant, entry: McpGrocyConfigEntry) -> None:
    """Warn when the linked core entry vanished; push URL changes to it when we own it."""
    issue_id = f"core_entry_missing_{entry.entry_id}"
    mcp_entry_id = entry.data.get(CONF_MCP_ENTRY_ID)
    mcp_entry = hass.config_entries.async_get_entry(mcp_entry_id) if mcp_entry_id else None

    if mcp_entry is None:
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="core_entry_missing",
            translation_placeholders={"url": entry.data[CONF_URL]},
        )
        return
    ir.async_delete_issue(hass, DOMAIN, issue_id)

    target = entry.data[CONF_URL]
    if not entry.data.get(CONF_MANAGED_MCP_ENTRY):
        if mcp_entry.data.get(CONF_URL) != target:
            _LOGGER.warning(
                "The Model Context Protocol entry %s points at %s while the app is reachable at %s; "
                "update that entry manually (it was not created by MCP Grocy)",
                mcp_entry.title,
                mcp_entry.data.get(CONF_URL),
                target,
            )
        return
    if mcp_entry.data.get(CONF_URL) != target:
        # A re-discovery updated our entry (new hostname); propagate to the core entry.
        hass.config_entries.async_update_entry(mcp_entry, data={**mcp_entry.data, CONF_URL: target})
        hass.config_entries.async_schedule_reload(mcp_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: McpGrocyConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: McpGrocyConfigEntry) -> None:
    """Remove the core `mcp` entry we created (app uninstalled or integration deleted)."""
    ir.async_delete_issue(hass, DOMAIN, f"core_entry_missing_{entry.entry_id}")
    if not entry.data.get(CONF_MANAGED_MCP_ENTRY):
        return
    mcp_entry_id = entry.data.get(CONF_MCP_ENTRY_ID)
    if mcp_entry_id and hass.config_entries.async_get_entry(mcp_entry_id) is not None:
        await hass.config_entries.async_remove(mcp_entry_id)
