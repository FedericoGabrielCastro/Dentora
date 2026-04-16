# create-django-domain-model

Create or modify a Django model for Dentora following project conventions.

**Usage:** `/create-django-domain-model <app>.<ModelName> [brief description of what it represents]`

**Examples:**
- `/create-django-domain-model appointments.Appointment links a patient to a dentist at a specific time slot`
- `/create-django-domain-model patients.Patient demographic and contact info for a dental patient`
- `/create-django-domain-model appointments.AvailabilitySlot recurring weekly slot for a dentist`

---

## What this skill does

You are designing or modifying a Django model for Dentora, a dental appointment management backend.
Before writing anything, read the existing `models.py` in the target app (if it exists).
If the app does not exist, stop and say so — do not scaffold it silently.

The argument is: $ARGUMENTS

---

## Step-by-step process

### 1. Understand the entity

Identify what real-world concept this model represents:

| Entity | Core responsibility |
|--------|-------------------|
| `Patient` | Person receiving dental care. Has contact info, DNI, optional medical notes. |
| `Dentist` | Professional providing care. Has specialization, license number, linked to one or more clinics. |
| `Appointment` | A confirmed or pending booking between a patient and a dentist at a specific date/time. |
| `AvailabilitySlot` | A recurring or one-off time window when a dentist is available. Not an appointment itself. |
| `Treatment` | A procedure performed or planned during an appointment (e.g., extraction, cleaning). |
| `Clinic` | Physical location. A dentist can work at multiple clinics. |

### 2. Define fields

Apply these rules to every field:

**Naming and documentation**
- Use `verbose_name` on every field.
- Add `help_text` when the field name alone is ambiguous (e.g., `status`, `type`, `notes`).
- Use snake_case for field names. No abbreviations (use `first_name`, not `fname`).

**Nullability**
- `null=True, blank=True` only for genuinely optional data that may be absent in the DB.
- `blank=True` alone for optional text fields that default to `""`.
- Required fields: no `null`, no `blank`.
- Never use `null=True` on string fields (`CharField`, `TextField`) — use `blank=True` with `default=""` instead.

**Choices**
- Define as inner `TextChoices` class on the model.
- Name the class after the field (e.g., `AppointmentStatus`, `DentistSpecialization`).
- Include a `display_name` when the raw value is a code (e.g., `CANCELLED = "cancelled", _("Cancelled")`).

**Timestamps and traceability**
- Every model must have:
  ```python
  created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("created at"))
  updated_at = models.DateTimeField(auto_now=True, verbose_name=_("updated at"))
  ```
- For entities that can be deactivated without deletion, add:
  ```python
  is_active = models.BooleanField(default=True, verbose_name=_("active"))
  ```

**Relationships**
- Always set `on_delete` explicitly. Do not use `CASCADE` by default — choose what makes sense:
  - `CASCADE`: child is meaningless without parent (e.g., `AvailabilitySlot` → `Dentist`)
  - `PROTECT`: parent should not be deleted while children exist (e.g., `Appointment` → `Patient`)
  - `SET_NULL`: child survives but loses the reference (rare, use carefully)
- Always set `related_name` to a meaningful plural (e.g., `related_name="appointments"`).
- For M2M, define the `through` model if the relationship carries its own data.

**Indexes and constraints**
- Add `db_index=True` on fields used frequently in `filter()` or `order_by()`.
- Use `Meta.indexes` for composite indexes (e.g., dentist + date on `AvailabilitySlot`).
- Use `Meta.constraints` with `UniqueConstraint` or `CheckConstraint` for business invariants that must be enforced at the DB level (e.g., a patient cannot have two confirmed appointments at the same time).
- Prefer DB constraints over Python-only validation for data integrity that matters.

### 3. Define Meta

```python
class Meta:
    ordering = ["-created_at"]          # or whatever makes sense for this model
    verbose_name = _("appointment")
    verbose_name_plural = _("appointments")
    indexes = [...]                     # composite indexes if needed
    constraints = [...]                 # DB-level invariants if needed
```

### 4. Define __str__

Return a human-readable string that identifies the record unambiguously.
Examples:
- `Appointment`: `f"Appointment #{self.pk} — {self.patient} with {self.dentist} on {self.scheduled_at:%Y-%m-%d %H:%M}"`
- `Patient`: `f"{self.first_name} {self.last_name} (DNI: {self.dni})"`

### 5. Consider admin registration

After writing the model, register it in `admin.py`:
- `list_display`: fields useful for scanning records (name, status, date, related entity)
- `list_filter`: choices fields and date fields
- `search_fields`: name, DNI, email — anything staff would search by
- `readonly_fields`: `created_at`, `updated_at`
- For models with FK relationships, add `raw_id_fields` or `autocomplete_fields` for performance.

### 6. Consider migration impact

After defining the model, state:
- Whether this is a new model (safe) or a change to an existing one (check for nullability and default requirements).
- If adding a non-nullable field to an existing table, a `default` or a two-step migration is required.
- If adding a `UniqueConstraint` or index to an existing table with data, note the potential lock.
- Provide the command to generate the migration, but do not run it:
  ```bash
  poetry run python manage.py makemigrations <app> --name <descriptive_name>
  ```

### 7. Business logic boundary

Do not add to the model:
- Methods that call external services
- Methods that trigger side effects (emails, tasks)
- Complex query logic (move to a custom `Manager` or a service)

`clean()` is acceptable for single-record field-level invariants (e.g., `end_time > start_time`).
Cross-record rules (e.g., "no overlapping appointments for this dentist") belong in `services.py`.

---

## Validation checklist

Before considering the model done:

- [ ] Every field has `verbose_name`
- [ ] No `null=True` on `CharField` or `TextField`
- [ ] Choices defined as `TextChoices` inner class
- [ ] `created_at` and `updated_at` present
- [ ] All FK have explicit `on_delete` and `related_name`
- [ ] `__str__` is human-readable and unambiguous
- [ ] `Meta` has `ordering`, `verbose_name`, `verbose_name_plural`
- [ ] Composite indexes added for FK + date/status combinations used in filtering
- [ ] DB constraints added for invariants that must be enforced at the DB level
- [ ] Model registered in `admin.py` with `list_display` and `search_fields`
- [ ] Migration impact assessed and `makemigrations` command provided
- [ ] No business logic beyond `clean()` field-level checks

---

## Anti-patterns to avoid

| Anti-pattern | Why it's a problem | What to do instead |
|---|---|---|
| `fields = '__all__'` in serializers later generated from this model | Leaks internal fields, breaks on schema changes | Always list fields explicitly |
| `null=True` on string fields | Two representations of "empty" (`NULL` and `""`) | Use `blank=True, default=""` |
| Business logic in `save()` | Hard to test, runs on every save including migrations | Move to `services.py` |
| `CASCADE` everywhere | Silent data loss when a parent is deleted | Choose `on_delete` deliberately per relationship |
| No `related_name` | Django auto-generates confusing names, breaks on model rename | Always set a meaningful `related_name` |
| Constraints only in Python (`clean()`) | `bulk_create`, admin, and raw SQL bypass Python validation | Mirror critical invariants in `Meta.constraints` |
| Monolithic model with 20+ fields | Hard to reason about, slow to query | Split into related models (e.g., `Patient` + `PatientMedicalProfile`) |
| Generic `status = CharField(max_length=50)` with no choices | Anything can be written, hard to filter | Define `TextChoices` and restrict the field |
