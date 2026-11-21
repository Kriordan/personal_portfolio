/* Read-only status polling; a lost request is never resubmitted automatically. */
(() => {
  'use strict';
  // Notes stay in the form. Warn before navigation discards any unsaved response,
  // including another finding's note when one response is submitted.
  const saved = new WeakMap();
  let submitting = null;
  const responses = () => [...document.querySelectorAll('[data-annotation-form]')];
  const value = form => JSON.stringify([...new FormData(form)]);
  function remember() {
    responses().forEach(form => {
      if (!saved.has(form)) saved.set(form, form.dataset.unsaved === 'true' ? null : value(form));
    });
  }
  remember();
  document.addEventListener('submit', event => {
    submitting = event.target.matches('[data-annotation-form]') ? event.target : null;
  });
  window.addEventListener('beforeunload', event => {
    // Exempt this POST only for this navigation. If another draft prompts the
    // learner to cancel leaving, the submitted form is still unsaved too.
    const sending = submitting;
    submitting = null;
    if (responses().some(form => form !== sending && saved.get(form) !== value(form))) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  const panel = document.querySelector('[data-feedback-panel]');
  if (!panel) return;
  const announcement = document.querySelector('[data-feedback-announcement]');
  let failures = 0;
  const live = () => panel.querySelector('[data-feedback-live="true"]');
  async function poll() {
    if (!live()) return;
    try {
      const response = await fetch(panel.dataset.statusUrl, { credentials: 'same-origin', cache: 'no-store',
        headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(15000) });
      if (!response.ok || !response.headers.get('content-type')?.includes('application/json')) throw new Error('status');
      const result = await response.json();
      if (typeof result.html !== 'string' || typeof result.live !== 'boolean') throw new Error('status');
      failures = 0;
      if (!result.live) {
        const replacingFocus = panel.contains(document.activeElement);
        // Server-rendered template: all learner/provider text is HTML-escaped.
        panel.innerHTML = result.html;
        remember();
        announcement.textContent = 'Feedback status updated.';
        // A focused Refresh status link disappears when feedback arrives. Keep
        // that reader at the result; leave focus elsewhere on the page alone.
        if (replacingFocus) panel.querySelector('#feedback-heading')?.focus();
        return;
      }
    } catch (_) {
      if (++failures >= 6) {
        announcement.textContent = 'Status updates stopped. Your request is saved; use Refresh status to check again.';
        return;
      }
    }
    setTimeout(poll, 2000);
  }
  panel.addEventListener('click', event => {
    const link = event.target.closest('[data-snapshot-note]');
    if (!link) return;
    const target = document.getElementById(link.hash.slice(1));
    if (target?.closest('details')) {
      target.closest('details').open = true;
      target.tabIndex = -1;
      target.focus({ preventScroll: true });
    }
  });
  if (live()) setTimeout(poll, 1000);
})();
