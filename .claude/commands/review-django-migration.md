# review-django-migration

Review a Django migration for safety, reversibility, lock risk, and consistency with models.

**Usage:** `/review-django-migration <app> [migration name or number]`

**Examples:**
- `/review-django-migration appointments` (reviews the latest migration)
- `/review-django-migration appointments 0004`
- `/review-django-migration appointments 0004_add_status_to_appointment`

---

## What this skill does

You are reviewing a Django migration before it is applied to staging or production.
Read the migration file and the corresponding model(s) before writing anything.
Do not modify the migration — only report findings and recommendations.

The argument is: $ARGUMENTS

---

## Step 1 — Locate and read the migration

1. Find the file in `<app>/migrations/`.
2. If no specific migration is given, read the latest one (highest number).
3. Also read the current state of `<app>/models.py` to compare intent vs. implementation.
4. Check the previous migration in the sequence to understand what state the schema was in before.

---

## Step 2 — Classify the operations

List every operation in the migration and assign it a risk level.

### Schema operations

| Operation | Risk | Notes |
|-----------|------|-------|
| `CreateModel` | Low | New table, no existing data touched |
| `DeleteModel` | High | Irreversible data loss if not preceded by a data migration |
| `AddField` (nullable or with default) | Low | Non-blocking on most DBs |
| `AddField` (non-nullable, no default) | High | Requires a DB-level default or a two-step migration |
| `RemoveField` | Medium | Irreversible; data is dropped |
| `RenameField` | Medium | Locks table; application must deploy atomically |
| `RenameModel` | Medium | Locks table; breaks any raw SQL or external references |
| `AlterField` (type change) | High | May require full table rewrite on PostgreSQL |
| `AlterField` (adding `unique=True`) | Medium | Acquires lock while building the unique index |
| `AlterField` (adding `db_index=True`) | Low-Medium | Postgres can build indexes `CONCURRENTLY`; Django cannot by default |
| `AddIndex` | Low-Medium | See index note below |
| `AddConstraint` | Medium | Validates all existing rows; locks table briefly |

### Data operations

| Operation | Risk | Notes |
|-----------|------|-------|
| `RunPython` | Depends | Must have a reverse function; must be safe to re-run |
| `RunSQL` | High | Manually verify idempotency and reversibility |
| `RunPython(migrations.RunPython.noop)` as reverse | Acceptable | Only if the forward operation is genuinely irreversible |

---

## Step 3 — Check each risk category

### Nullability and defaults

- `AddField` with `null=False` and no `default`: **blocks the migration** on a non-empty table in PostgreSQL. Django adds a column-level default for the migration, then drops it — this works but locks the table. Flag it.
- `AddField` with `null=False` and a `default`: safe, but verify the default makes sense for existing rows. A default of `""` or `0` on a required field may silently corrupt old data.
- `RemoveField` on a field still referenced in code: application will break before the migration runs. The field must be removed from the codebase first.

**Safe pattern for adding a required field to a populated table:**
1. Migration 1: add the field as `null=True`.
2. Data migration: backfill the value for all existing rows.
3. Migration 3: alter the field to `null=False`.

If the submitted migration skips steps 1–2, flag it.

### Renames

- `RenameField` and `RenameModel` require the application code to be updated atomically with the migration. In a rolling deploy, the old name must remain available until all instances are updated.
- Check: is the renamed field or model still referenced anywhere in the codebase under the old name?

### Indexes

- Django's `AddIndex` does not use `CONCURRENTLY` by default. On a large table this acquires a lock that blocks reads and writes for the duration of the index build.
- Flag any `AddIndex` on a table that is expected to have significant data (`Appointment`, `Patient`).
- Recommend: run `CREATE INDEX CONCURRENTLY` manually in production and use `SeparateDatabaseAndState` in the migration to keep the migration state consistent.

### Constraints

- `AddConstraint` (e.g., `UniqueConstraint`, `CheckConstraint`) validates all existing rows. If any row violates the constraint, the migration fails mid-run.
- Check: are there existing rows that could violate the new constraint?
- For `UniqueConstraint`: is there a data migration beforehand that deduplicates rows?
- For `CheckConstraint`: does the constraint expression match the field types and possible values?

### Data migrations (`RunPython`)

Every `RunPython` must be reviewed for:

1. **Reverse function present?** `migrations.RunPython.noop` is acceptable only for genuinely irreversible operations. Document why in a comment.
2. **Idempotency:** can it be run twice without errors or duplicate data?
3. **Batch size:** does it load all rows into memory with `Model.objects.all()`? On large tables, use `iterator()` or process in batches.
4. **Direct model access:** data migrations must use the historical model from `apps.get_model()`, not import the current model class. Importing the current model breaks if the model changes later.

```python
# Correct
def forwards(apps, schema_editor):
    Appointment = apps.get_model("appointments", "Appointment")
    ...

# Wrong — breaks on future model changes
from appointments.models import Appointment
def forwards(apps, schema_editor):
    ...
```

5. **Transaction safety:** `RunPython` runs inside the migration transaction by default. If the operation is long-running, consider `atomic=False` on the migration and manual transaction management.

### Rollback safety

- Can this migration be reversed with `migrate <app> <previous>`?
- `DeleteModel` is not reversible without data.
- `RemoveField` is not reversible without data.
- `RunPython` without a reverse function is not reversible.
- If a migration is not reversible, document it explicitly with a comment in the migration file.

---

## Step 4 — Consistency with models

Compare the migration operations against `models.py`:

- Does every field in the migration exist in the current model with matching type, nullability, and constraints?
- Are there fields in the model that are not in the migration? (Missing `makemigrations` run.)
- Are there operations in the migration that are not reflected in the model? (Migration was edited manually.)
- Does the `Meta.constraints` and `Meta.indexes` in the model match what the migrations have built up?

Run mentally or suggest running:
```bash
poetry run python manage.py migrate --check
```
A non-zero exit means the migration state does not match the models.

---

## Step 5 — Report format

Produce a structured report with a clear risk rating.

```
## Migration: appointments/0004_add_status_to_appointment.py

**Overall risk: MEDIUM**

### Operations
1. AddField: Appointment.status (CharField, null=False, default="scheduled") — LOW RISK
   Existing rows will receive "scheduled" as the default. Verify this is correct for historical data.

2. AddIndex: Appointment — MEDIUM RISK
   Index on (dentist_id, scheduled_at). This table may already have data.
   Recommendation: run CREATE INDEX CONCURRENTLY manually in production.
   Use SeparateDatabaseAndState in this migration to keep the state consistent.

### Reversibility
- Reversible: YES (RemoveField and RemoveIndex are defined)

### Consistency with models.py
- ✓ Appointment.status field matches the model definition
- ✓ Index matches Meta.indexes

### Recommendations
1. Verify that "scheduled" is the correct default for existing appointment rows.
2. For the index: plan a CONCURRENTLY build in production to avoid locking the appointments table.

### Verdict
Approvable with the index caveat addressed before production deploy.
```

---

## Validation checklist

- [ ] Every operation has been classified with a risk level
- [ ] Non-nullable `AddField` without default has been flagged
- [ ] `RemoveField` / `DeleteModel` irreversibility is noted
- [ ] `RenameField` / `RenameModel` deploy atomicity is addressed
- [ ] `AddIndex` on large tables is flagged for `CONCURRENTLY`
- [ ] `AddConstraint` checked against existing data
- [ ] Every `RunPython` has a reverse function (or `noop` is justified)
- [ ] `RunPython` uses `apps.get_model()`, not direct model imports
- [ ] Large `RunPython` operations use batching or `iterator()`
- [ ] Migration is consistent with current `models.py`
- [ ] `migrate --check` outcome is stated
- [ ] Overall rollback safety is assessed
- [ ] Report ends with a clear verdict: approvable / approvable with conditions / blocked

---

## Automatic blockers

These must be resolved before the migration can be approved:

| Condition | Why it blocks |
|-----------|--------------|
| `AddField(null=False)` with no default on a non-empty table | Will fail at runtime on PostgreSQL |
| `RunPython` importing model classes directly | Will break on future schema changes |
| `RemoveField` on a field still used in application code | Application will crash before migration runs |
| Missing `makemigrations --check` pass | Model and migration state are out of sync |
| `RunSQL` with no rollback SQL | Deployment cannot be rolled back |
| `AddConstraint` on data that already violates it | Migration will fail mid-run, leaving schema in partial state |
