"""Config flow: discover the mcp-grocy app and hand it off to the core `mcp` integration.

Steps
-----
hassio          <- Supervisor discovery {"service": "mcp_grocy", "config": {"url": ...}}
hassio_confirm  <- one-click confirmation (confirm-only form)
user            <- manual fallback; the URL is prefilled from the Supervisor when the app is installed

On confirmation the flow:
1. probes the Streamable HTTP endpoint (a 401 means the server was started with an access
   token, which Home Assistant's core client cannot send -> auth_required),
2. reuses an existing core `mcp` entry for the same URL, or creates one by starting the
   core `mcp` user step programmatically (core has no import step; see docs/home-assistant-hacs.md),
3. creates its own entry that remembers the linked core entry and exposes a health sensor.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

try:  # HA >= 2026.9 ships probatio (voluptuous stays importable as an alias)
    import probatio as vol
except ImportError:  # HA 2026.2 - 2026.8
    import voluptuous as vol

from homeassistant.config_entries import SOURCE_USER, ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_URL
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import (
    CONF_MANAGED_MCP_ENTRY,
    CONF_MCP_ENTRY_ID,
    CONF_SLUG,
    CORE_MCP_DOMAIN,
    DOMAIN,
    EXAMPLE_URL,
    PROBE_TIMEOUT,
)
from .supervisor import async_find_app

_LOGGER = logging.getLogger(__name__)

# Abort reasons of the core `mcp` flow that are surfaced verbatim.
_CORE_ABORT_PASSTHROUGH = {
    "already_configured",
    "missing_capabilities",
    "cannot_connect",
    "timeout_connect",
}


class McpGrocyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MCP Grocy."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize flow state."""
        self._url: str | None = None
        self._slug: str | None = None
        self._addon_name: str | None = None
        self._mcp_entry_id: str | None = None
        self._managed = False

    # ------------------------------------------------------------------ discovery
    async def async_step_hassio(self, discovery_info: HassioServiceInfo) -> ConfigFlowResult:
        """Handle the Supervisor discovery message sent by the app (service `mcp_grocy`)."""
        try:
            url = cv.url(discovery_info.config.get(CONF_URL))
        except (vol.Invalid, ValueError):
            _LOGGER.debug("Ignoring discovery from %s: invalid URL", discovery_info.slug)
            return self.async_abort(reason="invalid_discovery_info")

        # unique_id == Supervisor discovery uuid: HA deletes the entry when the app is
        # uninstalled (hassio.discovery.async_process_del) and a re-discovery with a new
        # URL updates the stored entry in place.
        await self.async_set_unique_id(discovery_info.uuid)
        self._abort_if_unique_id_configured(updates={CONF_URL: url})
        self._async_abort_entries_match({CONF_URL: url})

        self._url = url
        self._slug = discovery_info.slug
        self._addon_name = discovery_info.name
        self.context["title_placeholders"] = {"addon": discovery_info.name}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm the discovered app."""
        if user_input is None:
            self._set_confirm_only()
            return self.async_show_form(
                step_id="hassio_confirm",
                description_placeholders={
                    "addon": self._addon_name or "",
                    "url": self._url or "",
                },
            )
        # The card may have been created before the user added the same URL manually.
        self._async_abort_entries_match({CONF_URL: self._url})
        if (error := await self._async_handoff()) is not None:
            return self.async_abort(reason=error)
        return self._async_finish()

    # ------------------------------------------------------------------ manual
    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manual setup (also the fallback when discovery is off in the app)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                url = cv.url(user_input[CONF_URL])
            except (vol.Invalid, ValueError):
                errors[CONF_URL] = "invalid_url"
            else:
                self._async_abort_entries_match({CONF_URL: url})
                self._url = url
                if (error := await self._async_handoff()) is None:
                    return self._async_finish()
                if error == "already_configured":
                    return self.async_abort(reason=error)
                errors["base"] = error
        elif (app := await async_find_app(self.hass)) is not None:
            # Prefill from the installed app (hostname on the Supervisor network).
            self._url = app.url
            self._slug = app.slug
            self._addon_name = app.name

        url_field = (
            vol.Required(CONF_URL, default=self._url) if self._url else vol.Required(CONF_URL)
        )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({url_field: str}),
            errors=errors,
            description_placeholders={
                "addon": self._addon_name or "-",
                "example_url": EXAMPLE_URL,
            },
        )

    # ------------------------------------------------------------------ hand-off
    async def _async_probe(self) -> str | None:
        """GET the Streamable HTTP endpoint to classify reachability / auth.

        mcp-grocy answers 405 (Allow: POST) to a session-less GET when no access token is
        configured, and 401 when the server was started with MCP_HTTP_ACCESS_TOKEN.
        """
        assert self._url is not None
        try:
            resp = await get_async_client(self.hass).get(self._url, timeout=PROBE_TIMEOUT)
        except httpx.TimeoutException:
            return "timeout_connect"
        except httpx.HTTPError:
            return "cannot_connect"
        if resp.status_code == 401:
            return "auth_required"
        return None

    async def _async_handoff(self) -> str | None:
        """Link or create the core `mcp` config entry. Return an error key or None."""
        if (error := await self._async_probe()) is not None:
            return error
        assert self._url is not None

        for entry in self.hass.config_entries.async_entries(CORE_MCP_DOMAIN):
            if entry.data.get(CONF_URL) == self._url:
                self._mcp_entry_id, self._managed = entry.entry_id, False
                return None

        data: dict[str, Any] = {CONF_URL: self._url}
        if self._slug:
            # Stored verbatim by core; on HA >= 2026.10 it names the LLM API "mcp-<slug>",
            # exactly like core's own app discovery does.
            data[CONF_SLUG] = self._slug

        # Core `mcp` has no import step; its user step accepts data programmatically and
        # runs validate_input() (initialize + tools capability check) before creating.
        result = await self.hass.config_entries.flow.async_init(
            CORE_MCP_DOMAIN, context={"source": SOURCE_USER}, data=data
        )
        if result["type"] is FlowResultType.CREATE_ENTRY:
            self._mcp_entry_id, self._managed = result["result"].entry_id, True
            return None

        if result["type"] is FlowResultType.ABORT:
            reason = result.get("reason", "unknown")
            if reason in _CORE_ABORT_PASSTHROUGH:
                return reason
            # "missing_credentials": the server answered 401 and core went down its OAuth path.
            return "auth_required"

        # FORM (with errors): do not leave a dangling core flow behind.
        try:
            self.hass.config_entries.flow.async_abort(result["flow_id"])
        except UnknownFlow:
            pass
        if result.get("step_id") != "user":
            return "auth_required"
        errors = result.get("errors") or {}
        return errors.get("base") or errors.get(CONF_URL) or "unknown"

    def _async_finish(self) -> ConfigFlowResult:
        """Create our own entry (health sensor + link to the core entry)."""
        title = f"MCP Grocy ({self._addon_name})" if self._addon_name else "MCP Grocy"
        return self.async_create_entry(
            title=title,
            data={
                CONF_URL: self._url,
                CONF_SLUG: self._slug,
                CONF_MCP_ENTRY_ID: self._mcp_entry_id,
                CONF_MANAGED_MCP_ENTRY: self._managed,
            },
        )
