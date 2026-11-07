// Real forms, cookie authentication and database writes; only transport failures are injected.
(async () => {
  const frame = document.getElementById('hub');
  const result = document.getElementById('result');
  const doc = () => frame.contentDocument;
  const get = selector => doc().querySelector(selector);
  const win = () => frame.contentWindow;
  const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
  let checks = 0;
  let step = 'browsing';
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
  let visits = 0;
  const visit = path => load(() => {
    // Force a document load even when only the fragment differs from this tab.
    const url = new URL(path, location.href);
    url.searchParams.set('fixture_visit', String(++visits));
    frame.src = url.href;
  });
  const follow = selector => load(() => get(selector).click());
  const state = async () => (await (await fetch('/__progress_state__')).json()).progress;
  const counts = async () => (await fetch('/__hub_counts__')).json();
  const section = async id => {
    get(`[data-lesson-link="${id}"]`).click();
    await wait(() => !get(`#${id}`).hidden, `section ${id}`);
  };
  const saved = async id => wait(async () => (await state())?.reading_section === id &&
    get('[data-position-status]')?.textContent.startsWith('Reading position saved'), `saved ${id}`);
  try {
    await wait(() => get('.is-sectioned'), 'lesson');
    const initialCounts = await counts();
    const selected = new URLSearchParams(win().location.search).get('practice_session');
    const lesson = `/learning/concepts/idempotency?practice_session=${selected}`;
    check(await state() === null, 'browsing has not enrolled the learner');
    await section('design');
    check(await state() === null, 'browsing sections writes no progress');
    check(get('[data-concept-enrollment] button').textContent === 'Start learning', 'clear explicit opt-in');
    frame.style.width = '320px';
    await delay(50);
    check(doc().documentElement.scrollWidth <= frame.clientWidth + 1, 'enrollment fits a phone');
    frame.style.width = '1280px';

    step = 'enrollment';
    await follow('[data-concept-enrollment] button');
    await wait(() => get('.is-sectioned'), 'enrolled lesson');
    await saved('design');
    check(win().location.hash === '#design', 'enrollment preserves the section being read');
    check(new URLSearchParams(win().location.search).get('practice_session') === selected, 'enrollment preserves selected practice');
    check(!get('[data-concept-enrollment]'), 'enrollment prompt disappears');
    check(get('[data-position-status]').getAttribute('role') === 'status', 'save confirmation is announced');
    const ids = [...doc().querySelectorAll('[id]')].map(element => element.id);
    check(new Set(ids).size === ids.length, 'progress and practice forms have unique IDs');
    check(JSON.stringify(await counts()) === JSON.stringify(initialCounts), 'enrollment and bookmark leave reviews and practice intact');
    await section('overview');
    await saved('overview');

    step = 'deep links and restoration';
    await visit(lesson + '#retries');
    await saved('retries');
    check(!get('#retries').hidden, 'intentional deep link wins over stored overview');
    const beforeNonLessonAnchor = await state();
    await visit(lesson + '#practice-heading');
    await wait(() => get('.is-sectioned'), 'practice anchor');
    check(get('#practice-heading').open, 'explicit non-lesson anchor stays usable');
    check(JSON.stringify(await state()) === JSON.stringify(beforeNonLessonAnchor), 'practice anchor does not reset reading position');
    await visit(lesson);
    await wait(() => get('.is-sectioned'), 'restored lesson');
    check(win().location.hash === '#retries' && !get('#retries').hidden, 'ordinary return restores saved section');
    check(JSON.stringify(await state()) === JSON.stringify(beforeNonLessonAnchor), 'restoring the same place creates no extra revision');
    await visit('/learning/');
    check(get('[data-learning-lesson]').hash === '#retries', 'home continues at saved section');
    check(get('[data-learning-continue]').href.endsWith(selected), 'home retains saved practice');
    check(doc().body.textContent.includes('Review · 4 due'), 'enrollment includes new concept questions');
    await follow('[data-learning-continue]');
    await wait(() => get('[data-practice-workspace].is-enhanced'), 'practice');
    check(get('#artifacts-0-body').value === 'POST /orders — saved work', 'saved work survives enrollment');
    await visit(lesson);
    await wait(() => get('.is-sectioned'), 'lesson');

    step = 'CSRF and stale tab';
    let form = get('[data-reading-position]');
    let data = new FormData(form);
    data.set('csrf_token', 'wrong');
    let response = await fetch(form.action, { method: 'POST', body: data, headers: { Accept: 'application/json' } });
    check(response.status === 400, 'bookmark requires valid CSRF');
    data = new FormData(form);
    data.set('section_id', 'overview');
    data.set('request_id', crypto.randomUUID());
    response = await fetch(form.action, { method: 'POST', body: data, headers: { Accept: 'application/json' } });
    check(response.ok, 'another tab saves a newer bookmark');
    await section('design');
    await wait(() => !get('[data-position-reload]').hidden, 'conflict recovery');
    check((await state()).reading_section === 'overview', 'stale tab cannot overwrite newer reading position');
    check(get('[data-position-save]').hidden, 'conflict cannot blindly retry stale state');
    await follow('[data-position-reload]');
    await wait(() => get('.is-sectioned'), 'reloaded bookmark');
    check(!get('#overview').hidden, 'reload restores the winning bookmark');

    step = 'lost response';
    const realFetch = win().fetch.bind(win());
    let drop = true;
    const requestIds = [];
    win().fetch = async (...args) => {
      requestIds.push(args[1].body.get('request_id'));
      const response = await realFetch(...args);
      if (drop) { drop = false; throw new Error('Fixture drops a committed response'); }
      return response;
    };
    await section('design');
    await wait(() => !get('[data-position-save]').hidden, 'unconfirmed-save recovery');
    const committed = await state();
    check(committed.reading_section === 'design', 'first save committed before connection loss');
    check(get('[data-position-status]').textContent.includes('not confirmed'), 'UI never claims an unconfirmed save succeeded');
    get('[data-position-save]').focus();
    get('[data-position-save]').click();
    await saved('design');
    check(doc().activeElement === get('[data-position-status]'), 'keyboard retry retains meaningful focus');
    check(requestIds.length === 2 && requestIds[0] === requestIds[1], 'retry uses the exact same request ID');
    check((await state()).revision === committed.revision, 'lost-response retry creates no second revision');

    step = 'failure before save';
    win().fetch = async () => { throw new Error('Fixture offline'); };
    await section('retries');
    await wait(() => !get('[data-position-save]').hidden, 'offline retry');
    check((await state()).reading_section === 'design', 'offline navigation leaves saved position intact');
    win().fetch = realFetch;
    get('[data-position-save]').click();
    await saved('retries');

    step = 'quick navigation';
    let release;
    let waiting = false;
    const gate = new Promise(resolve => { release = resolve; });
    let hold = true;
    win().fetch = async (...args) => {
      const response = await realFetch(...args);
      if (hold) { hold = false; waiting = true; await gate; }
      return response;
    };
    await section('overview');
    await wait(() => waiting, 'held first response');
    await section('design');
    release();
    await saved('design');
    check(get('[data-position-status]').textContent.includes(get('#lesson-heading-design').textContent), 'latest navigation wins within one tab');
    frame.style.width = '320px';
    await delay(50);
    check(doc().documentElement.scrollWidth <= frame.clientWidth + 1, 'saved position fits a phone');

    step = 'native forms';
    frame.setAttribute('sandbox', 'allow-same-origin allow-forms');
    await visit(lesson + '&fixture_scripts=off');
    form = get('[data-reading-position]');
    check(!get('.is-sectioned') && !get('[data-position-picker]').hidden, 'native position selector works without scripts');
    form.elements.section_id.value = 'overview';
    await load(() => form.requestSubmit());
    check(win().location.hash === '#overview', 'native save returns to the chosen section');
    check((await state()).reading_section === 'overview', 'native save is durable');
    frame.removeAttribute('sandbox');

    step = 'sign out, switch account, return';
    await visit('/logout');
    await visit(lesson);
    check(win().location.pathname.includes('login'), 'signed-out lesson requires login');
    await fetch('/__progress_login__/2');
    await visit('/learning/concepts/idempotency');
    await wait(() => get('.is-sectioned'), 'other learner');
    check(await state() === null && get('[data-concept-enrollment]'), 'another account sees no enrollment or bookmark');
    check(!get('#overview').hidden, 'another account starts at the introduction');
    await fetch('/__progress_login__/1');
    await visit(lesson);
    await wait(() => get('.is-sectioned'), 'returning learner');
    check((await state()).reading_section === 'overview', 'original bookmark survives sign out and return');
    check(JSON.stringify(await counts()) === JSON.stringify(initialCounts), 'review scheduling, conversation and artifacts unchanged throughout');
    result.textContent = `PASS: ${checks} concept progress browser checks`;
    document.documentElement.dataset.testResult = 'pass';
  } catch (error) {
    result.textContent = `FAIL: ${step}: ${error.message}\n${error.stack}`;
    document.documentElement.dataset.testResult = 'fail';
  }
})();
