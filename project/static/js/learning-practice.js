(() => {
  // Progressive enhancement only: saving, sending, conflicts and recovery all work without it.
  document.getElementById('practice-alert')?.focus();
  const form = document.querySelector('[data-practice-form]');
  if (!form) return;
  // An unsent message is unsaved whenever it has text, even when the page loaded with it
  // (saving keeps the draft in the box); a blank box is not.
  const drafts = [...form.querySelectorAll('[data-draft]')];
  const fields = [...form.querySelectorAll('textarea, select, input[type="checkbox"]')]
    .filter((field) => !drafts.includes(field));
  const read = (field) => (field.type === 'checkbox' ? field.checked : field.value);
  const initial = new Map(fields.map((field) => [field, read(field)]));
  // A re-rendered page (rejected or failed request) holds unsaved work from the start.
  const unsavedOnLoad = form.hasAttribute('data-unsaved');
  let submitting = false;
  const dirty = () => unsavedOnLoad
    || drafts.some((draft) => draft.value.trim() !== '')
    || fields.some((field) => read(field) !== initial.get(field));

  window.addEventListener('beforeunload', (event) => {
    if (submitting || !dirty()) return;
    event.preventDefault();
    event.returnValue = '';
  });
  form.addEventListener('submit', () => { submitting = true; });
  // Back/forward cache may restore this document after a submission. Its unsaved
  // draft guard must become active again when the learner returns.
  window.addEventListener('pageshow', () => { submitting = false; });
  const saveState = document.getElementById('practice-save-state');
  const showSaveState = () => {
    if (!saveState) return;
    const work = unsavedOnLoad || fields.some((field) => read(field) !== initial.get(field));
    const draft = drafts.some((field) => field.value.trim() !== '');
    const message = work ? `Unsaved work${draft ? ' · unsent message' : ''}`
      : draft ? 'Unsent message' : 'No unsaved changes.';
    if (saveState.textContent !== message) saveState.textContent = message;
  };
  form.addEventListener('input', showSaveState);
  form.addEventListener('change', showSaveState);
  showSaveState();

  // While the interviewer is replying, fetch every newer turn so this page's view stays current:
  // insert missing turns, advance expected_sequence, and announce changes without moving focus.
  // A dropped connection or a server error (a restart, say) is retried with growing waits. A
  // sign-out redirect, a 4xx, or a non-JSON answer stops at once, as do repeated failures:
  // then Send comes back (the server still refuses it while a reply is live) with a note to reload.
  const status = document.getElementById('reply-status');
  const expected = form.querySelector('[name="expected_sequence"]');
  const sendButtons = [...form.querySelectorAll('button[name="action"][value="send"]')];
  if (status && status.dataset.replyPoll && expected) {
    const started = Date.now();
    const maxFailures = 6;
    let failures = 0;
    // Rewriting the live region with the same words would make screen readers repeat them.
    const words = (node) => node.textContent.replace(/\s+/g, ' ').trim();
    const sameWords = (target, html) => {
      const holder = document.createElement('div');
      holder.innerHTML = html;
      return words(holder) === words(target);
    };
    const revealed = document.getElementById('revealed-requirements');
    const giveUp = () => {
      status.removeAttribute('data-reply-live');
      status.innerHTML = '<p>Couldn\'t check for the reply. Reload the page to see it.</p>';
      sendButtons.forEach((button) => { button.disabled = false; });
    };
    const poll = () => {
      if (!status.hasAttribute('data-reply-live')) return;
      fetch(`${status.dataset.replyPoll}?after=${encodeURIComponent(expected.value)}`,
        { headers: { Accept: 'application/json' }, credentials: 'same-origin' })
        .then((response) => {
          const json = (response.headers.get('Content-Type') || '').includes('application/json');
          if (response.status >= 500) throw new Error('retry');
          if (!response.ok || response.redirected || !json) throw new Error('stop');
          return response.json();
        })
        .then((data) => {
          failures = 0;
          const transcript = document.getElementById('transcript');
          form.dispatchEvent(new Event('practice:before-turns'));
          let added = false;
          data.turns.forEach((turn) => {
            if (!document.getElementById(`turn-${turn.sequence}`)) {
              transcript.insertAdjacentHTML('beforeend', turn.html);
              added = true;
            }
          });
          if (data.latest_sequence > Number(expected.value)) expected.value = String(data.latest_sequence);
          if (!sameWords(status, data.status_html)) status.innerHTML = data.status_html;
          if (revealed && typeof data.revealed_html === 'string' && !sameWords(revealed, data.revealed_html)) {
            revealed.innerHTML = data.revealed_html;
            form.dispatchEvent(new Event('practice:requirements'));
          }
          status.toggleAttribute('data-reply-live', data.reply.live);
          sendButtons.forEach((button) => { button.disabled = data.reply.live; });
          if (added) form.dispatchEvent(new Event('practice:turns'));
          if (data.reply.live) setTimeout(poll, Date.now() - started < 30000 ? 1500 : 5000);
        })
        .catch((error) => {
          failures += 1;
          if (error.message === 'stop' || failures >= maxFailures) giveUp();
          else setTimeout(poll, Math.min(5000 * 2 ** (failures - 1), 30000));
        });
    };
    setTimeout(poll, 1500);
  }

  // The server limits UTF-8 bytes after normalizing line endings, so count the same way.
  const encoder = new TextEncoder();
  form.querySelectorAll('[data-byte-count]').forEach((output) => {
    const box = document.getElementById(output.dataset.byteCount);
    const limit = Number(output.dataset.limit);
    if (!box || !limit) return;
    const update = () => {
      const bytes = encoder.encode(box.value.replace(/\r\n?/g, '\n')).length;
      output.textContent = `${(bytes / 1024).toFixed(1)} of ${limit / 1024} KiB`;
      output.classList.toggle('is-over', bytes > limit);
      output.classList.toggle('is-near', bytes >= limit * 0.8);
    };
    box.addEventListener('input', update);
    update();
  });
})();
