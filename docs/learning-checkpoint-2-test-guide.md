# Checkpoint 2: try Learn and Review

From the repository root:

```sh
poetry run python scripts/learning-preview-fixture.py --concept
```

The script disables dotenv and uses a temporary SQLite database with disposable content and progress. It does not publish content or modify your real account. PostgreSQL migration/concurrency verification is covered by the automated suite separately.

1. Open [the local login](http://127.0.0.1:5057/login). Sign in with `learning1@example.test` / `LearningPreview123!`.
2. Open **Learning → Idempotency and uncertain outcomes**. Expand the lesson sections. In the simulation, compare a lost response with the same key versus a new key; expect one versus two orders.
3. Select **Review due questions**. Explain a question, select **Show answer**, then **Good**. Expect a saved message and the next question. Return to the lesson: its due count should decrease. Complete all four to reach **No questions due right now**.
4. Sign out and sign in as `learning2@example.test` with the same fixture password. Expect four questions due: progress belongs to each account.

Stop the server with **Ctrl+C**; restart to reset the demo. The fixture includes additional legacy notes for regression checks, so its flashcard count is intentionally larger than the repository's 37 cards.

To practise testing the code:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
  poetry run python -m unittest discover -s tests -p 'test_concept_web.py' -v
npm run test:browser
```

Use the repository's Node version (`nvm use`) for npm commands. A useful test to read is `test_old_question_version_can_finish_without_resetting_progress`: it changes published content while a review is in progress and proves the original version is retained.
