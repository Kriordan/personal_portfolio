# Learning App

A spaced repetition system optimized for retaining software engineering lessons. Capture debugging incidents, technical concepts, and CLI commands as flashcards, then review them on an intelligent schedule that maximizes long-term retention.

## Features

- **Two Scheduling Algorithms**: SM-2 (classic SuperMemo) and HLR (Half-Life Regression)
- **Multiple Card Types**: Q/A, incident, cloze, command, and code_diff
- **Interleaved Sessions**: Prevents topic bingeing with smart queue ordering
- **Per-Tag Recall Targets**: Higher retention for critical knowledge (security, auth, etc.)
- **Session Analytics**: Track lapses, graduations, and weak areas
- **Keyboard Shortcuts**: Space to flip, 1-4 to rate
- **Debug Mode**: Inspect scheduler decisions for admin users

## Architecture

```
project/learning/
├── __init__.py              # Blueprint registration
├── views.py                 # Routes and card builder
├── queue_builder.py         # Session interleaving logic
├── scheduler_config.py      # SM-2 and HLR parameters
├── recall_config.json       # Per-tag target recall overrides
├── spaced_repetition.py     # Core SM-2 algorithm
├── schedulers/
│   ├── __init__.py          # ScheduleInput/Output dataclasses
│   ├── factory.py           # Scheduler factory
│   ├── sm2.py               # SM-2 scheduler
│   └── hlr.py               # HLR scheduler
└── templates/learning/
    ├── index.html           # Notes list
    ├── review.html          # Review session
    └── note.html            # Single note view
```

## Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/learning/` | List notes with due card counts |
| GET | `/learning/review` | Start review session with due cards |
| GET | `/learning/note/<note_id>` | View a specific note's flashcards |
| POST | `/learning/rate` | Submit a card rating (0-5) |
| POST | `/learning/api/incident` | Create incident card (admin only) |

## Card Types

### Q/A (default)

Basic question and answer format.

```json
{
  "id": "tz-1",
  "question": "Which Postgres type stores timezone info?",
  "answer": "timestamptz (DateTime(timezone=True))"
}
```

### Incident

Captures real debugging lessons with symptom/cause/fix/prevention structure.

```json
{
  "id": "inc-1",
  "type": "incident",
  "title": "Alembic migration timezone bug",
  "symptom": "TypeError comparing naive and aware datetimes",
  "root_cause": "DB column used timestamp without timezone",
  "fix": "Use DateTime(timezone=True) + migrate with AT TIME ZONE 'UTC'",
  "prevention": "Add tests + enforce UTC timestamps"
}
```

**Rendered prompt**: "Symptom: {symptom}\n\nWhat's the likely root cause? How do you fix it? How do you prevent regression?"

### Cloze

Fill-in-the-blank using `{{c1::answer}}` syntax.

```json
{
  "id": "cloze-1",
  "type": "cloze",
  "text": "In Postgres, use {{c1::timestamptz}} to store real points in time."
}
```

**Rendered prompt**: "In Postgres, use [...] to store real points in time."

### Command

CLI commands and one-liners for muscle memory.

```json
{
  "id": "cmd-1",
  "type": "command",
  "prompt": "Convert column to timestamptz safely",
  "answer": "ALTER COLUMN ... TYPE timestamptz USING col AT TIME ZONE 'UTC';"
}
```

### Code Diff

Before/after code changes.

```json
{
  "id": "diff-1",
  "type": "code_diff",
  "prompt": "Fix model timestamps",
  "before": "db.DateTime()",
  "after": "db.DateTime(timezone=True)"
}
```

## Note Format

Notes are JSON files stored in `/notes/*.json`:

```json
{
  "id": "timezone-learning",
  "title": "Timezone-Aware Timestamps",
  "created_at": "2026-01-16",
  "tags": ["postgresql", "sqlalchemy", "datetime"],
  "summary": "Brief description of the topic...",
  "flashcards": [
    { "id": "tz-1", "question": "...", "answer": "..." },
    { "id": "inc-1", "type": "incident", "symptom": "...", ... }
  ]
}
```

Cards can have their own `tags` array which merges with note-level tags.

## Schedulers

### SM-2 (`sm2_v2_steps`)

Classic SuperMemo algorithm with learning steps:

- **New cards**: Enter learning phase with 10min and 1-day steps
- **Review**: Interval grows based on easiness factor (2.5 default)
- **Lapse**: Failed cards re-enter relearning steps
- **Graduation**: After passing all steps, enters review phase

### HLR (`hlr_v1`)

Half-Life Regression scheduler with predicted recall:

- **Half-life model**: Memory decays exponentially; half-life grows with successful reviews
- **Target recall**: Schedule review when predicted recall drops to target (default 0.9)
- **Multipliers**: Rating 3=1.4x, Rating 4=1.8x, Rating 5=2.2x half-life growth
- **Lapse penalty**: 0.5x half-life on failure
- **Graduation**: Cards with 180+ day half-life get 90-day confidence checks

Change scheduler per-user via `User.scheduler_preference`.

## Per-Tag Target Recall

Configure higher retention for critical topics in `recall_config.json`:

```json
{
  "tags": {
    "security": 0.95,
    "auth": 0.93,
    "migrations": 0.92
  },
  "default": 0.9
}
```

Cards tagged with `security` will be reviewed more frequently to maintain 95% recall.

## Session Queue Building

The `build_review_queue()` function orders cards to maximize learning:

1. **Prioritize weak cards**: Recent lapses, short intervals, relearning state
2. **Interleave topics**: No more than 2 consecutive cards from the same note
3. **Interleave tags**: No more than 3 consecutive cards sharing the same primary tag
4. **Light randomness**: Prevents memorizing card order

## Rating Scale

| Key | Rating | Meaning |
|-----|--------|---------|
| 1 | 0 | Again (complete failure, re-enter learning) |
| 2 | 3 | Hard (correct but difficult) |
| 3 | 4 | Good (correct with effort) |
| 4 | 5 | Easy (instant recall) |

## Keyboard Shortcuts

- **Space**: Flip card (show answer)
- **1**: Rate "Again" (0)
- **2**: Rate "Hard" (3)
- **3**: Rate "Good" (4)
- **4**: Rate "Easy" (5)

## Debug Mode

Admins see scheduler debug info in the `/rate` response. Non-admins can add `?debug=1` to the review URL:

```json
{
  "debug": {
    "scheduler_version": "hlr_v1",
    "predicted_recall_before": 0.91,
    "predicted_recall_after": 0.97,
    "half_life_days": 12.4,
    "target_recall": 0.9,
    "next_review": "2026-02-14T10:23:00Z"
  }
}
```

## Database Models

### ReviewProgress

Current state for each card per user:

| Field | Type | Description |
|-------|------|-------------|
| card_id | string | `{note_id}:{card_id}` |
| learning_state | string | new/learning/review/relearning |
| step_index | int | Current learning step (nullable) |
| lapses | int | Failure count |
| half_life_days | float | HLR memory half-life |
| predicted_recall | float | Current recall probability |
| target_recall | float | Desired recall threshold |
| easiness | float | SM-2 easiness factor |
| interval | int | Days until next review |
| next_review | datetime | When card is due |
| is_suspended | bool | Excluded from reviews |
| graduated_at | datetime | When card reached mastery |

### ReviewLog

Historical record of every review:

- Before/after state for all fields
- `response_ms`: Time to answer (for future difficulty estimation)
- `session_id`: Groups reviews in a session

## Creating Notes

### Manual JSON

Create `notes/my-topic.json` following the note format above.

### Cursor Commands

Use `.cursor/commands/create-learning-note.md` or `.cursor/commands/create-incident-note.md` to generate notes from chat sessions.

### API Endpoint (Admin)

```bash
curl -X POST /learning/api/incident \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Connection pool exhaustion",
    "symptom": "Timeouts under load",
    "root_cause": "Pool size too small",
    "fix": "Increase pool_size to 20",
    "prevention": "Add pool monitoring alert",
    "tags": ["postgresql", "performance"]
  }'
```

## Tests

```bash
# Run all learning tests
pytest tests/test_scheduler.py tests/test_hlr_scheduler.py tests/test_card_builder.py tests/test_queue_builder.py

# Run specific test
pytest tests/test_queue_builder.py::QueueBuilderTests::test_build_review_queue_interleaves_and_keeps_all_cards
```

## Configuration

### Scheduler Parameters (`scheduler_config.py`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| LEARNING_STEPS | [10min, 1day] | Steps for new cards |
| RELEARNING_STEPS | [10min, 1day] | Steps after lapse |
| GRADUATING_INTERVAL_DAYS | 3 | First review interval |
| HLR_INITIAL_HALF_LIFE | 0.5 | Starting half-life (days) |
| HLR_DEFAULT_TARGET_RECALL | 0.9 | Default recall target |
| HLR_GRADUATION_HALF_LIFE_DAYS | 180 | Half-life for mastery |

## Session Summary

At session end, the UI displays:

- **Reviewed**: Total cards reviewed
- **Lapses**: Cards rated "Again"
- **Graduated**: Cards that moved from learning to review
- **Weak areas**: Top 3 tags with most lapses

## Migrations

The learning models require these migrations:

1. `3767349966b5_add_review_progress.py` - ReviewProgress table
2. `c48018381e52_add_review_log_and_scheduler_version.py` - ReviewLog table
3. `9e5947e5a52a_add_learning_state_fields.py` - Learning state fields
4. `01b6b2a3c6ef_add_hlr_fields.py` - HLR fields (half_life, predicted_recall, target_recall)
5. `1f2a3b4c5d6e_add_review_progress_graduation.py` - Graduation fields (is_suspended, graduated_at)

## References

- [SM-2 Algorithm](https://www.supermemo.com/en/archives1990-2015/english/ol/sm2)
- [Half-Life Regression (Settles & Meeder, 2016)](https://aclanthology.org/P16-1038.pdf)
- [Spacing Effect (Cepeda et al., 2008)](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2831652/)
