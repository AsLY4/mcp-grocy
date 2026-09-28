"""Config-flow tests for mcp_grocy (no Home Assistant instance needed).

    python -m venv .venv-ha && . .venv-ha/bin/activate   # Python 3.14
    pip install -r requirements_test.txt     # pytest-homeassistant-custom-component tracks HA core
    pytest tests/custom_components -p no:cacheprovider
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.mcp_grocy.const import (
    CONF_MANAGED_MCP_ENTRY,
    CONF_MCP_ENTRY_ID,
    DOMAIN,
)

URL = "http://local-mcp-grocy-api:8080/mcp"
DISCOVERY = HassioServiceInfo(
    config={"url": URL, "addon": "MCP Grocy API"},
    name="MCP Grocy API",
    slug="local_mcp_grocy_api",
    uuid="1234",
)


@pytest.fixture(autouse=True)
def _custom_integrations(enable_custom_integrations: None) -> None:
    """Custom integrations must be enabled explicitly."""


async def test_hassio_links_existing_core_entry(hass: HomeAssistant) -> None:
    """A core `mcp` entry for the same URL is reused, not duplicated."""
    mcp_entry = MockConfigEntry(domain="mcp", data={"url": URL}, title="mcp-grocy")
    mcp_entry.add_to_hass(hass)

    with (
        patch(
            "custom_components.mcp_grocy.config_flow.McpGrocyConfigFlow._async_probe",
            return_value=None,
        ),
        patch("custom_components.mcp_grocy.async_setup_entry", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=DISCOVERY
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "hassio_confirm"
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_MCP_ENTRY_ID] == mcp_entry.entry_id
    assert result["data"][CONF_MANAGED_MCP_ENTRY] is False
    assert result["result"].unique_id == "1234"


async def test_hassio_creates_core_entry(hass: HomeAssistant) -> None:
    """Without a core entry the flow starts the core `mcp` user step programmatically."""
    created = MockConfigEntry(domain="mcp", data={"url": URL}, title="mcp-grocy")
    created.add_to_hass(hass)  # stands in for the entry the core flow would create
    original_init = hass.config_entries.flow.async_init
    calls: list[tuple[str, dict]] = []

    async def fake_init(handler: str, *, context=None, data=None):
        if handler == "mcp":
            calls.append((handler, data))
            return {
                "type": FlowResultType.CREATE_ENTRY,
                "flow_id": "core-flow",
                "handler": "mcp",
                "result": created,
            }
        return await original_init(handler, context=context, data=data)

    with (
        patch.object(hass.config_entries.flow, "async_init", side_effect=fake_init),
        patch(
            "custom_components.mcp_grocy.config_flow.McpGrocyConfigFlow._async_probe",
            return_value=None,
        ),
        patch("custom_components.mcp_grocy.async_setup_entry", return_value=True),
    ):
        # The existing-entry check must not match: move the stand-in entry to another URL.
        hass.config_entries.async_update_entry(created, data={"url": "http://other/mcp"})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=DISCOVERY
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert calls == [("mcp", {"url": URL, "slug": "local_mcp_grocy_api"})]
    assert result["data"][CONF_MANAGED_MCP_ENTRY] is True


async def test_hassio_aborts_when_token_required(hass: HomeAssistant) -> None:
    """A 401 from the server (started with an access token) aborts with guidance."""
    with patch(
        "custom_components.mcp_grocy.config_flow.McpGrocyConfigFlow._async_probe",
        return_value="auth_required",
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_HASSIO}, data=DISCOVERY
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "auth_required"


async def test_user_step_invalid_url(hass: HomeAssistant) -> None:
    """The manual step validates the URL before probing anything."""
    with patch("custom_components.mcp_grocy.config_flow.async_find_app", return_value=None):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"url": "not a url"}
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"url": "invalid_url"}
