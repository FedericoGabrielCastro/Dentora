#!/usr/bin/env bash
# Hook: async-task-warning
# Event: PostToolUse (Edit, Write)
# Purpose: Remind async safety rules when tasks.py or Celery-related files change.
#          Analyzes the diff to surface only the risks present in the actual change.
# Exit code is always 0 — informational only, never blocking.

set -euo pipefail

PAYLOAD=$(cat)

python3 - <<PYEOF
import sys
import json
import re
import os

data = json.loads("""$(echo "$PAYLOAD" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read()))")""")

tool_input = data.get("tool_input", {})
file_path  = tool_input.get("file_path", "")
basename   = os.path.basename(file_path)

# ── Only process async-related files ─────────────────────────────────────────
WATCHED_NAMES = {"tasks.py", "celery.py"}
if not file_path.endswith(".py"):
    sys.exit(0)
if basename not in WATCHED_NAMES:
    # Also catch services.py that trigger tasks (on_commit wiring)
    if basename != "services.py":
        sys.exit(0)

if not os.path.exists(file_path):
    sys.exit(0)

old_string = tool_input.get("old_string", "")
new_string = tool_input.get("new_string", "")
changed    = new_string if new_string else ""

if not changed or changed == old_string:
    sys.exit(0)

# ── Detect patterns in the changed block ─────────────────────────────────────

# New task defined
new_task = bool(re.search(r"@shared_task|@app\.task|@celery\.task", changed))

# bind=True present or absent
has_bind      = "bind=True" in changed
missing_bind  = new_task and not has_bind

# max_retries explicitly set
has_max_retries   = "max_retries=" in changed
missing_max_retries = new_task and not has_max_retries

# Explicit task name
has_name      = re.search(r'name=["\']', changed)
missing_name  = new_task and not has_name

# Idempotency guard
has_idempotency = bool(re.search(
    r"(already_sent|sent_at|reminder_sent|processed|is_done|idempotent"
    r"|\.exists\(\)|if.*is not None|if.*is None)",
    changed
))

# Retry logic
has_retry    = "self.retry(" in changed or "raise self.retry" in changed
has_backoff  = bool(re.search(r"2 \*\* self\.request\.retries|exponential|countdown=", changed))

# Broad exception catch used for retry (risky)
broad_except = bool(re.search(r"except Exception.*self\.retry|except Exception.*retry", changed))

# on_commit wiring
uses_delay         = ".delay(" in changed or ".apply_async(" in changed
inside_atomic      = "atomic" in changed and ".delay(" in changed
uses_on_commit     = "on_commit" in changed
delay_in_atomic    = uses_delay and inside_atomic and not uses_on_commit

# Logging presence
has_logging  = "logger." in changed or "logging." in changed
missing_log  = new_task and not has_logging

# Model instance passed as argument (not serializable)
passes_instance = bool(re.search(
    r"\.delay\(.*=\w+(?<!_id)(?<!pk)(?<!_pk)\b(?![\._])",
    changed
))

# Direct model import in task (not apps.get_model — relevant for data migrations but
# worth flagging in tasks that load models at import time)
direct_model_import = bool(re.search(r"from \w+\.models import", changed))

# ── Build findings ────────────────────────────────────────────────────────────
errors   = []  # likely bugs
warnings = []  # things to verify
reminders = [] # good practice checks

# --- Hard issues ---
if delay_in_atomic:
    errors.append(
        "⛔  .delay() called inside transaction.atomic() — "
        "use transaction.on_commit(lambda: task.delay(...)) instead\n"
        "     Risk: task runs even if the transaction rolls back"
    )

if broad_except:
    errors.append(
        "⛔  bare 'except Exception' used as retry trigger — "
        "this retries on programming errors (TypeError, AttributeError)\n"
        "     Fix: catch only specific transient exceptions"
    )

# --- Warnings ---
if missing_bind:
    warnings.append("bind=True missing on @shared_task — needed for self.retry() and logging retries")

if missing_max_retries:
    warnings.append("max_retries not set — without a limit, a broken integration retries forever")

if missing_name:
    warnings.append("explicit name= not set — task names become import-path dependent and fragile on refactor")

if has_retry and not has_backoff:
    warnings.append(
        "retry without exponential backoff — consider: "
        "countdown=60 * (2 ** self.request.retries)"
    )

# --- Reminders ---
if new_task and not has_idempotency:
    reminders.append("idempotency: add a guard (sent flag, state check) — tasks can run more than once")

if missing_log:
    reminders.append("logging: add logger.info() at start and success, logger.warning() on retry")

if passes_instance:
    reminders.append(
        "task argument may be a model instance — pass pk (int) instead; "
        "instances are not serializable and go stale in the queue"
    )

# For services.py: check on_commit presence when .delay() is used
if basename == "services.py" and uses_delay and not uses_on_commit:
    warnings.append(
        "services.py: .delay() found without on_commit — "
        "wrap with transaction.on_commit(lambda: task.delay(...)) "
        "to avoid enqueueing on rollback"
    )

# ── Output ────────────────────────────────────────────────────────────────────
if not (errors or warnings or reminders):
    if new_task:
        # New task with no issues — minimal confirmation
        print(f"\n── async: {file_path.replace(os.getcwd() + '/', '')} ──")
        print("   new task defined — no obvious issues detected")
        print("   verify: idempotency guard, max_retries, on_commit wiring in the calling service\n")
    sys.exit(0)

rel_path = file_path.replace(os.getcwd() + "/", "")
print(f"\n── async: {rel_path} ──")

if errors:
    for e in errors:
        print(f"   {e}")
    print()

if warnings:
    print("   warnings:")
    for w in warnings:
        print(f"   • {w}")
    print()

if reminders:
    print("   reminders:")
    for r in reminders:
        print(f"   □ {r}")
    print()

PYEOF

exit 0
