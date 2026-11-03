# Checkpoint 5e: inspect a session export

Preview: <http://127.0.0.1:5063/learning/>. Login:
`learning1@example.test` / `LearningPreview123!`. To start it yourself:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python scripts/learning-preview-fixture.py --concept --feedback-example --port 5063
```

This is disposable data and scripted AI. Existing previews use other ports.

## DevTools and downloaded files

1. Resume the example, open **Build → Session details**, then **JSON** or
   **Markdown**. The workspace stays open. The same links appear before deletion.
2. In **Network → All → Preserve log**, inspect the GET ending in `/export/json`
   or `/export/md`. Expect `Content-Disposition: attachment`, a UUID-based
   filename, `Cache-Control: private, no-store`, and `X-Content-Type-Options: nosniff`.
   Because the link opens separately, use **Auto-open DevTools for popups** if
   your browser doesn't show the request in the original tab.
3. Leave a distinctive edit unsaved and download again. Your draft stays in the
   editor; the file contains the last saved revision. Save it, download again,
   and compare `artifacts[].current_revision` and `revisions`. Old feedback still
   cites the original revision, whose body is also in the file.
4. Open JSON in your editor or use `python -m json.tool <downloaded-file.json>`.
   Inspect `submissions[0].feedback.findings`: your latest agree/disagree response
   and note are present; private misconception mappings and reference solutions
   are absent. Markdown has the same saved work in readable sections.

Right-click the GET → **Copy as cURL**, append `--output /private/tmp/session.json`,
and run it in a terminal; or import the copied request into Postman. This uses
your browser session cookie. The separate JWT endpoint is
`/api/v1/learning/practice/sessions/<session-id>/export/json` (or `/md`), using
the existing API login flow. Repeating a download creates no receipts or ratings;
it reads a fresh consistent snapshot, so its timestamp or saved contents may change.

HTTPie can inspect counts and simulate unavailable reads in the disposable preview:

```sh
http GET :5063/fixture/results
http POST :5063/fixture/state reads=failure
# Try downloading: expect 503, without an attachment. The workspace stays open.
http POST :5063/fixture/state reads=success
# Retry the download, then compare counts: exporting changed nothing.
http GET :5063/fixture/results
```

## Python REPL: call the exporter directly

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from pathlib import Path
from tests.test_practice_export import PracticeExportTests
from project.services import practice_export_service as exports

fixture = PracticeExportTests()
fixture.setUp()  # independent in-memory data, not the running preview
document = exports.session_export(fixture.user.id, fixture.sid)
document['schema_version']                          # 1
document['artifacts'][0]['revisions'][1]['body']      # original saved work
document['submissions'][0]['feedback']['findings'][1]['evidence']
len(exports.render(document, 'json'))               # UTF-8 download bytes
Path('/private/tmp/practice-demo.md').write_bytes(exports.render(document, 'md'))
# For stepping: breakpoint(); then s into session_export(), n, p document, c.
fixture.tearDown()
```

If you experiment with ORM writes in this in-memory fixture, explicitly commit
or roll them back before exporting; its shared connection cannot isolate them.

Exports include full saved history and latest feedback responses, not unsaved
drafts or unfinished AI output. They are portable records; importing/restoring
them is outside this checkpoint. A 32 MiB allowance rejects oversized exports
explicitly rather than truncating them (`LEARNING_EXPORT_MAX_BYTES` for operators).
