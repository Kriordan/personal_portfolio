# Learning home: a 10-minute developer walkthrough

Use the disposable preview: `poetry run python scripts/learning-preview-fixture.py --concept`.
Open <http://127.0.0.1:5057/learning/>. If asked, sign in with
`learning1@example.test` / `LearningPreview123!`. This uses a temporary database
and a fake interviewer. Its hundreds of sample notes are deliberate stress data.

## 1. Follow the navigation in DevTools

In **Network**, enable **Preserve log**. Open My flashcards, search for
`Practice 02`, and use Next. Inspect the document requests:

- Search and pagination use GET with `q` and `page` in the URL. Reload keeps them.
- The response is HTML; no background API write is needed for browsing.
- Signed-in responses include `Cache-Control: private, no-store`.
- The due count and Start review still cover all your personal cards, even while searching.

In the Console, count the notes rendered on this page:

```js
document.querySelectorAll('.learning-hub-notes a').length // at most 25
```

Use the device toolbar at 390 and 320 pixels. Tab through the page: the first
control is Skip to content; Enter should focus the main content. A Performance
recording of a reload lets you inspect how much HTML/layout work this bounded
list needs. The Learning home itself contains no note list.

## 2. Trace one saved change

Start a personal flashcard review, reveal a card, and rate it Good. In Network,
inspect the `/learning/rate` POST and its response: find `card_id`, `request_id`,
`expected_revision`, and the resulting review schedule. Return to My flashcards
and reload; the saved rating should still affect the due count. The concept's
Review count is independent.

On the idempotency lesson, start practice, edit an artifact, and Save and pause.
Return to Learning and use Continue practice. Compare the session UUID in the
URL and the saved artifact. Opening it should leave it paused until you choose
Resume session. For recovery experiments, use the [workspace guide](learning-workspace-test-guide.md).

## 3. Inspect HTTP without the browser

```sh
http --headers :5057/learning/references
http --headers :5057/learning/flashcards
```

Without a login cookie, expect 200 for references and 302 to login for flashcards.
For an authenticated request, use Network → **Copy as cURL** on your flashcard
GET and run it locally; compare the headers and HTML with the browser response.

## 4. Explore the Python pieces

From the repo root, start a REPL:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from pathlib import Path
from project.services import learning_service
notes = learning_service.load_notes(Path("notes"))
[(note["id"], note["title"]) for note in notes[:3]]
cards = learning_service.build_cards(notes)
cards[0].keys()
help(learning_service.summarize_notes_for_user)
```

These calls read checked-in notes, not the running preview's synthetic notes or
database. They let you inspect the content-to-card transformation without
changing progress. The existing summary service adds each user's schedule to
that content when the flashcard page is requested.
