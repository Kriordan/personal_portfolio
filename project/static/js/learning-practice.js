(() => {
  // Progressive enhancement only: saving, conflicts and recovery all work without it.
  const form = document.querySelector('[data-practice-form]');
  if (!form) return;
  const fields = [...form.querySelectorAll('textarea, select')];
  const initial = new Map(fields.map((field) => [field, field.value]));
  // A re-rendered page (rejected or failed save) holds unsaved text from the start.
  const unsavedOnLoad = form.hasAttribute('data-unsaved');
  let submitting = false;
  const dirty = () => unsavedOnLoad || fields.some((field) => field.value !== initial.get(field));

  window.addEventListener('beforeunload', (event) => {
    if (submitting || !dirty()) return;
    event.preventDefault();
    event.returnValue = '';
  });
  form.addEventListener('submit', () => { submitting = true; });

  // The server limit is UTF-8 bytes after normalizing line endings, so count the same way.
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

  document.getElementById('practice-alert')?.focus();
})();
