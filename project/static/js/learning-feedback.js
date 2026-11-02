/* Read-only status polling; a lost request is never resubmitted automatically. */
(() => {
  'use strict';
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
        // Server-rendered template: all learner/provider text is HTML-escaped.
        panel.innerHTML = result.html;
        announcement.textContent = 'Feedback status updated.';
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
    if (target?.closest('details')) target.closest('details').open = true;
  });
  if (live()) setTimeout(poll, 1000);
})();
