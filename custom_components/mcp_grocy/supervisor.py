"""Read the mcp-grocy app state through the Supervisor (only on HA OS / Supervised)."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.hassio import is_hassio

from .const import APP_PORT, APP_SLUG_SUFFIX, MCP_PATH

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class AppStatus:
    """Subset of the Supervisor app info the integration cares about."""

    slug: str
    name: str
    hostname: str
    state: str
    version: str | None
    update_available: bool

    @property
    def url(self) -> str:
        """Streamable HTTP endpoint reachable on the Supervisor internal network."""
        return f"http://{self.hostname}:{APP_PORT}{MCP_PATH}"


async def async_get_app(hass: HomeAssistant, slug: str) -> AppStatus | None:
    """Return the app status for `slug`, or None when unavailable."""
    if not is_hassio(hass):
        return None
    # Imported lazily: the hassio component is only loadable on Supervisor installs.
    from aiohasupervisor import SupervisorError  # noqa: PLC0415
    from homeassistant.components.hassio import get_supervisor_client  # noqa: PLC0415

    try:
        info = await get_supervisor_client(hass).addons.addon_info(slug)
    except SupervisorError as err:
        _LOGGER.debug("Cannot read app %s: %s", slug, err)
        return None
    state = getattr(info.state, "value", info.state)
    return AppStatus(
        slug=info.slug,
        name=info.name,
        hostname=info.hostname,
        state=str(state),
        version=info.version,
        update_available=bool(info.update_available),
    )


async def async_find_app(hass: HomeAssistant) -> AppStatus | None:
    """Find the installed mcp-grocy app whatever repository hash prefixes its slug."""
    if not is_hassio(hass):
        return None
    from aiohasupervisor import SupervisorError  # noqa: PLC0415
    from homeassistant.components.hassio import get_supervisor_client  # noqa: PLC0415

    try:
        installed = await get_supervisor_client(hass).addons.list()
    except SupervisorError as err:
        _LOGGER.debug("Cannot list apps: %s", err)
        return None
    for app in installed:
        if app.slug.endswith(APP_SLUG_SUFFIX):
            return await async_get_app(hass, app.slug)
    return None
