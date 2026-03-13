#!/usr/bin/env bash
# setup.sh — Deploy MAO framework into a project
#
# Run from the project root AFTER the subtree has been added:
#   git subtree add --prefix=.claude/framework <path-to-this-repo> main --squash
#   .claude/framework/setup.sh <project_id> [project_name]
#
# This copies templates, replaces placeholders, and creates project-specific dirs.
# Safe to re-run — skips files that already exist.

set -euo pipefail

PROJECT_ID="${1:?Usage: setup.sh <project_id> [project_name]}"
PROJECT_NAME="${2:-$PROJECT_ID}"
PROJECT_ROOT="$(git rev-parse --show-toplevel)"
FRAMEWORK_DIR="$PROJECT_ROOT/.claude/framework"
TEMPLATES="$FRAMEWORK_DIR/templates"

if [[ ! -d "$TEMPLATES" ]]; then
    echo "ERROR: Templates not found at $TEMPLATES"
    echo "Did you run: git subtree add --prefix=.claude/framework <repo> main --squash"
    exit 1
fi

echo "=== Deploying MAO framework ==="
echo "  Project ID:   $PROJECT_ID"
echo "  Project Name: $PROJECT_NAME"
echo "  Project Root: $PROJECT_ROOT"
echo ""

# Helper: copy template with placeholder replacement, skip if exists
deploy_template() {
    local src="$1" dst="$2"
    if [[ -f "$dst" ]]; then
        echo "  SKIP $dst (already exists)"
        return
    fi
    mkdir -p "$(dirname "$dst")"
    sed \
        -e "s|{{PROJECT_ID}}|$PROJECT_ID|g" \
        -e "s|{{PROJECT_NAME}}|$PROJECT_NAME|g" \
        -e "s|{{PROJECT_ROOT}}|$PROJECT_ROOT|g" \
        "$src" > "$dst"
    echo "  CREATE $dst"
}

# 1. Deploy root templates
echo "[templates]"
deploy_template "$TEMPLATES/CLAUDE.md" "$PROJECT_ROOT/CLAUDE.md"
deploy_template "$TEMPLATES/mcp.json" "$PROJECT_ROOT/.mcp.json"
deploy_template "$TEMPLATES/envrc" "$PROJECT_ROOT/.envrc"
deploy_template "$TEMPLATES/gitignore" "$PROJECT_ROOT/.gitignore"

# 2. Deploy settings.local.json (hook paths point to .claude/framework/)
echo ""
echo "[settings]"
deploy_template "$TEMPLATES/settings.local.json" "$PROJECT_ROOT/.claude/settings.local.json"

# 3. Create project-specific directories
echo ""
echo "[project dirs]"
for dir in \
    ".claude/docs" \
    ".claude/skills/${PROJECT_ID}-patterns" \
    ".claude/skills/${PROJECT_ID}-workflows" \
    ".claude/artifacts"
do
    if [[ -d "$PROJECT_ROOT/$dir" ]]; then
        echo "  SKIP $dir/ (already exists)"
    else
        mkdir -p "$PROJECT_ROOT/$dir"
        echo "  CREATE $dir/"
    fi
done

# 4. Deploy project skill templates
echo ""
echo "[project skills]"
deploy_template "$TEMPLATES/project-patterns.SKILL.md.template" \
    "$PROJECT_ROOT/.claude/skills/${PROJECT_ID}-patterns/SKILL.md"
deploy_template "$TEMPLATES/project-workflows.SKILL.md.template" \
    "$PROJECT_ROOT/.claude/skills/${PROJECT_ID}-workflows/SKILL.md"
deploy_template "$TEMPLATES/project-guide.md.template" \
    "$PROJECT_ROOT/.claude/docs/${PROJECT_ID}-guide.md"

echo ""
echo "=== Setup complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .mcp.json — fill in LANGFUSE keys and verify paths"
echo "  2. Edit CLAUDE.md — customize for your project"
echo "  3. Edit .claude/docs/${PROJECT_ID}-guide.md — add domain entities, conventions"
echo "  4. Edit .claude/skills/${PROJECT_ID}-patterns/SKILL.md — add coding patterns"
echo "  5. Run: direnv allow"
echo "  6. Start Claude Code and run: refresh_index && add_memory('Project ${PROJECT_ID}: ...')"
echo ""
echo "To pull framework updates later:"
echo "  git subtree pull --prefix=.claude/framework <path-to-mao-repo> main --squash"
