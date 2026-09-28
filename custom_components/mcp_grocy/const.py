"""Constants for the MCP Grocy companion integration."""

from datetime import timedelta

DOMAIN = "mcp_grocy"
# Domain of the Home Assistant core client integration this integration hands off to.
CORE_MCP_DOMAIN = "mcp"

# Config-entry data keys (CONF_URL / CONF_ACCESS_TOKEN come from homeassistant.const).
CONF_SLUG = "slug"  # Supervisor app slug, e.g. "4aaa27b6_mcp_grocy_api"
CONF_MCP_ENTRY_ID = "mcp_entry_id"  # entry_id of the linked core `mcp` config entry
CONF_MANAGED_MCP_ENTRY = "managed_mcp_entry"  # True when this integration created that entry

# Slug declared in the app's config.yaml. The Supervisor prefixes it with the repository
# hash ("local_" for /addons), so only the suffix is stable across installs.
APP_SLUG_SUFFIX = "_mcp_grocy_api"
# Container port of the MCP server inside the app (fixed; host mappings are irrelevant here).
APP_PORT = 8080
MCP_PATH = "/mcp"
# Hint only: the real URL is prefilled from the Supervisor or typed by the user.
EXAMPLE_URL = "http://<repository-hash>-mcp-grocy-api:8080/mcp"

HEALTH_SCAN_INTERVAL = timedelta(seconds=60)
PROBE_TIMEOUT = 10
