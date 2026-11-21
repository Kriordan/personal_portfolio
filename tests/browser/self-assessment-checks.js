// Real forms and persistence; only one-shot transport outcomes are simulated.
(async () => {
  const frame = document.getElementById('hub');
  const result = document.getElementById('result');
  const doc = () => frame.contentDocument;
  const get = selector => doc().querySelector(selector);
  const win = () => frame.contentWindow;
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  let checks = 0;
  let step = 'optional entry';
  const check = (condition, name) => { if (!condition) throw new Error(name); checks++; };
  const wait = async (condition, name) => {
    const deadline = Date.now() + 15000;
    while (!(await condition())) {
      if (Date.now() > deadline) throw new Error(`Timed out: ${name}`);
      await delay(25);
    }
  };
  const load = action => new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error('Navigation timed out')), 15000);
    frame.addEventListener('load', () => { clearTimeout(timeout); resolve(); }, { once: true });
    action();
  });
  const visit = path => load(() => { frame.src = new URL(path, location.href).href; });
  const follow = selector => load(() => get(selector).click());
  const state = async () => (await fetch('/__assessment_state__')).json();
  const progress = async () => (await (await fetch('/__progress_state__')).json()).progress;
  const counts = async () => (await fetch('/__hub_counts__')).json();
  const form = () => get('[data-self-assessment-form]');
  const submit = () => load(() => form().requestSubmit());
  const warn = () => {
    const event = new (win().Event)('beforeunload', { cancelable: true });
    win().dispatchEvent(event);
    return event.defaultPrevented;
  };
  try {
    await wait(() => get('.is-sectioned'), 'lesson');
    const selected = new URLSearchParams(win().location.search).get('practice_session');
    const initialCounts = await counts();
    check(get('.concept-reflection-link').textContent.includes('optional'), 'entry is explicitly optional');
    check(get('.concept-mode-nav').querySelectorAll('a').length === 4, 'four core learning modes stay intact');
    check(await progress() === null, 'baseline does not require enrollment');
    await follow('.concept-reflection-link');
    await wait(() => form(), 'reflection');
    const path = win().location.pathname + win().location.search;
    check(new URLSearchParams(win().location.search).get('practice_session') === selected, 'reflection keeps selected older session');
    check((await state()).revision === 0 && await progress() === null, 'visiting reflection writes no data');
    check(form().querySelectorAll('select').length === 4, 'four independent dimensions');
    for (const select of form().querySelectorAll('select')) {
      check(select.value === 'not_assessed', 'dimension starts optional');
      check(doc().querySelector(`label[for="${select.id}"]`) && doc().getElementById(select.getAttribute('aria-describedby')), 'select has label and description');
      select.focus();
      check(doc().activeElement === select && select.tabIndex === 0, 'select is keyboard focusable');
    }
    const ids = [...doc().querySelectorAll('[id]')].map(element => element.id);
    check(new Set(ids).size === ids.length, 'unique control IDs');
    frame.style.width = '320px';
    await delay(50);
    check(doc().documentElement.scrollWidth <= frame.clientWidth + 1, 'reflection fits a narrow phone');
    frame.style.width = '1280px';
    check(!warn(), 'untouched form does not warn');
    form().elements.recognition.value = 'without_help';
    form().elements.application.value = 'not_yet';
    check(warn(), 'leaving changed choices warns');

    step = 'native save and history';
    await submit();
    check(get('[role="status"]').textContent === 'Check-in saved.', 'save confirmation is announced');
    check((await state()).revision === 1, 'one dated check-in persisted');
    check(form().elements.recognition.value === 'without_help' && form().elements.judgment.value === 'not_assessed', 'areas remain independent after reload');
    check(!get('#assessment-history').open, 'history is unobtrusive until opened');
    get('#assessment-history summary').click();
    check(get('#assessment-history').open && get('time').hasAttribute('datetime'), 'dated history is accessible');
    check(await progress() === null, 'saving baseline does not enroll');
    check(JSON.stringify(await counts()) === JSON.stringify(initialCounts), 'saving does not schedule reviews or call AI');

    step = 'stale tab recovery';
    const data = new FormData(form());
    data.set('request_id', crypto.randomUUID());
    data.set('understanding', 'with_help');
    let response = await fetch(form().action, { method: 'POST', body: data });
    check(response.ok, 'another tab saves');
    form().elements.judgment.value = 'with_help';
    await submit();
    check(get('[role="alert"]').textContent.includes('newer change'), 'stale tab explains conflict');
    check(get('[aria-label="Latest saved check-in"]') && form().elements.judgment.value === 'with_help', 'latest and unsaved choices are available together');
    check(form().querySelector('button').textContent === 'Save as a new check-in', 'conflict requires an explicit new check-in');
    check((await state()).revision === 2, 'conflict writes no snapshot');
    await submit();
    check((await state()).revision === 3, 'explicit resolution adds a dated snapshot');

    step = 'lost response';
    const requestId = form().elements.request_id.value;
    await fetch('/__assessment_failure__/after', { method: 'POST' });
    form().elements.understanding.value = 'without_help';
    await submit();
    check(get('[role="alert"]').textContent.includes('not confirmed'), 'unknown outcome does not claim success');
    check((await state()).revision === 4, 'fixture committed before response was lost');
    check(form().elements.request_id.value === requestId, 'recovery preserves exact request');
    check(warn(), 'unsaved recovery choices warn on leaving');
    await submit();
    check((await state()).revision === 4, 'retry returns original snapshot without duplicate');

    step = 'failure before save';
    await fetch('/__assessment_failure__/before', { method: 'POST' });
    form().elements.recognition.value = 'with_help';
    await submit();
    check((await state()).revision === 4, 'failed write leaves prior check-in untouched');
    await submit();
    check((await state()).revision === 5, 'retry recovers choices');

    step = 'practice continuity';
    await follow('.concept-mode-nav a:nth-child(4)');
    await wait(() => get('[data-practice-workspace].is-enhanced'), 'Build');
    check(win().location.pathname.endsWith(selected), 'return uses same older session');
    check(get('#artifacts-0-body').value === 'POST /orders — saved work', 'saved work is intact');
    await follow('.concept-reflection-link');
    check((await state()).revision === 5 && form().elements.recognition.value === 'with_help', 'practice return resumes reflection');

    step = 'no scripts';
    frame.setAttribute('sandbox', 'allow-same-origin allow-forms');
    await visit(path + '&fixture_scripts=off');
    form().elements.judgment.value = 'without_help';
    await submit();
    check((await state()).revision === 6, 'all persistence works without JavaScript');
    get('#assessment-history summary').click();
    check(get('#assessment-history').open, 'native history works without JavaScript');
    frame.removeAttribute('sandbox');

    step = 'account isolation';
    await visit('/logout');
    await visit(path);
    check(win().location.pathname.includes('login'), 'signed-out reflection redirects to login');
    await fetch('/__progress_login__/2');
    await visit('/learning/concepts/idempotency/self-assessment');
    check((await state()).entries.length === 0 && form().elements.judgment.value === 'not_assessed', 'another learner sees no reflection history');
    await fetch('/__progress_login__/1');
    await visit(path);
    check((await state()).entries.length === 6 && form().elements.judgment.value === 'without_help', 'history survives sign out and return');

    step = 'explicit deletion';
    await follow('.assessment-delete a');
    check((await state()).entries.length === 6, 'opening confirmation does not delete');
    check(get('[data-assessment-delete]').textContent.includes('Keep my check-ins'), 'deletion has a cancel path');
    const deletion = get('[data-assessment-delete]');
    const bad = new FormData(deletion);
    bad.set('csrf_token', 'wrong');
    response = await fetch(deletion.action, { method: 'POST', body: bad });
    check(response.status === 400 && (await state()).entries.length === 6, 'deletion requires CSRF');
    await load(() => deletion.requestSubmit());
    check((await state()).entries.length === 0 && form().elements.judgment.value === 'not_assessed', 'explicit deletion removes ratings');
    check(JSON.stringify(await counts()) === JSON.stringify(initialCounts) && await progress() === null, 'review, AI, artifacts and enrollment unchanged throughout');
    result.textContent = `PASS: ${checks} self-assessment browser checks`;
    document.documentElement.dataset.testResult = 'pass';
  } catch (error) {
    result.textContent = `FAIL: ${step}: ${error.message}\n${error.stack}`;
    document.documentElement.dataset.testResult = 'fail';
  }
})();
