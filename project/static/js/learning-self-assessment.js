/* Native forms own persistence. Warn when leaving an unsaved reflection. */
(() => {
  'use strict';
  const form = document.querySelector('[data-self-assessment-form]');
  if (!form) return;
  const value = () => JSON.stringify([...new FormData(form)]);
  const initial = form.dataset.unsaved === 'true' ? null : value();
  let submitting = false;
  form.addEventListener('submit', () => { submitting = true; });
  window.addEventListener('beforeunload', event => {
    const sending = submitting;
    submitting = false;
    if (!sending && value() !== initial) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  if (window.location.hash === '#assessment-history') {
    const history = document.getElementById('assessment-history');
    if (history) history.open = true;
  }
})();
