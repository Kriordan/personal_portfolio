# Checkpoint 2c.1: try Build and inspect its saves

Released with Keith's approval on November 14: **Heroku v177** and standalone
**iPhone build 11**, from `8e3bff8`.

[Install the Build iPhone preview](https://expo.dev/accounts/kriordan/projects/personal-portfolio/builds/077bde85-d29e-448b-9855-9d61a7b2635e).
Open the link in Safari on the registered iPhone and tap **Install**. Update
build 10 to get Build editing; sign in with the existing website account. The
app uses the hosted API and runs without your Mac. Spending limits are unchanged.

The maximum-text simulator review passed November 14, including a fix for tabs
that crowded their labels when text size changed while the app was open.
Physical iPhone acceptance and a full VoiceOver audit are still separate checks.

## Five-minute phone walkthrough

1. Open **Learning → Idempotency → Build**, then continue a session. Write a
   short API proposal. Wait for **Draft saved on this device**, close/reopen the
   app, and return to the same session: your draft should still be there.
   Reconnect to load the saved session after reopening.
2. Switch to **Discuss** before saving. Send should explain that Build edits
   need attention. Return to Build and **Save artifact**; the saved revision
   advances. Add a pinned decision in **Assumptions & decisions → Add a note**
   and **Save notes**. Nothing here requests paid AI.
3. Open that same session on the website: the artifact and note should match.
   Make a phone edit, then save a different web edit. Back on the phone, compare
   the newer saved version. Keeping the phone draft only updates its starting
   revision; you still explicitly Save. Discarding affects only the local draft.

## Two-minute large-text regression check

1. With Build open, use iPhone **Settings → Accessibility → Display & Text Size →
   Larger Text**. Enable the larger accessibility sizes and move the slider to
   the maximum. Return to the app: all four tab names should remain readable,
   wrapping onto additional rows. Switch Discuss → Build and confirm the same
   session remains selected.
2. In Build, open an artifact and inspect its notation choices, text field, draft
   status, and Save action. Open a note, change its type, and toggle **Pin this
   note**: its label should wrap beside the visible switch. Save and reopen the
   work; its saved revision should advance. These saves do not request AI.
3. Restore your previous text size. The tabs should reflow without restarting the
   app. The simulator check used the default `large` and the maximum
   `accessibility-extra-extra-extra-large`; repeat on the signed preview above.
   This is a layout check, not a full VoiceOver audit.

## Practice with a REPL and HTTPie/Postman

Use the disposable fixture for mutations and failure experiments, not your
hosted progress. Start it from the repository with the project's Python env:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python scripts/learning-preview-fixture.py --concept --port 5074
```

A local QA phone build must point at this fixture. The fixture uses fake AI and
documented disposable logins. In a Python REPL:

```python
import requests
from uuid import uuid4
base = 'http://127.0.0.1:5074'
s = requests.Session()
login = s.post(base + '/api/v1/auth/login', json={
    'email': 'learning1@example.test', 'password': 'LearningPreview123!'
})
login.raise_for_status()
s.headers['Authorization'] = 'Bearer ' + login.json()['access_token']
root = base + '/api/v1/learning/practice'
sessions = s.get(root + '/sessions').json()['sessions']
[(x['id'], x['concept_id']) for x in sessions]
```

Create a session in the fixture UI first if the list is empty. Choose its exact
ID, then examine the server's head independently from your unsaved phone draft:

```python
sid = sessions[0]['id']
url = root + '/sessions/' + sid
detail = s.get(url).json()
[(a['artifact_id'], a['revision'], a['body']) for a in detail['artifacts']]
detail['session_brief']
```

The fixture's access token lasts only ten seconds. Repeat the login/header
assignment when needed, or use `/api/v1/auth/refresh` with the refresh token as
Bearer authorization. Keep tokens out of screenshots and saved collections.

In Postman or HTTPie, inspect these requests (use the JWT as Bearer auth):

| Request | What to notice |
| --- | --- |
| `GET /api/v1/learning/practice/sessions/<id>` | Current artifact revisions, learner notes, and transcript are distinct. |
| `PUT .../sessions/<id>/artifacts/api` | Body contains `request_id`, `base_revision`, `language`, and `body`. A stale base returns 409. |
| `PUT .../sessions/<id>/brief` | Body contains `request_id`, `base_revision`, and the entire `entries` list; preserve IDs, pins, and sources. |
| `GET .../receipts/<request_id>` | Both kinds of save have operation `save`. Retry the identical request ID/body: one revision, same result. |
| `GET .../sessions/<id>/artifacts/api/revisions/<n>` | Historical content stays unchanged after a newer save. |

For interrupted-save practice, POST `{"practice":"lost","reads":"failure"}`
to `/fixture/state`. Save on the phone: the server commits but recovery remains
uncertain. Restore `{"practice":"success","reads":"success"}`, close/reopen,
and inspect the saved revision and `/fixture/results`. Recovery reads the receipt
without issuing a second PUT. In browser DevTools, the existing web workspace's
Network panel provides the other half of the phone/web comparison.

Sign-out clears unsaved device drafts; confirmed server artifacts remain.
For maximum-size testing, seed a 65,535-byte artifact through the fixture API and
add one character on the phone. Avoid generating 65,536 individual keystrokes.
