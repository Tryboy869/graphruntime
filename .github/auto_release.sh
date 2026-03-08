#!/usr/bin/env bash
# auto_release.sh — Detects new CHANGELOG sections and publishes a new version
# Also triggered when a new registry graph.json is merged

set -euo pipefail

log()  { echo "[RELEASE] $*"; }
fail() { echo "[FAIL] $*" >&2; exit 1; }
ok()   { echo "[OK] $*"; }

CHANGELOG="CHANGELOG.md"
PYPROJECT="pyproject.toml"
MODE="${1:-changelog}"   # changelog | registry

# ── Extract latest version from CHANGELOG ─────────────────────────
get_changelog_version() {
    grep -oP '## \[\K[0-9]+\.[0-9]+\.[0-9]+' "$CHANGELOG" | head -1
}

# ── Extract current version from pyproject.toml ───────────────────
get_current_version() {
    grep -oP 'version = "\K[^"]+' "$PYPROJECT" | head -1
}

# ── Bump patch version ─────────────────────────────────────────────
bump_patch() {
    local ver="$1"
    local major minor patch
    IFS='.' read -r major minor patch <<< "$ver"
    echo "${major}.${minor}.$((patch+1))"
}

# ── Update pyproject.toml version ─────────────────────────────────
update_version() {
    local new_ver="$1"
    sed -i "s/version = \"[^\"]*\"/version = \"${new_ver}\"/" "$PYPROJECT"
    ok "Updated pyproject.toml to ${new_ver}"
}

# ── Update index.json with new graph ──────────────────────────────
update_registry_index() {
    log "Updating registry/index.json with new graphs"

    python3 << 'PYEOF'
import json, os
from pathlib import Path

index_path = Path("registry/index.json")
packages   = []

if index_path.exists():
    existing = json.loads(index_path.read_text())
    packages = existing.get("packages", [])

existing_paths = {p["path"] for p in packages}

for lang_dir in ["python", "javascript", "rust", "go", "infra", "ai"]:
    lang_path = Path("registry") / lang_dir
    if not lang_path.exists():
        continue
    for f in sorted(lang_path.glob("*.json")):
        rel = f"registry/{lang_dir}/{f.name}"
        if rel in existing_paths:
            continue
        try:
            data = json.loads(f.read_text())
            name = f.stem.split("@")[0]
            ver  = f.stem.split("@")[1] if "@" in f.stem else "latest"
            packages.append({
                "name":     name,
                "version":  ver,
                "language": lang_dir,
                "path":     rel,
                "nodes":    data.get("stats", {}).get("fichiers_total", 0),
                "edges":    data.get("stats", {}).get("edges_total", 0),
            })
            print(f"  + Added: {rel}")
        except Exception as e:
            print(f"  ⚠ Skipped {f}: {e}")

packages.sort(key=lambda x: x["name"])
index_path.write_text(json.dumps(
    {"total": len(packages), "packages": packages},
    indent=2, ensure_ascii=False
))
print(f"  ✓ index.json updated — {len(packages)} packages")
PYEOF
}

# ── Create git tag and push ────────────────────────────────────────
create_release() {
    local version="$1"
    log "Creating release v${version}"

    git config user.email "actions@github.com"
    git config user.name  "GraphRuntime Bot"

    git add pyproject.toml registry/index.json CHANGELOG.md 2>/dev/null || true
    git commit -m "chore: release v${version} [skip ci]" 2>/dev/null || true
    git tag -a "v${version}" -m "Release v${version}"
    git push origin HEAD --tags

    ok "Released v${version}"
}

# ── Main ───────────────────────────────────────────────────────────
if [[ "$MODE" == "changelog" ]]; then
    CHANGELOG_VER=$(get_changelog_version)
    CURRENT_VER=$(get_current_version)

    log "Changelog version : $CHANGELOG_VER"
    log "Current version   : $CURRENT_VER"

    if [[ "$CHANGELOG_VER" != "$CURRENT_VER" && -n "$CHANGELOG_VER" ]]; then
        log "New version detected in CHANGELOG: $CHANGELOG_VER"
        update_version "$CHANGELOG_VER"
        update_registry_index
        create_release "$CHANGELOG_VER"
    else
        log "No new version in CHANGELOG — checking for registry updates"
        update_registry_index
        # If index changed, bump patch
        if git diff --quiet registry/index.json 2>/dev/null; then
            log "No registry changes"
        else
            NEW_VER=$(bump_patch "$CURRENT_VER")
            log "Registry updated — bumping patch to $NEW_VER"
            update_version "$NEW_VER"
            create_release "$NEW_VER"
        fi
    fi

elif [[ "$MODE" == "registry" ]]; then
    log "Registry mode — new graph accepted"
    update_registry_index
    CURRENT_VER=$(get_current_version)
    NEW_VER=$(bump_patch "$CURRENT_VER")
    update_version "$NEW_VER"
    create_release "$NEW_VER"
fi

ok "Done"
