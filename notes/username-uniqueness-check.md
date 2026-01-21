# Username Uniqueness Check (Signup)

## Short Summary
- Checking username availability before insert avoids `IntegrityError` on unique constraints.
- Add a quick `SELECT` using the submitted username and reject early with a flash message.
- Keep the flow consistent with existing email uniqueness checks to reduce race-prone UX.
- Return the signup form with the user input intact so they can choose a new name.

## Q/A Flashcards
Q: Why can a signup endpoint throw `IntegrityError` for usernames?
A: If the database has a unique constraint and the code inserts without checking
   first, duplicates trigger a constraint violation.

Q: What is the minimal pre-insert guard for a username?
A: Query for an existing user with the same username and bail out if found.

Q: Where should the check live in the request flow?
A: After form validation and before creating the user record.

Q: What user-facing response should be returned on conflict?
A: Flash a clear message and re-render the signup form so they can choose another.

Q: Does this fully eliminate duplicates in all cases?
A: It prevents most UX errors, but the DB constraint remains the final guard.
