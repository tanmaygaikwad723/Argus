#!/usr/bin/env bash
set -euo pipefail

GRAPH_NAME="${GRAPH_NAME:-Geopolitics}"
REDIS_CLI_BIN="${REDIS_CLI_BIN:-redis-cli}"

if ! command -v "$REDIS_CLI_BIN" >/dev/null 2>&1; then
  echo "redis-cli not found in PATH" >&2
  exit 1
fi

run_query() {
  local query="$1"
  "$REDIS_CLI_BIN" GRAPH.QUERY "$GRAPH_NAME" "$query"
}

run_query "CREATE INDEX FOR (e:Event) ON (e.externalid)"
run_query "CREATE INDEX FOR (y:Year) ON (y.value)"
run_query "CREATE INDEX FOR (p:Publisher) ON (p.name)"
run_query "CREATE INDEX FOR (n:NewsArticle) ON (n.url)"
run_query "CREATE INDEX FOR (a:Actor) ON (a.name)"
run_query "CREATE INDEX FOR (l:Location) ON (l.name)"

echo "FalkorDB constraints/indexes applied for graph: $GRAPH_NAME"
