#!/usr/bin/env python3
"""PreToolUse hook: Phase 4 — Model selection enforcement.

Enforces cheapest-capable-first model selection for Agent calls.
Blocks opus/sonnet when the task doesn't warrant it.

Model hierarchy (CLAUDE.md):
  1. Gemini Flash Lite — indexing, classification
  2. Gemini Flash — reviews, analysis, bulk reads
  3. Gemini Pro — complex reasoning, architecture
  4. Haiku — quick fixes, boilerplate, simple edits
  5. Sonnet — multi-file implementation, tests, refactoring
  6. Opus — final decisions, ambiguous debugging, architecture sign-off
"""

import json
import sys

# Keywords that justify expensive models (case-insensitive matching)
_OPUS_KEYWORDS = {
    "debug", "ambiguous", "architecture", "sign-off", "final decision",
    "complex analysis", "design review", "root cause", "investigate",
    "diagnose", "critical", "production issue",
}

_SONNET_KEYWORDS = {
    "implement", "refactor", "test", "multi-file", "migration",
    "rewrite", "convert", "build", "create feature", "add feature",
    "fix bug", "write tests", "integration",
}

# Subagent types that should never use opus
_CHEAP_SUBAGENTS = {"Explore", "Plan", "claude-code-guide", "statusline-setup"}


def _text_contains_any(text: str, keywords: set[str]) -> bool:
    """Check if text contains any keyword (case-insensitive)."""
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def main():
    try:
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})

    if tool_name != "Agent":
        sys.exit(0)

    model = tool_input.get("model", "")
    if not model:
        sys.exit(0)

    model_lower = model.lower()
    subagent_type = tool_input.get("subagent_type", "")
    description = tool_input.get("description", "")
    prompt = tool_input.get("prompt", "")
    combined_text = f"{description} {prompt}"

    # Rule 1: Explore/Plan agents should never use opus or sonnet
    if subagent_type in _CHEAP_SUBAGENTS:
        if "opus" in model_lower:
            _deny(
                f"subagent_type='{subagent_type}' doesn't need opus. "
                "Remove the model param to use the default, or use model='haiku'."
            )
        if "sonnet" in model_lower:
            _deny(
                f"subagent_type='{subagent_type}' doesn't need sonnet. "
                "Remove the model param to use the default, or use model='haiku'."
            )

    # Rule 2: Opus requires justifying keywords
    if "opus" in model_lower:
        if not _text_contains_any(combined_text, _OPUS_KEYWORDS):
            _deny(
                "model='opus' is reserved for: ambiguous debugging, architecture sign-off, "
                "final decisions, complex root cause analysis.\n"
                f"Task: \"{description}\"\n"
                "Try: model='sonnet' for implementation, or delegate to Gemini."
            )

    # Rule 3: Sonnet should have implementation-like keywords
    if "sonnet" in model_lower:
        if len(combined_text) < 50 and not _text_contains_any(combined_text, _SONNET_KEYWORDS):
            _deny(
                "model='sonnet' is for: multi-file implementation, tests, refactoring.\n"
                f"Task looks simple: \"{description}\"\n"
                "Try: model='haiku' for simple tasks, or delegate to Gemini."
            )

    # All checks passed
    sys.exit(0)


def _deny(reason: str):
    """Print deny decision and exit."""
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(result))
    sys.exit(0)


if __name__ == "__main__":
    main()
