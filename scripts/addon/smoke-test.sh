#!/usr/bin/env bash
# Boots the app image next to a mock Supervisor and checks, without Home Assistant:
#  1. the s6 longrun exports the options and starts the MCP HTTP server on 8080,
#  2. POST /mcp initialize + tools/list work (what HA's mcp integration does) and the
#     seeded /config/mcp-grocy.yaml enables tools,
#  3. the discovery oneshot sent {"service":"mcp","config":{"url":...}} to /discovery
#     (mock HA version 2026.10.0, so the version gate lets it through).
set -euo pipefail
IMAGE=${1:?usage: smoke-test.sh <image>}
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) # docker -v needs an absolute host path
NET=mcp-grocy-smoke-$$
WORK=$(mktemp -d)
CURL="docker run --rm --network ${NET} curlimages/curl:8.11.1"
trap 'docker rm -f mock-supervisor mcp-grocy-app >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; rm -rf "$WORK"' EXIT

cat > "$WORK/options.json" <<'JSON'
{"grocy_base_url":"http://grocy.invalid","grocy_api_key":"test","enable_ssl_verify":true,"rest_response_size_limit":10000,"home_assistant_discovery":"auto"}
JSON
mkdir -p "$WORK/config"

docker network create "$NET" >/dev/null
docker run -d --name mock-supervisor --network "$NET" --network-alias supervisor \
  -v "$SCRIPT_DIR/mock-supervisor.py:/mock.py:ro" -v "$WORK/options.json:/data/options.json:ro" \
  -e MOCK_RECORD_FILE=/tmp/discovery.json -e MOCK_HA_VERSION=2026.10.0 \
  python:3.12-alpine python /mock.py >/dev/null
# The Supervisor also writes /data/options.json into the container; bashio reads the
# options through the Supervisor API, so the mock is what really matters here.
docker run -d --name mcp-grocy-app --network "$NET" -e SUPERVISOR_TOKEN=test-token \
  -v "$WORK/options.json:/data/options.json:ro" -v "$WORK/config:/config" "$IMAGE" >/dev/null

# 1. server up (health endpoint)
for _ in $(seq 1 90); do
  if $CURL -fsS http://mcp-grocy-app:8080/ >/dev/null 2>&1; then break; fi
  sleep 1
done
$CURL -fsS http://mcp-grocy-app:8080/ | grep -q '"streamable":"/mcp"'

# 2. MCP handshake as HA does it (Streamable HTTP, JSON responses)
HDR=(-H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')
INIT='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"smoke","version":"0"}}}'
SID=$($CURL -sS -D - -o /dev/null "${HDR[@]}" -X POST --data "$INIT" http://mcp-grocy-app:8080/mcp \
  | tr -d '\r' | awk 'tolower($1)=="mcp-session-id:"{print $2}')
[ -n "$SID" ] || { echo "no Mcp-Session-Id"; docker logs mcp-grocy-app; exit 1; }
$CURL -sS -H "Mcp-Session-Id: $SID" "${HDR[@]}" -X POST \
  --data '{"jsonrpc":"2.0","method":"notifications/initialized"}' http://mcp-grocy-app:8080/mcp >/dev/null
TOOLS=$($CURL -sS -H "Mcp-Session-Id: $SID" "${HDR[@]}" -X POST \
  --data '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' http://mcp-grocy-app:8080/mcp)
COUNT=$(printf '%s' "$TOOLS" | grep -o '"name":"' | wc -l)
[ "$COUNT" -gt 0 ] || { echo "tools/list is empty (mcp-grocy.yaml not seeded?)"; echo "$TOOLS"; exit 1; }
echo "tools/list: $COUNT tools"

# 3. discovery message
for _ in $(seq 1 30); do
  if docker exec mock-supervisor test -s /tmp/discovery.json; then break; fi
  sleep 1
done
docker exec mock-supervisor cat /tmp/discovery.json | tee /dev/stderr \
  | grep -q '"service": *"mcp".*"url": *"http://local-mcp-grocy-api:8080/mcp"'
echo "OK: server, MCP handshake and discovery behave as Home Assistant expects"
