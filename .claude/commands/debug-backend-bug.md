# debug-backend-bug

Investigate a bug in Dentora systematically. No impulsive changes — find the root cause first, then propose the minimal fix.

**Usage:** `/debug-backend-bug <description of the problem>`

**Examples:**
- `/debug-backend-bug appointments are being created with status "cancelled" instead of "scheduled"`
- `/debug-backend-bug GET /api/appointments/ returns 500 when dentist_id is not provided`
- `/debug-backend-bug send_appointment_reminder task is running but patients are not receiving emails`
- `/debug-backend-bug booking an appointment does not check for dentist availability`
- `/debug-backend-bug cancellation endpoint returns 200 but the appointment status is not updated in the DB`

---

## What this skill does

You are investigating a bug in the Dentora backend.
Do not make any changes until you have identified the root cause with confidence.
Read before you write. Hypothesize before you fix.

The argument is: $ARGUMENTS

---

## Step 1 — Understand and restate the problem

Before looking at any code, answer these three questions in writing:

1. **What is the observed behavior?** (what actually happens)
2. **What is the expected behavior?** (what should happen)
3. **Where in the system does the gap likely live?** (HTTP layer, service, task, DB, external service)

If the description is ambiguous, state your assumption explicitly and continue.

---

## Step 2 — Locate the entry point

Trace the request or event through the system from the outside in:

**For an HTTP bug:**
1. Find the URL in `urls.py` → identify the view.
2. Read the view: what serializer does it use? What service does it call?
3. Follow the service: what does it read from the DB? What does it write?

**For a Celery task bug:**
1. Find the task in `tasks.py`.
2. What triggers it? (signal, `on_commit`, Beat schedule)
3. What service does it delegate to?
4. What external I/O does it perform?

**For a model/data bug:**
1. Which model is involved?
2. What writes to this field? (`save()`, `update()`, `bulk_create()`, a migration default)
3. Is there a signal or `save()` override that could interfere?

Read every file in the chain before forming a hypothesis. Do not stop at the view.

---

## Step 3 — Form hypotheses

List 2–4 specific, falsifiable hypotheses. Order them from most to least likely based on the entry point trace.

Format:
```
H1 (most likely): The service is calling .update() directly, bypassing the status validation in save().
H2: The serializer is not validating the status field and accepting "cancelled" as input.
H3: A signal on Appointment.post_save is overwriting the status after creation.
H4: There is a migration default that sets status to "cancelled" on new rows.
```

Do not investigate all hypotheses at once. Start with H1.

---

## Step 4 — Investigate

For each hypothesis, identify the specific lines that would confirm or deny it.

**What to look for:**

| Symptom | Where to look |
|---------|--------------|
| Wrong value written to DB | `services.py` write path, `serializer.create()`/`update()`, model `save()` override, signals |
| Value correct in DB but wrong in response | `OutputSerializer`, view `Response()` construction |
| Exception swallowed silently | `except Exception: pass`, bare `except:`, Celery `on_failure` handler |
| Task runs but has no effect | Idempotency guard triggering incorrectly, wrong `appointment_id` being passed |
| Intermittent failure | Race condition, missing `select_for_update()`, transaction isolation issue |
| Works in tests, fails in production | Hardcoded test data hiding a real edge case, env-specific config, missing `on_commit` in tests |

**Log inspection:**
- Check Django logs for unhandled exceptions or unexpected query patterns.
- Check Celery worker logs for task failures, retries, or silent errors.
- If using Sentry or similar, look for the traceback — do not guess what the stack trace says.

**DB inspection (read-only):**
```python
# Run in Django shell to inspect actual data
poetry run python manage.py shell

from appointments.models import Appointment
Appointment.objects.filter(...).values("id", "status", "created_at", "updated_at")
```

---

## Step 5 — Identify the root cause

State the root cause in one sentence before proposing any fix:

```
Root cause: cancel_appointment() calls Appointment.objects.filter(pk=id).update(status=...) 
which bypasses the post_save signal that enqueues the notification task, so the task 
is never enqueued on cancellation.
```

If you cannot state the root cause in one sentence, you have not found it yet. Keep reading.

**Distinguish root cause from symptom:**

| Symptom | Possible root cause |
|---------|-------------------|
| Email not sent | Task not enqueued / task enqueued but silently failed / wrong recipient |
| Wrong status in DB | Direct `.update()` bypassing validation / serializer accepting invalid input / signal overwriting |
| 500 error | Unhandled exception / missing `.get()` error handling / serializer not called with `raise_exception=True` |
| Test passes, prod fails | `on_commit` not firing in tests / missing env var / different DB state |

---

## Step 6 — Propose the fix

Once the root cause is clear, propose the minimal change that resolves it.

**Rules for the fix:**
- Change only what is necessary to fix this specific bug.
- Do not refactor surrounding code as part of the fix.
- Do not add features or handle unrelated edge cases.
- If the fix requires touching more than two files, question whether you have found the real root cause.

**Format:**

```
## Proposed fix

File: appointments/services.py, line 47

Problem: .update() bypasses post_save signal.

Change:
  Before: Appointment.objects.filter(pk=appointment_id).update(status=Appointment.Status.CANCELLED)
  After:  appointment = Appointment.objects.get(pk=appointment_id)
          appointment.status = Appointment.Status.CANCELLED
          appointment.save()

Why this fixes it: .save() triggers post_save, which enqueues the notification task via on_commit.

Side effects to verify: any other code path that calls .update() on Appointment.status 
has the same problem — list them if found.
```

---

## Step 7 — Prevent regression

After the fix, add or adjust a test that would have caught this bug.

**For a service bug:** add a test in `tests/test_services.py` that verifies the side effect:
```python
def test_cancel_appointment_enqueues_notification(self, appointment, mocker):
    mock_task = mocker.patch("appointments.services.send_cancellation_notice.delay")
    cancel_appointment(appointment_id=appointment.pk, reason="patient request")
    mock_task.assert_called_once_with(appointment.pk)
```

**For a view bug:** add a test in `tests/test_views.py` that hits the endpoint and asserts the full response:
```python
def test_cancel_returns_correct_status_in_response(self, auth_client, appointment):
    response = auth_client.post(f"/api/appointments/{appointment.pk}/cancel/")
    assert response.status_code == 200
    assert response.data["status"] == "cancelled"
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CANCELLED
```

**For a task bug:** add a test that verifies the task has the expected effect on DB state:
```python
def test_reminder_task_marks_sent_at(self, appointment, mocker):
    mocker.patch("notifications.tasks.send_reminder_email")
    send_appointment_reminder(appointment_id=appointment.pk)
    appointment.refresh_from_db()
    assert appointment.reminder_sent_at is not None
```

State which existing test should have caught this and why it did not.

---

## Step 8 — Final report

Produce a concise summary before finishing:

```
## Bug report: [one-line description]

**Root cause:** [one sentence]

**Fix:** [file, line, what changed]

**Why it was missed:** [gap in test coverage, wrong assumption, missing guard]

**Regression test added:** [yes / no — if no, explain why it's not feasible]

**Other code paths with the same issue:** [list or "none found"]
```

---

## Checklist

- [ ] Problem restated in observed vs. expected terms
- [ ] Entry point traced through all layers before hypothesizing
- [ ] Hypotheses listed and ranked before investigating
- [ ] Root cause stated in one sentence
- [ ] Fix changes only what is necessary — no unrelated cleanup
- [ ] Fix touches two files or fewer (if more, root cause is re-examined)
- [ ] At least one regression test added
- [ ] Other code paths with the same pattern are listed
- [ ] Final report written

---

## What not to do

- Do not add logging and call it a fix — logging is for investigation, not resolution
- Do not wrap the bug in a try/except to suppress the symptom
- Do not fix a symptom and declare the bug closed without finding the root cause
- Do not refactor surrounding code while fixing — that is a separate PR
- Do not mark a bug as fixed without a test that would have caught it
