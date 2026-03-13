#!/usr/bin/env bash
# pull-framework.sh — Pull MAO framework updates from claude_workspace template into the current project
#
# Usage (from any project that uses the MAO framework):
#   .claude/tools/pull-framework.sh [path-to-template]
#
# What it syncs (generic framework — WILL overwrite):
#   - Hooks: .claude/hooks/ (2 consolidated + lib/)
#   - Docs: .claude/docs/ (all generic guides, skips <project>-guide.md)
#   - Tools: .claude/tools/ (reset-mcps.sh, pull-framework.sh)
#   - Skills: implementation-plan, walkthrough (generic artifact skills)
#   - Settings: hooks section of settings.local.json (merges with existing permissions)
#
# What it preserves (project-specific — NEVER touched):
#   - .mcp.json, .envrc, CLAUDE.md
#   - .claude/docs/<project>-guide.md
#   - .claude/skills/<project>-* (project patterns and workflows)
#   - .claude/settings.local.json permissions and enabledMcpjsonServers
#   - .claude/artifacts/

set -euo pipefail

# Resolve template path
TEMPLATE="${1:-/home/tohigu/projects/spandrel/claude_workspace}"
PROJECT="$(pwd)"

if [[ ! -d "$TEMPLATE/.claude" ]]; then
    echo "ERROR: Template not found at $TEMPLATE/.claude"
    echo "Usage: .claude/tools/pull-framework.sh [path-to-claude-workspace]"
    exit 1
fi

if [[ ! -d "$PROJECT/.claude" ]]; then
    echo "ERROR: Not in a project with .claude/ directory"
    exit 1
fi

echo "=== Pulling MAO framework updates ==="
echo "  Template: $TEMPLATE"
echo "  Project:  $PROJECT"
echo ""

# Track changes for summary
CHANGES=()

# --- 1. Hooks (full replace) ---
echo "  [hooks] Syncing consolidated hooks + lib..."
rm -rf "$PROJECT/.claude/hooks/lib/__pycache__/"
for f in pre-tool-gate.py post-tool-trace.py; do
    if ! diff -q "$TEMPLATE/.claude/hooks/$f" "$PROJECT/.claude/hooks/$f" >/dev/null 2>&1; then
        /bin/cp "$TEMPLATE/.claude/hooks/$f" "$PROJECT/.claude/hooks/$f"
        CHANGES+=("hooks/$f")
        echo "    updated $f"
    fi
done

# Sync lib/ directory
mkdir -p "$PROJECT/.claude/hooks/lib"
for f in "$TEMPLATE/.claude/hooks/lib/"*.py; do
    basename=$(basename "$f")
    if ! diff -q "$f" "$PROJECT/.claude/hooks/lib/$basename" >/dev/null 2>&1; then
        /bin/cp "$f" "$PROJECT/.claude/hooks/lib/$basename"
        CHANGES+=("hooks/lib/$basename")
        echo "    updated lib/$basename"
    fi
done

# --- 2. Docs (sync generic, skip project-specific) ---
echo ""
echo "  [docs] Syncing generic framework docs..."
for f in "$TEMPLATE/.claude/docs/"*.md; do
    basename=$(basename "$f")
    # Skip templates
    [[ "$basename" == *.template ]] && continue
    # Skip if project has a project-specific guide with this name pattern
    # (project guides match *_*-guide.md like rfp_gatherer-guide.md)
    if [[ -f "$PROJECT/.claude/docs/$basename" ]]; then
        # Check if this is a project-specific file (contains project ID pattern)
        # Generic docs: INDEX.md, usage-guide.md, architecture-overview.md, etc.
        # Project docs: rfp_gatherer-guide.md, my_app-guide.md, etc.
        # Heuristic: if the file exists in the template, it's generic → sync it
        if ! diff -q "$f" "$PROJECT/.claude/docs/$basename" >/dev/null 2>&1; then
            /bin/cp "$f" "$PROJECT/.claude/docs/$basename"
            CHANGES+=("docs/$basename")
            echo "    updated $basename"
        fi
    else
        # New doc from template — only copy if it's not a project-guide template
        /bin/cp "$f" "$PROJECT/.claude/docs/$basename"
        CHANGES+=("docs/$basename (new)")
        echo "    added $basename"
    fi
done

# --- 3. Tools (full replace) ---
echo ""
echo "  [tools] Syncing CLI tools..."
mkdir -p "$PROJECT/.claude/tools"
for f in "$TEMPLATE/.claude/tools/"*.sh; do
    basename=$(basename "$f")
    if ! diff -q "$f" "$PROJECT/.claude/tools/$basename" >/dev/null 2>&1; then
        /bin/cp "$f" "$PROJECT/.claude/tools/$basename"
        chmod +x "$PROJECT/.claude/tools/$basename"
        CHANGES+=("tools/$basename")
        echo "    updated $basename"
    fi
done

# --- 4. Generic skills (implementation-plan, walkthrough) ---
echo ""
echo "  [skills] Syncing generic artifact skills..."
for skill in implementation-plan walkthrough; do
    if [[ -f "$TEMPLATE/.claude/skills/$skill/SKILL.md" ]]; then
        mkdir -p "$PROJECT/.claude/skills/$skill"
        if ! diff -q "$TEMPLATE/.claude/skills/$skill/SKILL.md" "$PROJECT/.claude/skills/$skill/SKILL.md" >/dev/null 2>&1; then
            /bin/cp "$TEMPLATE/.claude/skills/$skill/SKILL.md" "$PROJECT/.claude/skills/$skill/SKILL.md"
            CHANGES+=("skills/$skill/SKILL.md")
            echo "    updated $skill"
        fi
    fi
done

# --- 5. Settings: merge hooks from template, preserve project permissions ---
echo ""
echo "  [settings] Merging hook configuration..."
if command -v python3 >/dev/null 2>&1; then
    python3 - "$TEMPLATE/.claude/settings.local.json" "$PROJECT/.claude/settings.local.json" << 'PYEOF'
import json, sys

template_path, project_path = sys.argv[1], sys.argv[2]

with open(template_path) as f:
    template = json.load(f)
with open(project_path) as f:
    project = json.load(f)

# Take hooks from template (generic framework config)
new_hooks = template.get("hooks", {})
old_hooks = project.get("hooks", {})

# Take permissions from project (project-specific)
# But merge in any new MCP permissions from template that project doesn't have
template_perms = set(template.get("permissions", {}).get("allow", []))
project_perms = set(project.get("permissions", {}).get("allow", []))

# Add MCP permissions from template that aren't in project (new tools)
new_mcp_perms = {p for p in template_perms if p.startswith("mcp__") and p not in project_perms}
merged_perms = sorted(project_perms | new_mcp_perms)

changed = False
if new_hooks != old_hooks:
    project["hooks"] = new_hooks
    changed = True
if new_mcp_perms:
    project["permissions"]["allow"] = merged_perms
    changed = True

if changed:
    with open(project_path, "w") as f:
        json.dump(project, f, indent=2)
        f.write("\n")
    print("    updated settings.local.json (hooks" + (f" + {len(new_mcp_perms)} new permissions)" if new_mcp_perms else ")"))
else:
    print("    settings.local.json already up to date")

sys.exit(0 if changed else 2)  # exit 2 = no changes (not an error)
PYEOF
    exit_code=$?
    [[ $exit_code -eq 0 ]] && CHANGES+=("settings.local.json")
else
    echo "    SKIP: python3 not available for settings merge"
fi

# --- Summary ---
echo ""
if [[ ${#CHANGES[@]} -eq 0 ]]; then
    echo "=== No changes — project is up to date with template ==="
else
    echo "=== Updated ${#CHANGES[@]} files ==="
    for c in "${CHANGES[@]}"; do
        echo "  .claude/$c"
    done
    echo ""
    echo "Review changes with: git diff .claude/"
fi
