# MCP Grocy API - Home Assistant App

This App (Home Assistant's name for add-ons since [2026.2](https://www.home-assistant.io/blog/2026/02/04/release-20262/)) runs the [mcp-grocy](https://github.com/miguelangel-nubla/mcp-grocy) MCP server next to Home Assistant and exposes it on the Supervisor's internal network: Streamable HTTP on `/mcp` (legacy SSE on `/mcp/sse`), container port 8080.

Home Assistant's built-in **Model Context Protocol** integration (`mcp`, in core since 2025.2, Streamable HTTP since 2026.2) connects to it directly and hands the Grocy tools to Assist and to any conversation agent (OpenAI, Anthropic, Google, Ollama, ...). No MCP proxy is needed any more, and no HACS component either: HACS distributes integrations, dashboards and themes, [never Apps](https://hacs.xyz/docs/faq/addons).

What you get:

- Ask your assistant what is in stock, what expires soon, what is on the shopping list, which recipes you can cook, which chores are due.
- A curated, read-only set of 15 tools by default. Write tools (add to shopping list, consume, purchase, ...) are opt-in, each behind a private acknowledgement token you choose.
- On Home Assistant 2026.10 and later the App announces itself: a **Discovered** card appears, one click connects it. On 2026.2 - 2026.9 you type one URL.

## Installation

1. Add this repository to your App store (Settings > Apps > App store > three dots > **Repositories**). Use the URL **with** `#main` to follow stable releases; without the fragment the Supervisor tracks the `dev` prerelease branch:

   ```text
   https://github.com/miguelangel-nubla/mcp-grocy#main
   ```

   [![Open your Home Assistant instance and show the add App repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmiguelangel-nubla%2Fmcp-grocy%23main)

2. Find **MCP Grocy API** in the store and click **Install**. There is no prebuilt image yet: the Supervisor builds the container from the repository's `Dockerfile` on your device (several minutes, longer on Raspberry Pi class hardware; needs internet access for `npm install`).
3. Open the **Configuration** tab, set `grocy_base_url` and `grocy_api_key` (see below), save, then **Start** the App. Enable **Watchdog** and **Start on boot** if you want the Supervisor to keep it running.

The App runs on `aarch64` and `amd64`.

### Migrating from a hand-made local App

If you built the server yourself as a local App (a `config.yaml`, `Dockerfile` and `run.sh` written by hand in `/addons/mcp-grocy`, as the earlier community how-tos described), first **uninstall that App** (Settings > Apps > your App > Uninstall; its `/addon_configs/<slug>/` folder and `mcp-grocy.yaml` are kept) - an uninstalled-but-still-running old App would keep host port 8080 and keep answering Home Assistant with the old tool profile. Then replace its files with a clone of this repository:

```bash
cd /addons && rm -rf mcp-grocy && git clone --branch main https://github.com/miguelangel-nubla/mcp-grocy.git mcp-grocy
```

Then Settings > Apps > App store > three dots > **Check for updates**, install **MCP Grocy API** from _Local apps_ and copy your options over. Differences to expect: the slug is `mcp_grocy_api` (hostname `local-mcp-grocy-api`), so the tools file now lives in `/addon_configs/local_mcp_grocy_api/mcp-grocy.yaml` - copy your existing `mcp-grocy.yaml` there before the first start, or let the App seed the read-only profile and edit it; port 8080 is no longer published on the host, so point the Model Context Protocol integration at `http://local-mcp-grocy-api:8080/mcp` instead of your Home Assistant IP (or map the port in the **Network** section to keep the old URL - only once the old App is gone); `enable_http_server`/`http_server_port` are ignored. Since server 2.8.0 the meal plan also accepts free-text notes (`recipes_mealplan_add_note`), so a `rest_command` workaround for notes is no longer needed.

## Configuration

Defaults as shipped in `config.yaml`:

```yaml
grocy_base_url: http://a0d7b954-grocy:80
grocy_api_key: your_grocy_api_key_here
enable_ssl_verify: true
rest_response_size_limit: 10000
home_assistant_discovery: auto
```

### Option: `grocy_base_url` (required)

Base URL of your Grocy instance. `http://a0d7b954-grocy:80` reaches the community **Grocy** App over the internal network; for an external instance use its full URL, e.g. `https://grocy.example.com`. Works with upstream Grocy 4.x and with [grocy-next](https://github.com/miguelangel-nubla/grocy-next).

### Option: `grocy_api_key` (required)

API key created in Grocy under **Manage API keys** (top-right menu). It is passed to Grocy in the `GROCY-API-KEY` header and never written to the App log.

### Option: `enable_ssl_verify` (optional, default `true`)

Set to `false` only for self-signed certificates on an HTTPS `grocy_base_url`.

### Option: `rest_response_size_limit` (optional, default `10000`, minimum `1000`)

Byte cap applied to the raw Grocy response returned by the `system_dev_test_request` developer tool (disabled in the default profile); the other tools are not affected. The 2.x App read a differently named option; this is the one that is actually applied.

### Option: `home_assistant_discovery` (optional, default `auto`)

How the App announces its MCP endpoint to Home Assistant through the Supervisor discovery API at every start:

| Value       | Behaviour                                                                                                                                                            |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `auto`      | Announce to the core **Model Context Protocol** integration when Home Assistant is 2026.10 or newer; on older versions only print the manual URL in the log.         |
| `core`      | Always announce to the core integration, regardless of the Home Assistant version (for beta testers of 2026.10; older cores log a traceback for every announcement). |
| `companion` | Announce to the optional **MCP Grocy** HACS companion integration instead (install it first, see below). Nothing is sent to the core integration in this mode.       |
| `off`       | Never announce. Add the integration manually with the URL from the Info page.                                                                                        |

Re-announcing is idempotent: the Supervisor keeps one discovery message per App and service, so restarting the App updates the existing entry instead of creating a second card.

### Legacy options: `enable_http_server`, `http_server_port` (ignored)

Kept so that 2.x configurations still validate. The server always runs, always on container port **8080**; setting these logs a warning and changes nothing. To reach the MCP endpoint from outside Home Assistant, map a host port in the **Network** section instead.

### Network: port `8080/tcp` (not mapped by default)

The MCP endpoint is **not authenticated**. Home Assistant's own client cannot send a static token (it supports no authentication or OAuth 2.0 only), so the App runs without one and, by default, does **not** publish port 8080 on the host: only containers on the Supervisor's internal network - Home Assistant itself and other Apps - can reach it. Map the port in the **Network** section only if an MCP client outside Home Assistant (Claude Desktop, Cursor, ...) needs it, and only on a network you trust. A static access token for the App is a possible future addition, not something the App supports today.

### Choosing which tools are exposed

The list of enabled tools and their acknowledgement tokens is the standard `mcp-grocy.yaml` of the server. In the App it lives in the App's configuration folder:

```text
/addon_configs/<repository-hash>_mcp_grocy_api/mcp-grocy.yaml
```

(`/app_configs/...` on Supervisor 2026.07 and newer, where `/addon_configs` is the legacy name; `/config/mcp-grocy.yaml` inside the container; the folder is visible to the **File editor**, **Studio Code Server** and **Samba share** Apps). On first start the App copies a Home Assistant profile there - **15 read-only tools**, no tokens - and never overwrites it afterwards. The file also lists, commented out, a proven "stock + shopping + chores + meal plan" profile (14 tools including write tools) to start from when the assistant should act, not only answer. Fewer tools mean smaller prompts and better results with small local models, and nothing in the default profile can modify your Grocy data.

To enable more tools:

1. Copy the entries you want from [`mcp-grocy.yaml.example`](https://github.com/miguelangel-nubla/mcp-grocy/blob/main/mcp-grocy.yaml.example) into that file. Give every **write** tool a **private** `ack_token` of your own; never reuse the example tokens, they are public and a model could quote them.

   ```yaml
   tools:
     shopping_list_add_item:
       enabled: true
       ack_token: a-private-random-phrase
   ```

2. Restart the App. An unknown tool name stops the App on purpose (instead of restarting forever); the log names it.
3. Reload the **Model Context Protocol** entry in Home Assistant (Settings > Devices & services > Model Context Protocol > three dots > Reload). Home Assistant otherwise re-reads the tool list only every 30 minutes.

Delete the file and restart the App to get the default profile back. Upgrading the App does not merge new default tools into an existing file; add them by hand.

## Connecting Home Assistant Assist

### Home Assistant 2026.10 and later: automatic

Core PR [#180378](https://github.com/home-assistant/core/pull/180378) (merged on the `dev` branch on 2026-08-29, expected in the 2026.10 release) teaches the Model Context Protocol integration to accept Supervisor App discovery. With `home_assistant_discovery: auto` (the default), a few seconds after the App starts:

1. Settings > **Devices & services** shows a **Discovered** card "Model Context Protocol server via Home Assistant app".
2. Click **Configure**, then **Submit**. Home Assistant connects to `http://<hostname>:8080/mcp`, lists the tools and creates the entry. Nothing to type.

Uninstalling the App removes the entry again. The App checks the Home Assistant version only when it starts: if it was already running when you upgraded Home Assistant to 2026.10, restart it once to get the card.

### Home Assistant 2026.2 - 2026.9: one URL to type

1. Settings > Devices & services > **Add integration** > **Model Context Protocol**.
2. Enter the URL and submit:

   ```text
   http://<hostname>:8080/mcp
   ```

   Use `/mcp` (Streamable HTTP, core PR [#161547](https://github.com/home-assistant/core/pull/161547)), not `/mcp/sse`: a POST to the SSE path answers 404, which the client does not retry with SSE. On Home Assistant 2025.2 - 2026.1 the client only speaks SSE; use `http://<hostname>:8080/mcp/sse` there. Home Assistant older than 2025.2 has no MCP client at all.

**The hostname rule.** `<hostname>` is the App's name on the Supervisor network, shown as **Hostname** on the App's **Info** page, and printed in the App log at every start. It is `<repository-hash>-mcp-grocy-api`, where `<repository-hash>` is the first 8 hex characters of the SHA-1 of the repository string **exactly as you entered it**, lowercased, `#branch` fragment included: `https://github.com/miguelangel-nubla/mcp-grocy#main` and the same URL without `#main` give two different hostnames. If you copied the App into `/addons`, the hostname is `local-mcp-grocy-api`. The port is always **8080** (the container port, independent of any host mapping). Do not read the hostname off someone else's screenshot; read it off your Info page.

### Then give the tools to an assistant (all versions)

1. Settings > **Voice assistants** > your assistant > open the options of its **conversation agent** (Ollama, OpenAI, Anthropic, Google, ...).
2. Under **Control Home Assistant**, tick **mcp-grocy** (the server's name; the LLM API id is `mcp-<app slug>` on 2026.10+). Tick **Assist** as well if the agent should also control your home; when both are selected the tools are namespaced `mcp-grocy__<tool>`, e.g. `mcp-grocy__inventory_stock_get_all`.
3. Ask: "What is expiring this week?", "What is on the shopping list?", "Can I cook lasagna tonight?".

Runtime facts worth knowing: Home Assistant only uses MCP _tools_ (the server's resources and prompts are ignored), opens a new MCP session per call, allows 10 s per tool call and refreshes the tool list every 30 minutes.

## Optional: the MCP Grocy HACS companion integration (experimental)

You do **not** need HACS for any of the above. The repository also contains `custom_components/mcp_grocy`, a thin custom integration for the cases the core integration does not cover:

- **One-click setup on Home Assistant 2026.2 - 2026.9**: with `home_assistant_discovery: companion` the App announces itself to this integration, which shows the Discovered card, asks you to confirm, then creates the core Model Context Protocol entry for you. Its manual step prefills the URL from the Supervisor when the App is installed.
- **A connectivity binary sensor** (`Server`, device class connectivity) that polls the server's health endpoint every minute, with attributes `url`, `server_version`, `mcp_entry_id` and, when the App is found through the Supervisor, `app_slug`, `app_state`, `app_version`, `app_update_available`.
- **Cleanup**: removing the integration (or uninstalling the App) removes the core entry it created; if that entry disappears on its own, a repair issue tells you.

It does not re-implement MCP, has no Python requirements, and does not add authentication: like the core integration it connects to the unauthenticated internal URL. The companion creates the core entry by starting the core integration's own user flow programmatically - undocumented core behaviour, checked against the core code of 2026.9 but not yet covered by an end-to-end test - which is why it is an experiment and off by default (`home_assistant_discovery: auto` never sends it anything). On 2026.10+ it is optional: pick either the core card (`auto`) or the companion (`companion`), not both.

Install it:

1. HACS > three dots > **Custom repositories** > URL `https://github.com/miguelangel-nubla/mcp-grocy`, category **Integration** > Add. HACS offers the integration's GitHub **releases** (prereleases only with "Show beta versions"); a fork without releases shows nothing.
2. Download **MCP Grocy**, restart Home Assistant.
3. Set `home_assistant_discovery: companion` in the App, restart the App, confirm the Discovered card - or add **MCP Grocy** manually under Settings > Devices & services > Add integration and enter the URL.

Requires Home Assistant 2026.2.0 or newer. The integration is checked in CI with hassfest, the HACS action and its pytest suite (Python 3.14, `pytest-homeassistant-custom-component`).

## Troubleshooting

**Read the log first** (App page > **Log**). Expected lines at start:

- `Creating /config/mcp-grocy.yaml from the Home Assistant profile (read-only tools)` - first start only.
- `Starting MCP Grocy API <version> (Grocy: <url>, SSL verify: true)`.
- `Announced http://<hostname>:8080/mcp to Home Assistant (service mcp)` on 2026.10+, or `Home Assistant <version> < 2026.10: no automatic discovery. Add the Model Context Protocol integration manually with URL http://<hostname>:8080/mcp` on older versions.

**Health endpoint.** `GET http://<hostname>:8080/` returns `{"status":"ok","service":"mcp-grocy","version":"...","endpoints":{"streamable":"/mcp","sse":"/mcp/sse",...}}`. The Supervisor watchdog polls it and restarts the App when it fails. To call it yourself, use another App on the internal network (for example the Terminal & SSH App: `curl http://<hostname>:8080/`) or temporarily map port 8080 and use your Home Assistant's IP.

**No Discovered card (2026.10+).** Check the log line above. If it says `< 2026.10`, the App started before Home Assistant was upgraded: restart the App (it reads the core version at start), or add the integration manually. If it says `Could not announce`, the Supervisor rejected the message; restart the App and, if it persists, open an issue with the log. `home_assistant_discovery: off` or `companion` never produce the core card.

**"Failed to connect" when adding the integration.** Check, in this order: the App is running (green state); the URL ends with `/mcp` (2026.2+) or `/mcp/sse` (2025.2 - 2026.1); the hostname is the one on the Info page (it changes when you re-add the repository with a different string, e.g. with or without `#main`); the port is 8080. Home Assistant reaches the App without any host port mapping.

**Integration set up but no tools listed / the assistant does not know about Grocy.**

- `mcp-grocy.yaml` in the App configuration folder enables no tools, or the App stopped because of an unknown tool name (log). Fix the file, restart the App, reload the Model Context Protocol entry.
- The entry was created before you edited the file: reload it, Home Assistant caches the tool list for 30 minutes.
- `mcp-grocy` is not ticked under **Control Home Assistant** in the conversation agent's options.

**Grocy errors in the log** (`ECONNREFUSED`, `401`, certificate errors): fix `grocy_base_url` (for the Grocy App use its internal hostname, `a0d7b954-grocy`, port 80), `grocy_api_key`, or set `enable_ssl_verify: false` for a self-signed certificate.

**Slow or failing tool calls.** Home Assistant aborts a call after 10 s. Keep fan-out tools such as `recipes_shopping_add_missing_products` disabled if your Grocy is slow.

**The App stops right after starting.** A configuration error halts the App instead of restarting it endlessly, so that the log stays readable; the last lines say why. The watchdog retries a few times with back-off and then gives up until you start it again.

**Official documentation mismatch.** The [Model Context Protocol integration page](https://www.home-assistant.io/integrations/mcp/) still describes an SSE URL and `mcp-proxy` at the time of writing; on 2026.2+ neither is needed with this App.

## Known limitations and next steps

Not done yet, tracked in [docs/home-assistant-hacs.md](https://github.com/miguelangel-nubla/mcp-grocy/blob/main/docs/home-assistant-hacs.md):

- **Prebuilt images.** The Supervisor builds the image locally because `config.yaml` has no `image:`. Publishing per-architecture images on each release (and making the GHCR packages public) is a follow-up.
- **Static access token.** The App cannot protect the MCP port with a token yet; keep port 8080 unmapped. The core integration could not use such a token anyway.
- **Tool titles and annotations.** Read-only tools already carry `readOnlyHint`; write tools do not yet declare `destructiveHint`/`idempotentHint`, so Home Assistant treats them with its conservative defaults.
- **Dev channel.** Prereleases on the `dev` branch do not bump the App version yet; follow `#main` for updates.

## Support

- Issues and questions: [github.com/miguelangel-nubla/mcp-grocy/issues](https://github.com/miguelangel-nubla/mcp-grocy/issues) - please attach the App log (it contains no secrets) and your Home Assistant version.
- Server documentation (tools, `mcp-grocy.yaml` reference, environment variables): the [README](https://github.com/miguelangel-nubla/mcp-grocy#readme) and [Configuration Guide](https://github.com/miguelangel-nubla/mcp-grocy/blob/main/src/resources/config.md).
- Design notes and the feasibility study behind this App: [docs/home-assistant-hacs.md](https://github.com/miguelangel-nubla/mcp-grocy/blob/main/docs/home-assistant-hacs.md).
