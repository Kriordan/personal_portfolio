# Checkpoint 2c.2: try feedback and inspect its evidence

Released with Keith's approval on November 16, 2026: **Heroku v179** and standalone
**iPhone build 14**, from `8b508f3`.

[Install the updated iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/a55838d8-8dd0-40c0-a9dd-f5d43c9fd3b7).
Open the link in Safari on the registered iPhone and tap **Install**. Update your
existing app, then sign in with the website account if needed. It uses the hosted
API and works without your Mac. Existing saved sessions and all spending limits
are unchanged. These are hands-on exploration steps;
automated test results are in the [checkpoint log](engineering-learning-milestone-2.md#checkpoint-2c2--feedback-and-revision-on-iphone).

## Five-minute phone walkthrough

1. Open **Learning → Idempotency → Build → Feedback & snapshots** in your existing
   session. Save/discard unfinished Build drafts and send/clear any Discuss draft
   first. **Save snapshot** runs syntax checks without an AI charge.
2. Inspect **What was saved & checked**. Then explicitly **Request feedback**;
   this action uses the shared AI allowance. Leave and return: the same snapshot
   and eventual result remain available.
3. Read a finding, open its cited original revision/message/note, and examine the
   next step. **Revisit the explanation** opens Learn; Build returns you to the
   same session and snapshot.
4. **Revise this work**, save an edit, and reopen feedback. The older assessment
   is labelled; it has not silently changed to assess your edit. Save a new
   snapshot when ready. Feedback on that version is another explicit request.
5. Try large text. Check the tabs, snapshot picker, evidence, and revision action,
   then restore your preferred text size. This does not replace a VoiceOver audit.

## Inspect it yourself in a Python REPL

Use disposable data for these experiments. From the repo, with its Python env:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python scripts/learning-preview-fixture.py \
  --concept --feedback-example --port 5075
```

The fixture seeds one session with scripted feedback and uses fake AI. A local
QA phone build must point at that fixture; the signed hosted app cannot use it.
Open `python` in the project's environment:

```python
import requests
base = 'http://127.0.0.1:5075'
s = requests.Session()
def login():
    r = s.post(base + '/api/v1/auth/login', json={
        'email': 'learning1@example.test', 'password': 'LearningPreview123!'})
    r.raise_for_status()
    s.headers['Authorization'] = 'Bearer ' + r.json()['access_token']

login()
root = base + '/api/v1/learning/practice'
sid = s.get(root + '/sessions').json()['sessions'][0]['id']
url = root + '/sessions/' + sid
detail = s.get(url).json()
seq = detail['submissions'][0]['sequence']
snapshot = s.get(f'{url}/submissions/{seq}').json()
feedback = s.get(f'{url}/submissions/{seq}/feedback').json()
snapshot['submission']['checks']
feedback['feedback']['findings'][0]['evidence']
```

The fixture token expires after ten seconds: call `login()` again between
experiments. Keep tokens out of screenshots and saved Postman collections.
Read the cited revision independently, then compare it with today's head:

```python
login()
citation = feedback['feedback']['findings'][0]['evidence'][0]
old = s.get(f"{url}/artifacts/{citation['artifact_id']}/revisions/{citation['revision']}")
old.json()
s.get(url).json()['artifacts']
```

## DevTools / Postman experiments

- In the fixture's web workspace, keep DevTools **Network → All** open. Save a
  snapshot, then request feedback. Inspect the two separate POSTs and their
  `request_id`s. Web forms also produce document navigations; an XHR-only filter
  hides them. Postman can inspect the equivalent JWT endpoints: `POST
  .../sessions/<id>/submissions` and `POST .../submissions/<sequence>/feedback`.
- Read `GET .../receipts/<request_id>`. Snapshot receipts have operation `submit`;
  feedback receipts have operation `feedback`. Replaying an identical request
  preserves the same result, even after the current artifact changes.
- On the disposable fixture only, POST `{"practice":"lost","reads":"failure"}`
  to `/fixture/state`, then request feedback on a fresh snapshot. Close the phone
  app. Restore `{"practice":"success","reads":"success"}`, reopen, and resume.
  Inspect `/fixture/results`: recovery should add no duplicate feedback or charge.
  Saving a snapshot alone must not change its simulated AI ledger.

No snapshot automatically changes your recall schedule or confidence ratings.
