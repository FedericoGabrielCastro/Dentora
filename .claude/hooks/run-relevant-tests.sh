#!/usr/bin/env bash
# Hook: run-relevant-tests
# Event: PostToolUse (Edit, Write)
# Purpose: Run only the tests relevant to the file Claude just modified.
#          Never runs the full suite. Suggests instead of running for risky cases.
# Exit code is always 0 — findings are informational, never blocking.

set -euo pipefail

PAYLOAD=$(cat)

# ── Extract file path ─────────────────────────────────────────────────────────
FILE_PATH=$(echo "$PAYLOAD" \
  | python3 -c "
import sys, json
print(json.load(sys.stdin).get('tool_input', {}).get('file_path', ''))
" 2>/dev/null || true)

# ── Only process Python files outside migrations ──────────────────────────────
if [[ -z "$FILE_PATH" ]] || [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi
if [[ "$FILE_PATH" == */migrations/* ]]; then
  exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# ── Resolve app and file role via Python ──────────────────────────────────────
python3 - "$FILE_PATH" <<'PYEOF'
import sys
import os
import subprocess
import re
from pathlib import Path

file_path = Path(sys.argv[1])
parts = file_path.parts

# ── Identify app directory ────────────────────────────────────────────────────
# Expected layout: <project_root>/<app>/<file>.py
# or              <project_root>/<app>/<subpackage>/<file>.py
# Find the app by locating the nearest parent that contains apps.py or models.py
app_dir = None
for parent in file_path.parents:
    if (parent / "apps.py").exists() or (parent / "models.py").exists():
        app_dir = parent
        break

if app_dir is None:
    sys.exit(0)

tests_dir = app_dir / "tests"
basename = file_path.name

# ── Map file to test targets ──────────────────────────────────────────────────
# Returns (test_paths, run_automatically, suggestion_only_reason)
def resolve_targets(basename, tests_dir, file_path):
    targets = []
    run_auto = True
    suggestion = None

    if basename == "models.py":
        # Models: suggest migration review + run model tests if they exist
        test_file = tests_dir / "test_models.py"
        if test_file.exists():
            targets.append(str(test_file))
        suggestion = (
            "models.py changed — also check:\n"
            "  • poetry run python manage.py makemigrations --check   (no pending migrations?)\n"
            "  • data-model-reviewer agent if this is a schema change"
        )

    elif basename == "serializers.py":
        test_file = tests_dir / "test_serializers.py"
        if test_file.exists():
            targets.append(str(test_file))

    elif basename in ("views.py", "viewsets.py"):
        # Views: run view tests; also run serializer tests since they are tightly coupled
        for name in ("test_views.py", "test_serializers.py"):
            t = tests_dir / name
            if t.exists():
                targets.append(str(t))

    elif basename == "services.py":
        # Services: run service tests AND view tests (views call services)
        for name in ("test_services.py", "test_views.py"):
            t = tests_dir / name
            if t.exists():
                targets.append(str(t))

    elif basename == "tasks.py":
        test_file = tests_dir / "test_tasks.py"
        if test_file.exists():
            targets.append(str(test_file))
        # Suggest checking that on_commit wiring is correct
        suggestion = (
            "tasks.py changed — reminder:\n"
            "  • tasks must be triggered via transaction.on_commit() in services\n"
            "  • test by calling the task function directly, not via .delay()"
        )

    elif basename == "permissions.py":
        # Permissions affect all views — run view tests
        test_file = tests_dir / "test_views.py"
        if test_file.exists():
            targets.append(str(test_file))
        suggestion = "permissions.py changed — verify that unauthenticated and forbidden cases are tested."

    elif basename.startswith("test_"):
        # The file IS a test file — run it directly
        targets.append(str(file_path))

    return targets, run_auto, suggestion

targets, run_auto, suggestion = resolve_targets(basename, tests_dir, file_path)

if not targets and suggestion is None:
    sys.exit(0)

app_name = app_dir.name
print(f"\n── tests: {app_name}/{basename} ──")

# ── Run relevant tests ────────────────────────────────────────────────────────
if targets:
    target_str = " ".join(targets)
    print(f"   running: pytest {target_str} -x -q\n")

    result = subprocess.run(
        ["poetry", "run", "pytest"] + targets + ["-x", "-q", "--tb=short", "--no-header"],
        capture_output=True,
        text=True,
        timeout=60,
    )

    output = result.stdout + result.stderr
    # Cap output to avoid flooding Claude's context
    lines = output.strip().splitlines()
    if len(lines) > 30:
        lines = lines[:30] + [f"   ... ({len(lines) - 30} more lines)"]
    if lines:
        print("\n".join(f"   {l}" for l in lines))

    if result.returncode == 0:
        print("\n   ✓ tests passed")
    else:
        print("\n   ✗ tests failed — review output above")

# ── Print contextual suggestion if any ───────────────────────────────────────
if suggestion:
    print(f"\n   note: {suggestion}")

print()
PYEOF

exit 0
