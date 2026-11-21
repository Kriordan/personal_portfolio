# Checkpoint 5b: investigate saved syntax checks

Pick one experiment; predict what will happen before trying it. This checkpoint
checks syntax, not design reasoning. It never calls AI or changes review scheduling.

## DevTools: follow a snapshot from editor to saved history

Use the new disposable preview at <http://127.0.0.1:5058/learning/>. If it isn't
running, start it from the repository root:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python scripts/learning-preview-fixture.py --concept --port 5058
```

Login: `learning1@example.test` / `LearningPreview123!`. Port 5058 keeps any
older demo on 5057 intact. Demo progress disappears when its process stops.

1. Start/resume idempotency practice. In **Build → API**, select **JSON** and enter
   `{"path":"/orders",}`. Type a question in the message box without sending it.
2. In DevTools **Network**, enable **Preserve log** and select **All** (these are
   document requests). Choose **Checks → Save and check**.
3. Inspect the POST's **Payload**: `action=submit`, `request_id`,
   `expected_sequence`, `brief_revision`, and each artifact's base revision/body.
   The unsent message travels with the form for recovery, but is not recorded
   in the snapshot or conversation. It should still be in the composer.
4. Inspect **Response** and the UI: a syntax issue, line/column, and an exact
   revision link. Fix the trailing comma and check again. Open the earlier
   snapshot: it still reports the original issue and identifies newer saved work.
5. Right-click the POST → **Copy as cURL**, run that unchanged command in a
   terminal, and inspect the response. The same request replays the same snapshot.
   Copying that request into Postman works too. A changed payload needs a new UUID.

In **Console**, inspect the form's revision fields without submitting anything:

```js
const fields = new FormData(document.querySelector('[data-practice-form]'));
Object.fromEntries([...fields].filter(([name]) => /revision|sequence|request_id/.test(name)));
```

Try a second tab: save a changed API there, then check from the older tab. Expect
409 and no snapshot until you have reviewed the newer work.

## Python REPL: inspect the checker and step through it

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

```python
from pprint import pprint
from project.learning.artifact_checks import check_artifact, CHECKER_VERSION
CHECKER_VERSION
pprint(check_artifact("json", '{"path":"/orders",}'))
pprint(check_artifact("json", '{"path":"/orders"}'))
pprint(check_artifact("yaml", 'a: &shared [1]\nb: *shared'))
pprint(check_artifact("sql", 'CREATE TABLE orders (id bigint);'))

import pdb
pdb.runcall(check_artifact, "json", '{"path": }')
# n = next line; s = step in; p body = inspect; c = continue
```

Explain why aliases and SQL return `not_checked`, while malformed JSON returns
`error`. “Not checked” describes the checker's limits, not a mistake in the design.

## DevTools: lose a confirmation, then recover

Only on the disposable preview, use Console:

```js
await fetch('/fixture/state', {
  method: 'POST', headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({practice: 'lost'})
});
```

Choose **Save and check**. Expect the recovery page, HTTP 503, and your draft intact.
Note its hidden `request_id` in Elements. Change `lost` to `success` in the Console
call, then retry using the recovery button. The same ID recovers one snapshot.
Inspect <http://127.0.0.1:5058/fixture/results> before/after to confirm the count.
Repeat with `practice: 'failure'`: no snapshot is written before the retry.

For a profiling refresher, record one **Save and check** in Performance. Distinguish
the form navigation and rendering from server parsing. Use Network's Timing tab
for the request; client-side profiling does not measure Python execution.
