# create-celery-task

Implement an async Celery task for Dentora with clear inputs, idempotency, retries, logging, and tests.

**Usage:** `/create-celery-task <app>/<task-name> [brief description]`

**Examples:**
- `/create-celery-task notifications/send-appointment-reminder send email+SMS reminder 24h before a scheduled appointment`
- `/create-celery-task appointments/expire-unconfirmed-slots mark as expired all unconfirmed appointments past their confirmation deadline`
- `/create-celery-task notifications/send-cancellation-notice notify patient and dentist when an appointment is cancelled`
- `/create-celery-task appointments/sync-availability-from-external sync dentist availability from an external calendar API`
- `/create-celery-task patients/send-treatment-summary email a post-appointment treatment summary to the patient`

---

## What this skill does

You are implementing a Celery task for Dentora.
Before writing anything, read `tasks.py` in the target app (if it exists) and `celery.py` at the project root.
Do not create a new app — if the app does not exist, stop and say so.

The argument is: $ARGUMENTS

---

## Step 1 — Should this actually be async?

Before writing a single line, answer these questions:

| Question | If yes → |
|----------|----------|
| Does this involve I/O that could block the request? (email, SMS, external API) | Async task |
| Does this need to run on a schedule, not triggered by a user action? | Celery beat task |
| Does this touch many DB rows and could slow down a response? | Async task |
| Does this need to retry on transient failure? | Async task |
| Is this a simple DB write that takes < 50ms and never fails transiently? | Keep it synchronous |
| Is this called from a serializer or view just to avoid thinking? | Keep it synchronous |

State your decision and the reason before implementing.

**Dentora task categories:**

| Category | When to use async | Example |
|----------|------------------|---------|
| Notifications | Always — email/SMS involves external I/O | `send_appointment_reminder` |
| Scheduled cleanup | Always — runs on a timer, not a request | `expire_unconfirmed_slots` |
| External sync | Always — third-party API, latency unpredictable | `sync_dentist_availability` |
| Report generation | If > a few seconds | `generate_monthly_report` |
| Simple status update | Probably not — just write to DB | `mark_appointment_completed` |

---

## Step 2 — Task signature and placement

**File:** `<app>/tasks.py`

**Rules:**
- Always use `bind=True` so the task instance is available as `self` for retries and logging.
- Accept primitive types as arguments (`int`, `str`, `uuid`), never model instances — instances are not serializable and go stale in the queue.
- Name tasks explicitly with `name=` to avoid import-path coupling.
- One task per function. Do not write tasks that do two unrelated things.

```python
import logging
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="notifications.send_appointment_reminder",
    max_retries=3,
    default_retry_delay=60,  # seconds
)
def send_appointment_reminder(self, appointment_id: int) -> None:
    ...
```

---

## Step 3 — Idempotency

Every task must be safe to run more than once with the same arguments. Celery can deliver a message more than once (at-least-once delivery).

**Patterns by task type:**

**Notification tasks** — guard with a sent flag on the model:
```python
if appointment.reminder_sent_at is not None:
    logger.info("Reminder already sent for appointment %s, skipping.", appointment_id)
    return
```

**Cleanup tasks** — use `filter()` with state, not a fixed list:
```python
# Good — idempotent: only acts on rows that still qualify
Appointment.objects.filter(
    status=Appointment.Status.SCHEDULED,
    scheduled_at__lt=cutoff,
).update(status=Appointment.Status.EXPIRED)

# Bad — not idempotent: re-processes the same rows if task runs twice
for appt in appointments_to_expire:
    appt.status = "expired"
    appt.save()
```

**External sync tasks** — use upsert (`update_or_create`) instead of delete + recreate:
```python
AvailabilitySlot.objects.update_or_create(
    external_id=slot_data["id"],
    defaults={...},
)
```

---

## Step 4 — Full task implementation

```python
@shared_task(
    bind=True,
    name="notifications.send_appointment_reminder",
    max_retries=3,
    default_retry_delay=60,
)
def send_appointment_reminder(self, appointment_id: int) -> None:
    """Send a 24h reminder to the patient and dentist for a scheduled appointment."""
    logger.info("Starting reminder task for appointment_id=%s", appointment_id)

    # 1. Load the record — handle not found gracefully
    try:
        appointment = Appointment.objects.select_related("patient", "dentist").get(
            pk=appointment_id
        )
    except Appointment.DoesNotExist:
        logger.warning(
            "Appointment %s not found, skipping reminder.", appointment_id
        )
        return  # do not retry — the record is gone

    # 2. Guard: idempotency check
    if appointment.reminder_sent_at is not None:
        logger.info("Reminder already sent for appointment %s.", appointment_id)
        return

    # 3. Guard: skip if appointment is no longer in a state that needs a reminder
    if appointment.status not in (
        Appointment.Status.SCHEDULED,
        Appointment.Status.CONFIRMED,
    ):
        logger.info(
            "Appointment %s has status %s, skipping reminder.",
            appointment_id,
            appointment.status,
        )
        return

    # 4. Delegate to service — no logic in the task body
    try:
        send_appointment_reminder_notification(appointment)
    except TransientNotificationError as exc:
        # Transient failure — retry with exponential backoff
        logger.warning(
            "Transient error sending reminder for appointment %s: %s. Retrying.",
            appointment_id,
            exc,
        )
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    except PermanentNotificationError as exc:
        # Permanent failure — log and do not retry
        logger.error(
            "Permanent error sending reminder for appointment %s: %s. Not retrying.",
            appointment_id,
            exc,
        )
        return

    # 5. Mark as sent inside a transaction
    Appointment.objects.filter(pk=appointment_id).update(
        reminder_sent_at=timezone.now()
    )

    logger.info("Reminder sent successfully for appointment_id=%s", appointment_id)
```

---

## Step 5 — Scheduled tasks (Celery Beat)

For tasks that run on a timer rather than being triggered by an event, register them in `settings.py`:

```python
# settings.py
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "send-appointment-reminders": {
        "task": "notifications.send_appointment_reminder_batch",
        "schedule": crontab(hour=8, minute=0),  # every day at 08:00
    },
    "expire-unconfirmed-slots": {
        "task": "appointments.expire_unconfirmed_slots",
        "schedule": crontab(minute="*/15"),  # every 15 minutes
    },
}
```

For batch scheduled tasks, implement a **coordinator + per-item pattern**:

```python
@shared_task(name="notifications.send_appointment_reminder_batch")
def send_appointment_reminder_batch() -> None:
    """Enqueue individual reminder tasks for appointments in the next 24h."""
    cutoff = timezone.now() + timedelta(hours=24)
    appointment_ids = Appointment.objects.filter(
        status=Appointment.Status.CONFIRMED,
        scheduled_at__lte=cutoff,
        reminder_sent_at__isnull=True,
    ).values_list("pk", flat=True)

    for appointment_id in appointment_ids:
        send_appointment_reminder.delay(appointment_id)

    logger.info("Enqueued %d appointment reminders.", len(appointment_ids))
```

The coordinator only queries and enqueues. The per-item task handles the actual work and retries.

---

## Step 6 — Triggering from services

Tasks must be triggered from the service layer, not from views or serializers. Use `transaction.on_commit` to ensure the task is only enqueued after the transaction commits successfully.

```python
# appointments/services.py

from django.db import transaction

def cancel_appointment(appointment_id: int, reason: str) -> Appointment:
    with transaction.atomic():
        appointment = Appointment.objects.select_for_update().get(pk=appointment_id)
        # ... business logic ...
        appointment.save()

        # Enqueue AFTER the transaction commits — never inside atomic()
        transaction.on_commit(
            lambda: send_cancellation_notice.delay(appointment_id)
        )

    return appointment
```

Never call `.delay()` directly inside `transaction.atomic()` — if the transaction rolls back, the task will have already been enqueued with data that no longer exists.

---

## Step 7 — Tests

Create or update `tests/test_tasks.py` in the target app.

**Rules:**
- Call task functions directly — do not use `.delay()` or `.apply_async()` in tests.
- Test task logic, not Celery internals.
- Use `pytest-mock` (`mocker`) to patch external I/O (email, SMS, HTTP calls).
- For retry tests, use `task.apply()` and assert on `Retry` being raised.

```python
import pytest
from celery.exceptions import Retry


@pytest.mark.django_db
class TestSendAppointmentReminder:

    def test_sends_reminder_for_confirmed_appointment(self, mocker):
        appointment = AppointmentFactory(confirmed=True, reminder_sent_at=None)
        mock_notify = mocker.patch("notifications.tasks.send_appointment_reminder_notification")

        send_appointment_reminder(appointment_id=appointment.pk)

        mock_notify.assert_called_once_with(appointment)
        appointment.refresh_from_db()
        assert appointment.reminder_sent_at is not None

    def test_skips_if_reminder_already_sent(self, mocker):
        appointment = AppointmentFactory(confirmed=True, reminder_sent_at=timezone.now())
        mock_notify = mocker.patch("notifications.tasks.send_appointment_reminder_notification")

        send_appointment_reminder(appointment_id=appointment.pk)

        mock_notify.assert_not_called()

    def test_skips_cancelled_appointment(self, mocker):
        appointment = AppointmentFactory(cancelled=True, reminder_sent_at=None)
        mock_notify = mocker.patch("notifications.tasks.send_appointment_reminder_notification")

        send_appointment_reminder(appointment_id=appointment.pk)

        mock_notify.assert_not_called()

    def test_skips_gracefully_if_appointment_not_found(self, mocker):
        mock_notify = mocker.patch("notifications.tasks.send_appointment_reminder_notification")
        # Should not raise, should not retry
        send_appointment_reminder(appointment_id=99999)
        mock_notify.assert_not_called()

    def test_retries_on_transient_error(self, mocker):
        appointment = AppointmentFactory(confirmed=True, reminder_sent_at=None)
        mocker.patch(
            "notifications.tasks.send_appointment_reminder_notification",
            side_effect=TransientNotificationError("SMTP timeout"),
        )
        with pytest.raises(Retry):
            send_appointment_reminder.apply(args=[appointment.pk])
```

---

## Validation checklist

Before marking the task as done:

- [ ] Justified whether async is actually necessary
- [ ] Task accepts primitive arguments only (no model instances)
- [ ] `bind=True` and explicit `name=` on `@shared_task`
- [ ] Idempotency guard implemented (sent flag, state check, or upsert)
- [ ] `DoesNotExist` is caught and does not trigger a retry
- [ ] Transient vs permanent errors are distinguished in exception handling
- [ ] Retries use exponential backoff (`countdown=60 * (2 ** self.request.retries)`)
- [ ] No business logic in the task body — delegates to a service
- [ ] Triggered from the service layer with `transaction.on_commit()`
- [ ] For scheduled tasks: coordinator + per-item pattern, registered in `CELERY_BEAT_SCHEDULE`
- [ ] Logging at info level on start and success, warning on transient error, error on permanent failure
- [ ] Tests call the function directly — no `.delay()` in tests
- [ ] Tests cover: happy path, already-processed guard, wrong-state guard, not found, retry on transient error

---

## Anti-patterns to avoid

| Anti-pattern | Problem | Fix |
|---|---|---|
| Accepting a model instance as argument | Not serializable; stale data in queue | Accept `pk` (int) and load inside the task |
| Business logic inside the task body | Hard to test, mixes concerns | Delegate to a service function |
| `.delay()` inside `transaction.atomic()` | Task enqueued even if transaction rolls back | Use `transaction.on_commit(lambda: task.delay(...))` |
| No idempotency guard | Re-running sends duplicate emails, creates duplicate records | Add a sent flag or state check at the top |
| Catching bare `Exception` on retry | Retries on programming errors (TypeError, AttributeError) | Catch specific transient exceptions only |
| Triggering tasks from a view | Bypasses service layer; view becomes coordinator | Always trigger from `services.py` |
| One giant batch task that does everything | Can't retry individual failures | Coordinator enqueues per-item tasks |
| No logging | Impossible to debug production failures | Log task start, skip reason, success, and each error level |
| `max_retries=None` | Infinite retries on a broken integration | Set a finite `max_retries` (3–5 is usually enough) |
