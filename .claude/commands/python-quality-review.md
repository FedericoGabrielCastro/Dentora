# python-quality-review

Review Python code in Dentora against black, flake8, and mypy standards. Propose minimal, focused fixes.

**Usage:** `/python-quality-review <path> [optional: focus area]`

**Examples:**
- `/python-quality-review appointments/serializers.py`
- `/python-quality-review appointments/ focus on typing`
- `/python-quality-review .` (full project review)

---

## What this skill does

You are reviewing Python code in the Dentora backend for style, lint, and type correctness.
Read the target file(s) before doing anything. Do not rewrite entire files — propose the smallest change that fixes each issue.

The argument is: $ARGUMENTS

---

## Step 1 — Run the tools first

Before any manual review, simulate what each tool would report:

```bash
poetry run black --check --diff <path>
poetry run flake8 <path>
poetry run mypy <path>
```

Report the output of each. If all three pass cleanly, say so and stop — do not invent issues.

---

## Step 2 — Black (formatting)

Black is non-negotiable. Any diff from `black --check` is a required fix.

Do not manually reformat. State which lines need reformatting and apply `black` output exactly.
The only acceptable reason to not apply a black change is a `# fmt: off` block with a documented reason in a comment.

**Common violations to flag:**
- Lines over 88 characters
- Inconsistent string quotes (black prefers double quotes)
- Missing blank lines between top-level definitions
- Trailing commas missing in multi-line structures (black adds them)

---

## Step 3 — Flake8 (lint)

Review each warning. Not all flake8 warnings require the same urgency:

**Fix immediately:**

| Code | Issue |
|------|-------|
| `F401` | Unused import — delete it |
| `F811` | Redefined name — remove the duplicate |
| `F841` | Local variable assigned but never used |
| `E711` | Comparison to `None` with `==` — use `is None` |
| `E712` | Comparison to `True`/`False` with `==` — use `is True` or just the value |
| `W291` / `W293` | Trailing whitespace |
| `E501` | Line too long (if black didn't catch it, there's a string or comment involved) |

**Review with judgment:**

| Code | Issue | When to fix |
|------|-------|-------------|
| `C901` | Function too complex (McCabe) | If complexity > 10, consider splitting |
| `W503` / `W504` | Line break around binary operator | Follow project convention, pick one |
| `E402` | Module-level import not at top | Fix unless there's a runtime reason (e.g., Django setup) |

**Do not suppress with `# noqa` unless:**
- There is a genuine false positive
- The suppression includes a reason: `# noqa: F401 — re-exported for public API`

---

## Step 4 — Mypy (types)

Focus on errors, not just missing annotations. Missing annotations on existing code are lower priority than incorrect types on new code.

**Errors to fix:**

| Error | Meaning | Fix |
|-------|---------|-----|
| `error: Argument ... has incompatible type` | Wrong type passed | Fix the type or the annotation |
| `error: Item "None" of "Optional[X]" has no attribute` | Unguarded optional | Add `if x is not None` guard or use `assert` |
| `error: Return type ... incompatible` | Function returns wrong type | Align implementation or annotation |
| `error: Cannot determine type of ...` | Untyped variable in typed scope | Add annotation |
| `error: Missing return statement` | Code path returns nothing | Add explicit return or fix the logic |

**Annotations to add on new or touched code:**
- All function signatures: parameters and return type
- Class attributes that mypy cannot infer
- `Optional[X]` for values that can be `None`; do not use `X | None` unless the project is on Python 3.10+

**Do not:**
- Add `# type: ignore` to silence an error without a comment explaining why
- Annotate every local variable — only where mypy cannot infer

**Django/DRF-specific patterns:**
```python
# QuerySets need explicit generics
def get_upcoming(dentist: Dentist) -> QuerySet[Appointment]: ...

# Optional FK
dentist: Optional[Dentist] = models.ForeignKey(..., null=True)

# Serializer validated_data is typed as dict — narrow it explicitly
data: AppointmentBookData = serializer.validated_data  # type: ignore[assignment]
# (only acceptable if a TypedDict is defined for this serializer)
```

---

## Step 5 — Manual review (beyond the tools)

After the tools, check these by reading the code:

**Imports**
- Imports are grouped: stdlib → third-party → Django → local. One blank line between groups.
- No circular imports (app A imports from app B which imports from app A).
- No wildcard imports (`from module import *`).

**Names**
- Functions and variables: `snake_case`. Classes: `PascalCase`. Constants: `UPPER_SNAKE_CASE`.
- No single-letter names outside of loop counters (`i`, `j`) or list comprehensions.
- Boolean variables and functions start with `is_`, `has_`, `can_`, `should_`.
- Functions named after what they do, not how: `cancel_appointment`, not `set_status_to_cancelled`.

**Complexity**
- Functions with more than ~20 lines: flag for review, not necessarily a required fix.
- Nested conditionals deeper than 2 levels: suggest early return or extraction.
- Magic numbers (hardcoded `60`, `24`, `3`): suggest extracting to a named constant.

**Comments**
- No commented-out code. Delete it — git history exists.
- Comments explain *why*, not *what*. `# retry 3 times` on a retry loop is noise. `# SMTP provider limits to 3 attempts per minute` is useful.

---

## How to report findings

Group findings by severity. Propose the fix inline — do not just list the problem.

```
## Black
✓ No issues.

## Flake8
- appointments/services.py:14 — F401: `from django.utils import timezone` imported but unused. Remove it.
- appointments/services.py:47 — E711: `if appointment.status == None` → `if appointment.status is None`

## Mypy
- appointments/services.py:32 — error: Argument "dentist" has incompatible type "int"; expected "Dentist"
  Fix: load the Dentist instance before passing it, or change the function signature to accept `dentist_id: int`.

## Manual
- appointments/services.py:58 — magic number `60` in retry countdown. Extract to `RETRY_COUNTDOWN_SECONDS = 60`.
- appointments/views.py:23 — nested conditional 3 levels deep. Consider early return for the invalid-state check.
```

Apply fixes only where the change is clear and safe. For judgment calls (complexity, naming), flag them and let the developer decide.

---

## Approval criteria

The file passes review when:

- [ ] `black --check` exits with code 0 — no diff
- [ ] `flake8` reports no errors (warnings marked `# noqa` have a written reason)
- [ ] `mypy` reports no new errors on touched functions/classes
- [ ] No unused imports
- [ ] No `== None` / `== True` / `== False` comparisons
- [ ] All function signatures on new or modified functions have type annotations
- [ ] No `# type: ignore` or `# noqa` without an inline explanation
- [ ] No commented-out code
- [ ] No magic numbers in business logic (timeouts, limits, thresholds)
- [ ] Import groups are ordered: stdlib → third-party → Django → local

---

## What this skill does NOT do

- Does not rewrite working logic to make it "cleaner" — only fixes quality issues
- Does not add docstrings or comments to code that was not touched
- Does not enforce opinions beyond black, flake8, mypy, and the rules above
- Does not flag complexity as a required fix — only as a suggestion
