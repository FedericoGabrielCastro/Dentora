#!/usr/bin/env bash
# Hook: migration-review-warning
# Event: PostToolUse (Edit, Write)
# Purpose: Detect when a Django migration is created or modified and surface
#          a targeted review checklist based on the operations actually present.
# Exit code is always 0 — warning only, never blocking.

set -euo pipefail

PAYLOAD=$(cat)

# ── Extract tool name and file path ──────────────────────────────────────────
TOOL_NAME=$(echo "$PAYLOAD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_name',''))" 2>/dev/null || true)

FILE_PATH=$(echo "$PAYLOAD" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null || true)

# ── Only process Django migration files ──────────────────────────────────────
if [[ -z "$FILE_PATH" ]] || [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi
if [[ "$FILE_PATH" != */migrations/* ]]; then
  exit 0
fi
# Skip __init__.py inside migrations/
if [[ "$(basename "$FILE_PATH")" == "__init__.py" ]]; then
  exit 0
fi
if [[ ! -f "$FILE_PATH" ]]; then
  exit 0
fi

# ── Detect whether this is a new file or an edit to an existing migration ─────
# Editing an existing migration is almost always wrong.
IS_EDIT=false
if [[ "$TOOL_NAME" == "Edit" ]]; then
  IS_EDIT=true
fi

# ── Parse migration content for risky operations ─────────────────────────────
python3 - "$FILE_PATH" "$IS_EDIT" <<'PYEOF'
import sys
import re

migration_file = sys.argv[1]
is_edit = sys.argv[2] == "true"

with open(migration_file) as f:
    content = f.read()

migration_name = migration_file.split("/")[-1].replace(".py", "")

# Detect operations present in this migration
ops = {
    "AddField":        bool(re.search(r"migrations\.AddField", content)),
    "RemoveField":     bool(re.search(r"migrations\.RemoveField", content)),
    "DeleteModel":     bool(re.search(r"migrations\.DeleteModel", content)),
    "RenameField":     bool(re.search(r"migrations\.RenameField", content)),
    "RenameModel":     bool(re.search(r"migrations\.RenameModel", content)),
    "AlterField":      bool(re.search(r"migrations\.AlterField", content)),
    "AddIndex":        bool(re.search(r"migrations\.AddIndex", content)),
    "AddConstraint":   bool(re.search(r"migrations\.AddConstraint", content)),
    "RunPython":       bool(re.search(r"migrations\.RunPython", content)),
    "RunSQL":          bool(re.search(r"migrations\.RunSQL", content)),
    "CreateModel":     bool(re.search(r"migrations\.CreateModel", content)),
}

any_risky = any([
    ops["RemoveField"], ops["DeleteModel"], ops["RenameField"],
    ops["RenameModel"], ops["AlterField"], ops["RunPython"],
    ops["RunSQL"], ops["AddConstraint"],
])

# ── Header ────────────────────────────────────────────────────────────────────
if is_edit:
    print(f"\n⛔  EDITED existing migration: {migration_name}")
    print("   Editing an existing migration rewrites history.")
    print("   If this migration has already been applied anywhere, create a new one instead.\n")
else:
    print(f"\n⚠  New migration: {migration_name}")

# ── Operation summary ─────────────────────────────────────────────────────────
active_ops = [op for op, present in ops.items() if present]
if active_ops:
    print(f"   Operations detected: {', '.join(active_ops)}\n")

# ── Targeted checklist based on operations found ──────────────────────────────
checks = []

if ops["AddField"]:
    # Check for null=False with no default — the most common migration bug
    has_null_false_no_default = bool(
        re.search(r"field=.*?\(", content) and
        "null=True" not in content and
        "default=" not in content and
        "AddField" in content
    )
    checks.append("AddField: does this column have a safe default for existing rows?")
    checks.append("AddField: is null=False on a table that already has data? (needs default or two-step migration)")

if ops["RemoveField"]:
    checks.append("RemoveField: is this field still referenced in any view, serializer, service, or task?")
    checks.append("RemoveField: irreversible — data will be dropped. Is a backup or data migration needed?")

if ops["DeleteModel"]:
    checks.append("DeleteModel: ALL rows will be deleted. Is this table empty in production?")
    checks.append("DeleteModel: are there FK references to this model from other tables?")

if ops["RenameField"] or ops["RenameModel"]:
    checks.append("Rename: application code must be updated atomically with this migration.")
    checks.append("Rename: in a rolling deploy, the old name must remain valid until all instances restart.")
    checks.append("Rename: check for raw SQL, management commands, or Celery tasks that reference the old name.")

if ops["AlterField"]:
    checks.append("AlterField: type changes may require a full table rewrite on PostgreSQL.")
    checks.append("AlterField: adding unique=True acquires a lock while building the unique index.")
    checks.append("AlterField: verify existing data satisfies the new constraint before applying.")

if ops["AddIndex"]:
    checks.append("AddIndex: Django does not use CONCURRENTLY by default.")
    checks.append("AddIndex: on a large table (Appointment, Patient), consider running CREATE INDEX CONCURRENTLY manually.")

if ops["AddConstraint"]:
    checks.append("AddConstraint: validates ALL existing rows at apply time.")
    checks.append("AddConstraint: if any row violates the constraint, the migration fails mid-run.")

if ops["RunPython"]:
    has_reverse = "reverse_code=" in content
    uses_apps_get_model = "apps.get_model" in content
    has_direct_import = bool(re.search(r"^from \w+\.models import", content, re.MULTILINE))

    if not uses_apps_get_model or has_direct_import:
        checks.append("RunPython ⚠: use apps.get_model() — direct model imports break on future schema changes.")
    else:
        checks.append("RunPython: confirmed apps.get_model() usage ✓")

    if not has_reverse:
        checks.append("RunPython: no reverse_code found — is this migration reversible? Add noop with a comment if not.")
    checks.append("RunPython: is this idempotent? Safe to run twice?")
    checks.append("RunPython: does it load all rows into memory? Use iterator() or batch for large tables.")

if ops["RunSQL"]:
    checks.append("RunSQL: include reverse SQL or document why rollback is not possible.")
    checks.append("RunSQL: verify idempotency — what happens if this runs twice?")

# ── Rollback ──────────────────────────────────────────────────────────────────
irreversible_ops = [op for op in ["RemoveField", "DeleteModel", "RunSQL"] if ops[op]]
if irreversible_ops:
    checks.append(f"Rollback: {', '.join(irreversible_ops)} — migration may be irreversible. Document it with a comment.")

# ── Print checklist ───────────────────────────────────────────────────────────
if checks:
    print("   Review before applying:\n")
    for check in checks:
        print(f"   • {check}")

# ── Low-risk fast path ────────────────────────────────────────────────────────
if not any_risky and not is_edit:
    if ops["CreateModel"]:
        print("   CreateModel only — low risk. Verify __str__, Meta.ordering, and admin registration.")
    else:
        print("   No high-risk operations detected.")

print()
PYEOF

exit 0
