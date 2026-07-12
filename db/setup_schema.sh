#!/bin/bash
# =============================================================
# GEOPOLITICAL EVENT GRAPH — FalkorDB Schema Setup
# Runs entirely via redis-cli inside the container
#
# HOW TO USE (run from your host machine):
#
#   1. Copy into container:
#      docker cp setup_schema.sh <container_name>:/setup_schema.sh
#
#   2. Run inside container:
#      docker exec <container_name> bash /setup_schema.sh
#
#   OR skip the copy step entirely:
#      docker exec -i <container_name> bash < setup_schema.sh
# =============================================================

set -e  # stop immediately if any command fails

GRAPH="geopolitics"

echo ""
echo "====================================================="
echo " FalkorDB Schema Setup  →  graph: $GRAPH"
echo "====================================================="


# ── INDEXES ──────────────────────────────────────────────────
# echo ""
# echo "--- Creating Indexes ---"

# # Event
# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (e:Event) ON (e.externalid)"
# echo "  ✓ Event.externalid"

# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (e:Event) ON (e.date)"
# echo "  ✓ Event.date"

# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (e:Event) ON (e.quad_class)"
# echo "  ✓ Event.quad_class"

# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (e:Event) ON (e.cameo_code)"
# echo "  ✓ Event.cameo_code"

# # Actor
# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (a:Actor) ON (a.code)"
# echo "  ✓ Actor.code"

# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (a:Actor) ON (a.name)"
# echo "  ✓ Actor.name"

# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (a:Actor) ON (a.category)"
# echo "  ✓ Actor.category"

# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (a:Actor) ON (a.country_code)"
# echo "  ✓ Actor.country_code"

# # Location
# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (l:Location) ON (l.name)"
# echo "  ✓ Location.name"

# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (l:Location) ON (l.country_code)"
# echo "  ✓ Location.country_code"

# # Source
# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (s:Source) ON (s.name)"
# echo "  ✓ Source.name"

# # NewsArticle
# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (n:NewsArticle) ON (n.url)"
# echo "  ✓ NewsArticle.url"

# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (n:NewsArticle) ON (n.externalid)"
# echo "  ✓ NewsArticle.externalid"

# # Organization
# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (o:Organization) ON (o.name)"
# echo "  ✓ Organization.name"

# # Theme
# redis-cli GRAPH.QUERY $GRAPH "CREATE INDEX FOR (t:Theme) ON (t.type)"
# echo "  ✓ Theme.type"


# ── CONSTRAINTS ───────────────────────────────────────────────
echo ""
echo "--- Creating Unique Constraints ---"

redis-cli GRAPH.CONSTRAINT CREATE $GRAPH UNIQUE NODE Event        PROPERTIES 1 externalid
echo "  ✓ UNIQUE  Event.externalid"

redis-cli GRAPH.CONSTRAINT CREATE $GRAPH UNIQUE NODE Location     PROPERTIES 1 name
echo "  ✓ UNIQUE  Location.name"

redis-cli GRAPH.CONSTRAINT CREATE $GRAPH UNIQUE NODE NewsArticle  PROPERTIES 1 url
echo "  ✓ UNIQUE  NewsArticle.url"

redis-cli GRAPH.CONSTRAINT CREATE $GRAPH UNIQUE NODE NewsArticle  PROPERTIES 1 externalid
echo "  ✓ UNIQUE  NewsArticle.externalid"

echo "--- Creating Mandatory Constraints ---"

redis-cli GRAPH.CONSTRAINT CREATE $GRAPH MANDATORY NODE Event       PROPERTIES 1 externalid
echo "  ✓ MANDATORY  Event.externalid"

redis-cli GRAPH.CONSTRAINT CREATE $GRAPH MANDATORY NODE Event       PROPERTIES 1 date
echo "  ✓ MANDATORY  Event.date"

redis-cli GRAPH.CONSTRAINT CREATE $GRAPH MANDATORY NODE Actor       PROPERTIES 1 name
echo "  ✓ MANDATORY  Actor.code"

redis-cli GRAPH.CONSTRAINT CREATE $GRAPH MANDATORY NODE NewsArticle PROPERTIES 1 url
echo "  ✓ MANDATORY  NewsArticle.url"


# ── VERIFY ────────────────────────────────────────────────────
echo ""
echo "--- Verification ---"
echo "Indexes:"
redis-cli GRAPH.QUERY $GRAPH "CALL db.indexes()"

echo ""
echo "Constraints:"
redis-cli GRAPH.CONSTRAINT QUERY $GRAPH

echo ""
echo "====================================================="
echo " Schema setup complete."
echo "====================================================="
