"""Poll the mcp-grocy health endpoint (and, on Supervisor, the app state)."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_SLUG, DOMAIN, HEALTH_SCAN_INTERVAL, PROBE_TIMEOUT
from .supervisor import AppStatus, async_get_app

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class McpGrocyHealth:
    """Snapshot of server + app health."""

    reachable: bool
    server_version: str | None
    app: AppStatus | None


def health_url(mcp_url: str) -> str:
    """`http://host:port/mcp` -> `http://host:port/` (mcp-grocy health endpoint)."""
    parts = urlsplit(mcp_url)
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


class McpGrocyCoordinator(DataUpdateCoordinator[McpGrocyHealth]):
    """Health coordinator; never raises so the sensor simply turns off when the app is down."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=HEALTH_SCAN_INTERVAL,
        )
        self.entry = entry
        self._health_url = health_url(entry.data[CONF_URL])
        self._slug: str | None = entry.data.get(CONF_SLUG)

    async def _async_update_data(self) -> McpGrocyHealth:
        reachable, version = False, None
        try:
            resp = await get_async_client(self.hass).get(
                self._health_url, timeout=PROBE_TIMEOUT
            )
            payload = resp.json() if resp.status_code == 200 else {}
            reachable = payload.get("status") == "ok"
            version = payload.get("version")
        except (httpx.HTTPError, ValueError) as err:
            _LOGGER.debug("Health check failed for %s: %s", self._health_url, err)
        app = await async_get_app(self.hass, self._slug) if self._slug else None
        return McpGrocyHealth(reachable=reachable, server_version=version, app=app)


type McpGrocyConfigEntry = ConfigEntry[McpGrocyCoordinator]
