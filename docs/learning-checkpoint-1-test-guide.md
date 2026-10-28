# Checkpoint 1: five-minute practice

Run these commands from the repository root. No running database or AI credentials are needed.

1. **Run the nine content/security tests.** Expect `OK`.

   ```sh
   PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true \
     poetry run python -m unittest discover -s tests -p 'test_curriculum.py' -v
   ```

2. **Read one test and its implementation.** Start with `test_facilitator_gets_only_approved_facts_and_never_evaluation` in `tests/test_curriculum.py`, then find `facilitator_view` in `project/learning/content_schema.py`. Predict what happens when an unknown constraint ID is requested.

3. **Make a small change and watch a test fail.** Temporarily change the expected disclosed ID in that test from `scope` to `window`; rerun the command. Read the assertion difference, undo your edit, and rerun to return to green. Use `git diff` to verify your test edit is gone.

The database half is eight additional tests covering atomic imports, concurrent publication, crash recovery, and migration preservation. See [the PostgreSQL commands](engineering-learning-milestone-1.md#validation-evidence); they require a **disposable** local `library_sync_test` database and delete fixture tables. CI supplies one automatically.

There is no new browser screen in checkpoint 1. The lesson and exercise remain drafts; testing does not publish them.
