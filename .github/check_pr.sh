#!/usr/bin/env bash
# check_pr.sh — Validates PRs and issues for GraphRuntime registry contributions
# Used by GitHub Actions

set -euo pipefail

REPO="${GITHUB_REPOSITORY:-tryboy869/graphruntime}"
TOKEN="${GITHUB_TOKEN:-}"
PR_NUMBER="${PR_NUMBER:-}"
ISSUE_NUMBER="${ISSUE_NUMBER:-}"

log()  { echo "[CHECK_PR] $*"; }
fail() { echo "[FAIL] $*" >&2; exit 1; }
ok()   { echo "[OK] $*"; }

# ── Validate a registry graph.json PR ─────────────────────────────
validate_registry_pr() {
    log "Validating registry contribution PR #${PR_NUMBER}"

    # Find changed .json files in registry/
    CHANGED=$(git diff --name-only HEAD~1 HEAD | grep '^registry/.*\.json$' || true)

    if [[ -z "$CHANGED" ]]; then
        log "No registry JSON files changed — skipping registry validation"
        exit 0
    fi

    ERRORS=0

    for FILE in $CHANGED; do
        log "Checking: $FILE"

        # File must exist
        [[ -f "$FILE" ]] || { echo "  ✗ File not found: $FILE"; ERRORS=$((ERRORS+1)); continue; }

        # Must be valid JSON
        python3 -c "import json; json.load(open('$FILE'))" 2>/dev/null \
            || { echo "  ✗ Invalid JSON: $FILE"; ERRORS=$((ERRORS+1)); continue; }

        # Must have required fields
        python3 << PYEOF
import json, sys
data = json.load(open("$FILE"))
required = ["meta", "stats", "noeuds", "edges"]
missing  = [k for k in required if k not in data]
if missing:
    print(f"  ✗ Missing fields: {missing}")
    sys.exit(1)
stats = data.get("stats", {})
nodes = stats.get("fichiers_total", 0)
edges = stats.get("edges_total", 0)
if nodes < 3:
    print(f"  ✗ Too few nodes ({nodes}) — is this a real package?")
    sys.exit(1)
print(f"  ✓ {nodes} nodes, {edges} edges — looks good")
PYEOF
        rc=$?
        [[ $rc -ne 0 ]] && ERRORS=$((ERRORS+1))

        # Check file naming: language/package@version.json
        BASENAME=$(basename "$FILE")
        if [[ ! "$BASENAME" =~ ^[a-zA-Z0-9_\-]+(@[0-9]+\.[0-9]+.*)?\.json$ ]]; then
            echo "  ⚠ Non-standard filename: $BASENAME (expected: package@version.json)"
        fi

        ok "$FILE passed validation"
    done

    if [[ $ERRORS -gt 0 ]]; then
        fail "$ERRORS validation error(s) found"
    fi

    ok "All registry files validated"
}

# ── Check issue labels ─────────────────────────────────────────────
check_issue() {
    log "Checking issue #${ISSUE_NUMBER}"

    if [[ -z "$TOKEN" ]]; then
        log "No GitHub token — skipping issue check"
        exit 0
    fi

    ISSUE_DATA=$(curl -s -H "Authorization: token $TOKEN" \
        "https://api.github.com/repos/${REPO}/issues/${ISSUE_NUMBER}")

    TITLE=$(echo "$ISSUE_DATA" | python3 -c "import json,sys; print(json.load(sys.stdin).get('title',''))")
    log "Issue title: $TITLE"

    # Auto-label based on title keywords
    if echo "$TITLE" | grep -qi "registry\|graph\|package\|extract"; then
        log "Detected registry-related issue"
        curl -s -X POST \
            -H "Authorization: token $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"labels":["registry","contribution"]}' \
            "https://api.github.com/repos/${REPO}/issues/${ISSUE_NUMBER}/labels" > /dev/null
        ok "Labeled as registry/contribution"
    fi

    if echo "$TITLE" | grep -qi "bug\|error\|fail\|broken"; then
        log "Detected bug report"
        curl -s -X POST \
            -H "Authorization: token $TOKEN" \
            -H "Content-Type: application/json" \
            -d '{"labels":["bug"]}' \
            "https://api.github.com/repos/${REPO}/issues/${ISSUE_NUMBER}/labels" > /dev/null
        ok "Labeled as bug"
    fi
}

# ── Main ───────────────────────────────────────────────────────────
if [[ -n "$PR_NUMBER" ]]; then
    validate_registry_pr
elif [[ -n "$ISSUE_NUMBER" ]]; then
    check_issue
else
    log "Nothing to check (set PR_NUMBER or ISSUE_NUMBER)"
fi
