#!/usr/bin/env bash
# Hook: python-quality-check
# Event: PostToolUse (Edit, Write)
# Purpose: Run black, flake8, and selective mypy on every Python file Claude touches.
# Exit code is always 0 — findings are informational, not blocking.

set -euo pipefail

# ── Read the tool payload from stdin ─────────────────────────────────────────
PAYLOAD=$(cat)

FILE_PATH=$(echo "$PAYLOAD" \
  | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('tool_input', {}).get('file_path', ''))
" 2>/dev/null || true)

# ── Only process Python files ─────────────────────────────────────────────────
if [[ -z "$FILE_PATH" ]] || [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

# ── Skip files that don't exist (deleted) ────────────────────────────────────
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# ── Skip migrations — reviewed separately by data-model-reviewer ─────────────
if [[ "$FILE_PATH" == */migrations/* ]]; then
  exit 0
fi

# ── Determine file role for selective mypy ────────────────────────────────────
# Run mypy only on production code where types matter most.
# Skip tests and conftest — slower, lower value.
RUN_MYPY=false
BASENAME=$(basename "$FILE_PATH")
case "$BASENAME" in
  models.py|serializers.py|views.py|viewsets.py|services.py|tasks.py|permissions.py)
    RUN_MYPY=true
    ;;
esac

# ── Collect results ───────────────────────────────────────────────────────────
ISSUES=""

# black --check (fast, ~100ms)
BLACK_OUT=$(poetry run black --check --quiet "$FILE_PATH" 2>&1 || true)
if [[ -n "$BLACK_OUT" ]]; then
  ISSUES+="[black] $FILE_PATH needs formatting — run: poetry run black $FILE_PATH\n"
fi

# flake8 (fast, ~200ms)
FLAKE8_OUT=$(poetry run flake8 "$FILE_PATH" 2>/dev/null || true)
if [[ -n "$FLAKE8_OUT" ]]; then
  ISSUES+="[flake8]\n$FLAKE8_OUT\n"
fi

# mypy — only on key production files, capped at 5 errors to avoid noise
if [[ "$RUN_MYPY" == true ]]; then
  MYPY_OUT=$(poetry run mypy "$FILE_PATH" \
    --ignore-missing-imports \
    --no-error-summary \
    --no-pretty \
    2>/dev/null \
    | grep " error:" \
    | head -5 \
    || true)
  if [[ -n "$MYPY_OUT" ]]; then
    ISSUES+="[mypy]\n$MYPY_OUT\n"
  fi
fi

# ── Report ────────────────────────────────────────────────────────────────────
if [[ -n "$ISSUES" ]]; then
  echo "── quality check: $FILE_PATH ──"
  printf "%b" "$ISSUES"
fi

# Always exit 0 — informational only, never block Claude's workflow
exit 0
