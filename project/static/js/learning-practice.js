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
    };
    box.addEventListener('input', update);
    update();
  });
})();
