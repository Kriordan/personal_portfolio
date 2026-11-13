# Checkpoint 2a: Learn and Review on iPhone

November 13, 2026. This checkpoint brings **idempotency Learn and Review** to
the existing Expo app. Discuss, Build, feedback, self-assessment, and additional
concepts are not part of this mobile slice. The website keeps those features.

## Try it on your phone

The new backend endpoints and a new standalone `preview` build must be released
together. **Deployment and the signed preview are pending Keith's approval.**
The existing installed preview does not contain these screens.

Release precaution: clear Metro/EAS build caches when changing from the local
fixture to the hosted origin, then inspect the built bundle's actual API URL.
During verification, a cached transform retained the old local address until
`expo export --clear` was used. The final clean export targets the hosted API.

After release, open the Expo installation link in Safari on the already
registered iPhone and install it. Use your existing website account. The
preview uses the hosted API in `mobile/eas.json`; your Mac can be off. This is
internal distribution, not an App Store submission or an OTA update.

1. Open **Learning → Idempotency**. Browsing does not enroll you or change a
   review schedule. **Notes and flashcards** still opens the existing material.
2. Tap **Start learning** if you haven't enrolled on the website. Use the
   section picker or Next/Previous section to read the lesson. In the retry
   section, compare a lost response with a pre-commit failure and change the key.
3. Tap **Save my place** in a section. Leave and reopen the lesson. Refresh
   Learning on the website: Continue should point to the same section. A
   bookmark is explicit; scrolling alone does not save it or imply mastery.
4. Open **Review**, try answering aloud, then **Show answer**. Rate your actual
   recall with Again/Hard/Good/Easy. A rating changes the shared review schedule.
   The question advances only after its save is confirmed.
5. Background and reopen the app. Saved ratings and the bookmark should remain.
   **Revisit the explanation** opens the relevant lesson section. The bottom of
   the final section offers **Practice recall**.

Already reviewed questions may not be due. Don't reset your real progress to
exercise failures; use the disposable fixture below. An interrupted save offers
Check and explicit Retry; reconnection does not silently repeat a write.

## Hands-on engineering exploration

Use the same isolated fixture for the app, browser, and HTTP client:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python scripts/learning-preview-fixture.py --port 5072 --concept
```

The fixture prints disposable credentials and creates temporary data. Configure
your development client with `EXPO_PUBLIC_API_URL=http://127.0.0.1:5072` for the
iOS simulator, or your Mac's LAN address for a physical development phone.
An installed standalone hosted preview cannot be redirected with this variable;
it is embedded when that preview is built.

In **HTTPie or Postman**, sign in with the printed fixture account using
`POST /api/v1/auth/login` (`email` and `password`). Keep the returned access token
in a local, unsynced variable. It deliberately expires after ten seconds; the
app's existing refresh-token handling is exercised during the walkthrough.
Never put production tokens in a URL, screenshot, commit, or shared collection.

Inspect these requests using `Authorization: Bearer <access token>`:

| Request | What to look for |
| --- | --- |
| `GET /api/v1/learning/concepts` | Concept, draft label, due count, and account-scoped progress. |
| `GET /api/v1/learning/concepts/idempotency` | Lesson sections and saved section. No facilitator or evaluator material. |
| `POST /api/v1/learning/concepts/idempotency/enrollment` with `{}` | Explicit enrollment, safely repeatable without resetting your bookmark. |
| `GET /api/v1/learning/concepts/idempotency/review` | Questions with `card_id`, `content_version`, `progress_revision`; no answers. |
| `GET /api/v1/learning/concepts/idempotency/review/reveal` | Supply the question's `card_id`, `content_version`, and `expected_revision` as query parameters. Reveal is read-only. |
| `PUT /api/v1/learning/concepts/idempotency/reading-position` | Send the lesson version, section ID, current progress revision, and a new UUID `request_id`. Reuse the exact request when retrying. |
| `POST /api/v1/learning/concepts/idempotency/rate` | Send the question's version, card ID, current revision, chosen numeric rating, and UUID. The response is a durable receipt. |
| `GET /api/v1/learning/ratings/<request_id>` | Confirm an uncertain rating without sending another write. |

For a bookmark, the body is:

```json
{
  "content_version": 1,
  "section_id": "retries",
  "expected_revision": 1,
  "request_id": "replace-with-a-new-UUID"
}
```

Use values from your GET response; hosted content versions differ from the
fixture. Repeat the identical request and compare the revision. Then use the
old revision with a *different* UUID and section: expect 409, with the original
bookmark still intact. This reproduces two-device contention.

To investigate a lost rating response, only on the disposable fixture:

```sh
http POST :5072/fixture/state rating=lost receipts=failure
# Reveal and rate one question in the app. It must retain the pending rating.
http GET :5072/fixture/results
http POST :5072/fixture/state rating=success receipts=success
# Tap Check saved rating. A receipt should resolve it without a second rating.
http GET :5072/fixture/results
```

In the browser's **DevTools → Network**, perform the web equivalent against the
same fixture and inspect the page/form requests. Compare its updated progress
with the JSON API. Expo native traffic is not in Safari's webpage Network tab;
use React Native DevTools with a development build, your HTTP client, or the
fixture's local request log. Breakpoints in `concept-study.ts` and
`learning-session.ts` show the transitions from saving to checking/uncertain to
confirmed. Neither controller sends automatically when connectivity returns.

For a short **Python REPL** experiment without touching your data:

```python
from tests.test_concept_api import ConceptApiTests
from project.models import ReviewLog, ReviewReceipt
case = ConceptApiTests()
case.setUp()
body = case.rate_input()
first = case.call('POST', '/api/v1/learning/concepts/idempotency/rate', body)
again = case.call('POST', '/api/v1/learning/concepts/idempotency/rate', body)
first.status_code, first.json == again.json
ReviewLog.query.count(), ReviewReceipt.query.count()  # (1, 1)
case.tearDown()
```

Run the REPL with dotenv disabled, as above. `setUp` uses a disposable test
database, never the hosted database.

## Implementation and release notes

- New JWT adapters reuse the existing curriculum projection, enrollment,
  bookmarks, review scheduler, and receipt services. No migration, dependency,
  AI call, or infrastructure was added. Existing web and notes APIs are retained.
- Hosted owner-only access and exact labelled-draft policy cover every new
  endpoint. Answers are requested only on reveal. Evaluation/private reference
  material stays out of responses and the mobile bundle; the repository itself
  remains public.
- Pending bookmark intents and ratings use existing secure device storage and
  account fencing. Recovery reads first; stale revisions require an explicit
  refresh. No offline write queue or automatic POST retry was introduced.
- A newly opened lesson waits for its current server bookmark before choosing
  the initial section. Active review questions stay pinned while due counts
  refresh. Recovery from the Learning hub returns to the correct kind of review.
- The existing $5 shared AI allowance is unchanged; this checkpoint makes no
  paid calls. Release approval is still required before updating the hosted API
  and preparing a signed iPhone preview.

Automated evidence and native walkthrough results are recorded in the
[Milestone 2 checkpoint log](engineering-learning-milestone-2.md).
