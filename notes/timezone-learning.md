# Timezone-Aware Timestamps (Postgres + SQLAlchemy)

## Short Summary
- `timestamp without time zone` drops tz info on round-trip, even in Postgres.
- Prefer `timestamptz` (`DateTime(timezone=True)`) for real moments in time.
- Generate times in UTC (`datetime.now(timezone.utc)`), store as aware.
- Alembic autogenerate may miss or under-specify timezone changes.
- When converting existing `timestamp` data to `timestamptz`, use `AT TIME ZONE 'UTC'`
  so stored values are interpreted as UTC during the type change.
- After migrating, remove defensive "naive datetime" comparisons in app code.

## Q/A Flashcards
Q: Why can comparing datetimes fail in Python with SQLAlchemy?
A: It fails when you compare timezone-aware datetimes (e.g., `now(timezone.utc)`) to
   timezone-naive datetimes loaded from the DB.

Q: What Postgres type should you use for real points in time?
A: `timestamptz` (SQLAlchemy: `DateTime(timezone=True)`).

Q: What happens if you use `timestamp without time zone` in Postgres?
A: The DB drops timezone info on write/read, returning naive datetimes.

Q: Why is `timestamptz` safer than `timestamp` for production?
A: It preserves a real moment in time, supports correct timezone conversions, and
   avoids ambiguous comparisons.

Q: What’s the app-level rule for timestamps?
A: Always generate and compare in UTC with timezone-aware datetimes.

Q: Does Alembic autogenerate always do the right thing for timezone changes?
A: No. You must review and often edit the migration.

Q: How do you safely convert existing `timestamp` data to `timestamptz`?
A: Use `ALTER COLUMN ... TYPE timestamptz USING col AT TIME ZONE 'UTC'`.

Q: Where does the `AT TIME ZONE 'UTC'` conversion belong?
A: Inside the migration file (`postgresql_using=...`) so the change is applied in DB.

Q: After migrating to `timestamptz`, should you keep naive datetime fixes in code?
A: No, remove them and compare aware datetimes directly.

Q: What’s a quick checklist for this migration?
A: Update models to `DateTime(timezone=True)`, generate migration, add `AT TIME ZONE`
   conversions, run `db upgrade`, then clean up app logic.
