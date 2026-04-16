#!/usr/bin/env bash
# Hook: swagger-drift-warning
# Event: PostToolUse (Edit, Write)
# Purpose: Remind to update Swagger documentation when DRF endpoint files change.
#          Analyzes what changed to show only relevant reminders.
# Exit code is always 0 — informational only, never blocking.

set -euo pipefail

PAYLOAD=$(cat)

python3 - <<PYEOF
import sys
import json
import re

data = json.loads("""$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")""")

tool_input = data.get("tool_input", {})
file_path   = tool_input.get("file_path", "")

# ── Only process relevant DRF files ──────────────────────────────────────────
WATCHED_NAMES = {"views.py", "viewsets.py", "serializers.py", "urls.py", "routers.py"}
import os
basename = os.path.basename(file_path)

if not file_path.endswith(".py"):
    sys.exit(0)
if basename not in WATCHED_NAMES:
    sys.exit(0)
if not os.path.exists(file_path):
    sys.exit(0)

# ── Read current file content ─────────────────────────────────────────────────
with open(file_path) as f:
    current_content = f.read()

# ── Read the diff (only available on Edit tool) ───────────────────────────────
old_string = tool_input.get("old_string", "")
new_string = tool_input.get("new_string", "")
is_new_file = (old_string == "")  # Write tool or first content

# ── Detect what changed ───────────────────────────────────────────────────────
changed_content = new_string if new_string else current_content

# New HTTP methods added
http_methods = ["def get", "def post", "def put", "def patch", "def delete"]
new_methods = [m for m in http_methods if m in changed_content and m not in old_string]

# New serializer fields added
new_fields = bool(re.search(r"^\s+\w+ = serializers\.\w+Field", changed_content, re.MULTILINE)
                  and changed_content != old_string)

# New URL patterns added
new_urls = bool(re.search(r"path\(|re_path\(|router\.(register|include)", changed_content)
               and changed_content != old_string)

# extend_schema presence
has_extend_schema = "@extend_schema" in current_content
schema_added      = "@extend_schema" in new_string
schema_removed    = "@extend_schema" in old_string and "@extend_schema" not in new_string

# Status codes or response changes
status_changed = bool(re.search(r"status\.HTTP_\d+", changed_content)
                      and changed_content != old_string)

# ── Build targeted message ────────────────────────────────────────────────────
reminders = []

if basename in ("views.py", "viewsets.py"):
    if new_methods:
        methods_str = ", ".join(m.replace("def ", "") + "()" for m in new_methods)
        reminders.append(f"new method(s) detected: {methods_str}")
        reminders.append("→ add @extend_schema with summary, request, responses and tags")

    if schema_removed:
        reminders.append("@extend_schema was removed — Swagger will lose this endpoint's documentation")

    if not has_extend_schema and not is_new_file:
        reminders.append("@extend_schema not found in this view — endpoint is undocumented in Swagger")

    if status_changed:
        reminders.append("status code changed — update responses={} in @extend_schema")

elif basename == "serializers.py":
    if new_fields:
        reminders.append("serializer fields changed — Swagger schema may be out of date")
        reminders.append("→ check: are new fields reflected in @extend_schema request/responses?")
        reminders.append("→ check: are examples in OpenApiExample still accurate?")

elif basename in ("urls.py", "routers.py"):
    if new_urls:
        reminders.append("URL patterns changed — check Swagger tags and endpoint grouping")
        reminders.append("→ new paths may need @extend_schema(tags=[...]) on the registered view")

# ── Generic reminder if no specific issues detected but file changed ──────────
if not reminders and changed_content != old_string:
    reminders = ["file changed — verify Swagger documentation is still accurate"]

if not reminders:
    sys.exit(0)

# ── Print message ─────────────────────────────────────────────────────────────
app_part = file_path.replace(os.getcwd() + "/", "")
print(f"\n── swagger: {app_part} ──")
for r in reminders:
    print(f"   • {r}")

print()
print("   Swagger checklist:")
print("   □ request body matches current serializer")
print("   □ response body matches current output serializer")
print("   □ status codes are correct (201 create / 204 no body / 409 conflict)")
print("   □ error responses documented (400, 401, 404 where relevant)")
print("   □ OpenApiExample payloads still match field names")
print("   □ @extend_schema(exclude=True) on any internal endpoints")
print()
PYEOF

exit 0
