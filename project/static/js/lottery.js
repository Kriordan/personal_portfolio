(() => {
  'use strict';
  const form = document.getElementById('lottery-filters');
  if (!form) return;
  const key = 'scratch-off-preferences-v1';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(key) || '{}'); } catch (_) { /* Storage is optional. */ }
  if (!location.search && saved.state && ['ny', 'ct'].includes(saved.state)) {
    const params = new URLSearchParams({state: saved.state, target: saved.target || '1000', basis: saved.basis || 'ticket'});
    if (Array.isArray(saved[saved.state])) {
      params.set('prices_set', '1');
      saved[saved.state].forEach(p => params.append('price', p));
    }
    location.replace(`${location.pathname}?${params}`);
    return;
  }
  const initialState = form.elements.state.value;
  const persist = () => {
    saved.state = form.elements.state.value;
    saved.target = form.querySelector('select[name=target]').value;
    saved.basis = form.elements.basis.value;
    saved[initialState] = Array.from(form.querySelectorAll('[name=price]:checked'), e => e.value);
    try { localStorage.setItem(key, JSON.stringify(saved)); } catch (_) { /* Filters still work. */ }
  };
  // Persist query-string selections as well as form submissions.
  persist();
  form.addEventListener('submit', persist);
  form.querySelectorAll('[data-target]').forEach(button => button.addEventListener('click', () => {
    form.querySelector('select[name=target]').value = button.dataset.target;
    button.removeAttribute('name');
  }));
  form.querySelectorAll('[name=state]').forEach(radio => radio.addEventListener('change', () => {
    persist();
    const params = new URLSearchParams({state: radio.value, target: saved.target, basis: saved.basis});
    if (Array.isArray(saved[radio.value])) {
      params.set('prices_set', '1'); saved[radio.value].forEach(p => params.append('price', p));
    }
    location.assign(`${location.pathname}?${params}`);
  }));
  document.querySelectorAll('a[href^="#game-"]').forEach(link => link.addEventListener('click', () => {
    const detail = document.getElementById(link.hash.slice(1));
    if (detail) detail.open = true;
  }));
})();
