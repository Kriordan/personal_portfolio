(() => {
  // This lesson subset has no images, embeds, styles, or executable HTML.
  document.querySelectorAll('[data-concept-markdown]').forEach((element) => {
    const source = element.textContent;
    if (!window.marked?.parse || !window.DOMPurify?.sanitize) return;
    element.innerHTML = window.DOMPurify.sanitize(window.marked.parse(source), {
      ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li', 'blockquote', 'h3', 'h4', 'a', 'hr'],
      ALLOWED_ATTR: ['href', 'title'], ALLOW_DATA_ATTR: false,
    });
    element.classList.add('is-rendered');
    element.querySelectorAll('a').forEach((link) => link.setAttribute('rel', 'noreferrer'));
  });

  // Section links remain ordinary anchors. Enhancement focuses one section at a
  // time; with scripts blocked the entire lesson and navigation remain readable.
  const lesson = document.querySelector('[data-concept-lesson]');
  const sections = lesson ? [...lesson.querySelectorAll('[data-lesson-section]')] : [];
  const picker = lesson?.querySelector('#lesson-section');
  const hashTarget = () => {
    try { return document.getElementById(decodeURIComponent(location.hash.slice(1))); }
    catch { return null; }
  };
  const revealSection = () => {
    const target = hashTarget();
    const section = target?.closest('[data-lesson-section]') || sections[0];
    if (section) {
      sections.forEach((item) => { item.hidden = item !== section; });
      lesson.querySelectorAll('[data-lesson-link]').forEach((link) => {
        if (link.dataset.lessonLink === section.id) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
      picker.value = section.id;
    }
    if (target?.matches('details')) target.open = true;
  };
  if (sections.length) {
    lesson.classList.add('is-sectioned');
    lesson.querySelector('[data-lesson-picker]').hidden = false;
    picker.addEventListener('change', () => { location.hash = picker.value; });
  }
  revealSection();
  window.addEventListener('hashchange', () => {
    revealSection();
    const target = hashTarget();
    const heading = target?.matches('[data-lesson-section]') ? target.querySelector('h2') : null;
    if (heading) {
      heading.focus({ preventScroll: true });
      heading.scrollIntoView({ block: 'start' });
    }
  });

  const lab = document.querySelector('[data-retry-lab]');
  if (!lab) return;
  const failure = document.getElementById('retry-failure');
  const reuse = document.getElementById('retry-key');
  const next = document.getElementById('retry-next');
  const reset = document.getElementById('retry-reset');
  const list = document.getElementById('retry-steps');
  const status = document.getElementById('retry-status');
  const count = document.getElementById('retry-count');
  let step = 0;

  const events = () => {
    const committed = failure.value !== 'before';
    return [
      ['Client → API: send the order with key A.', 0],
      committed
        ? ['API → Database: commit one order and its receipt together.', 1]
        : ['API crashes before commit. Database rolls back; there is no committed order or receipt.', 0],
      failure.value === 'success'
        ? ['API → Client: success arrives. The client knows the order exists; no retry is needed.', 1]
        : ['Client times out. From the timeout alone, it cannot tell whether the order committed.', committed ? 1 : 0],
      [reuse.checked ? 'Client → API: retry the same operation with key A.' : 'Client → API: resend with a new key B. This identifies a new operation.', committed ? 1 : 0],
      committed && reuse.checked
        ? ['API → Client: return the recorded result for A. No second order is created.', 1]
        : ['API → Database: create an order and receipt for this key, then return success.', committed ? 2 : 1],
    ];
  };

  const render = () => {
    const trace = events();
    list.replaceChildren(...trace.map(([description], index) => {
      const item = document.createElement('li');
      item.textContent = description;
      if (index === step - 1) item.setAttribute('aria-current', 'step');
      item.classList.toggle('is-pending', index >= step);
      return item;
    }));
    count.textContent = String(step ? trace[step - 1][1] : 0);
    status.textContent = step ? `Step ${step} of ${trace.length}. ${trace[step - 1][0]}` : 'Ready. Follow the first attempt, then its retry.';
    if (step === trace.length && Number(count.textContent) === 2) {
      status.textContent += ' Two orders: changing the key removed the duplicate protection.';
    }
    // Disabling the focused button drops keyboard focus onto the document.
    const finishedHere = step === trace.length && document.activeElement === next;
    next.disabled = step === trace.length;
    if (finishedHere) reset.focus();
  };
  const restart = () => { step = 0; render(); };
  [failure, reuse, next, reset].forEach((control) => { control.disabled = false; });
  next.addEventListener('click', () => { step = Math.min(step + 1, events().length); render(); });
  reset.addEventListener('click', restart);
  failure.addEventListener('change', restart);
  reuse.addEventListener('change', restart);
  render();
})();
