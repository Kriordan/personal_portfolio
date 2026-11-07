(() => {
  const form = document.querySelector('[data-reading-position]');
  if (!form) return;
  const status = form.querySelector('[data-position-status]');
  const button = form.querySelector('[data-position-save]');
  const reload = form.querySelector('[data-position-reload]');
  const field = form.elements.section_id;
  let savedSection = form.dataset.savedSection;
  let savedVersion = form.dataset.savedVersion;
  let desired = null;
  let pending = null;
  let busy = false;
  let blocked = false;
  form.querySelector('[data-position-picker]').hidden = true;
  button.hidden = true;

  const save = async () => {
    if (busy || blocked || !desired) return;
    if (!pending) {
      if (desired === savedSection && form.elements.content_version.value === savedVersion) return;
      field.value = desired;
      form.elements.request_id.value = crypto.randomUUID();
      pending = new FormData(form); // Retry the same payload, even if navigation continues.
    }
    busy = true;
    // A keyboard retry must not strand focus when its button is hidden.
    if (document.activeElement === button) status.focus({ preventScroll: true });
    button.hidden = true;
    status.textContent = 'Saving reading position…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      const response = await fetch(form.action, { method: 'POST', body: pending,
        credentials: 'same-origin', headers: { Accept: 'application/json' },
        signal: controller.signal, keepalive: true });
      if (response.status === 409) {
        blocked = true;
        reload.hidden = false;
        status.textContent = 'Your reading position changed in another tab. Reload the saved position before saving again.';
        return;
      }
      if (!response.ok || response.redirected) throw new Error('Unconfirmed save');
      const result = (await response.json()).progress;
      if (!result || !Number.isInteger(result.revision) || result.reading_section !== pending.get('section_id') ||
          String(result.reading_version) !== pending.get('content_version')) throw new Error('Unconfirmed save');
      form.elements.expected_revision.value = String(result.revision);
      savedSection = result.reading_section;
      savedVersion = String(result.reading_version);
      pending = null;
      const title = [...field.options].find(option => option.value === savedSection)?.textContent || 'this section';
      status.textContent = `Reading position saved · ${title}`;
    } catch {
      status.textContent = 'Reading position not confirmed. Your lesson is still available. Retry saving your place.';
      button.textContent = 'Retry saving position';
      button.hidden = false;
    } finally {
      clearTimeout(timeout);
      busy = false;
    }
    if (!pending && !blocked && desired !== savedSection) save();
  };
  document.addEventListener('learning:section', event => {
    desired = event.detail.sectionId;
    if (!pending) save();
  });
  form.addEventListener('submit', event => { event.preventDefault(); save(); });
})();
