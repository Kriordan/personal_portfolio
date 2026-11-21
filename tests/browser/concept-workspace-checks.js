// Real Flask pages, native forms and persisted session data. See the browser fixture.
(async () => {
  const frame = document.getElementById('hub');
  const result = document.getElementById('result');
  const doc = () => frame.contentDocument;
  const get = (selector) => doc().querySelector(selector);
  let checks = 0;
  let step = 'lesson';
  const check = (condition, name) => { if (!condition) throw new Error(`${step}: ${name}`); checks += 1; };
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const wait = async (condition, name) => {
    const deadline = Date.now() + 15000;
    while (!condition()) {
      if (Date.now() > deadline) throw new Error(`${step}: timed out waiting for ${name}`);
      await delay(25);
    }
  };
  const load = async (action) => new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`${step}: navigation timed out`)), 15000);
    frame.addEventListener('load', () => { clearTimeout(timeout); resolve(); }, { once: true });
    action();
  });
  const click = (selector) => { get(selector).focus(); get(selector).click(); };
  const follow = (selector) => load(() => click(selector));
  const mode = (name) => [...doc().querySelectorAll('.concept-mode-nav a')].find((a) => a.textContent.trim().startsWith(name));
  const openMode = (name) => load(() => mode(name).click());
  const counts = async () => (await fetch('/__hub_counts__')).json();
  const fill = (selector, value) => {
    get(selector).value = value;
    get(selector).dispatchEvent(new frame.contentWindow.Event('input', { bubbles: true }));
  };
  const noOverflow = () => doc().documentElement.scrollWidth <= frame.clientWidth + 1;
  const leaving = () => {
    const event = new frame.contentWindow.Event('beforeunload', { cancelable: true });
    frame.contentWindow.dispatchEvent(event);
    return event.defaultPrevented;
  };
  try {
    await wait(() => get('.is-sectioned'), 'lesson enhancement');
    const selected = new URLSearchParams(frame.contentWindow.location.search).get('practice_session');
    const original = await counts();
    const lessonURL = frame.contentWindow.location.href;
    check(original.sessions === 2, 'fixture includes another session to detect accidental switching');
    check(get('h1').textContent === 'Idempotency' && doc().querySelectorAll('h1').length === 1, 'shared concept identity');
    check(mode('Learn').getAttribute('aria-current') === 'page', 'Learn is current');
    check(['Learn', 'Review', 'Discuss', 'Build'].every((name) => mode(name)?.href), 'all four modes have native links');
    check(doc().querySelectorAll('[data-lesson-section]:not([hidden])').length === 1, 'one readable section at a time');
    check(!get('#overview').hidden, 'lesson starts at its introduction');
    ['HIDDEN_SENTINEL', 'HINT_SENTINEL', 'EVALUATOR_SENTINEL', 'INSTRUCTION_SENTINEL', 'reference_reasoning'].forEach(
      (secret) => check(!doc().documentElement.outerHTML.includes(secret), `private reference absent: ${secret}`));

    step = 'sections and retry lab';
    click('[data-lesson-link="retries"]');
    await wait(() => !get('#retries').hidden, 'retry section');
    check(frame.contentWindow.location.hash === '#retries', 'section has a deep link');
    check(doc().activeElement.id === 'lesson-heading-retries', 'section heading receives keyboard focus');
    check(get('[data-retry-lab]').closest('[data-lesson-section]').id === 'retries', 'simulation sits beside its explanation');
    click('#retry-next'); click('#retry-next');
    check(get('#retry-count').textContent === '1', 'retry simulation still works');
    click('[data-lesson-link="overview"]');
    await wait(() => !get('#overview').hidden, 'overview');
    click('[data-lesson-link="retries"]');
    await wait(() => !get('#retries').hidden, 'retry section again');
    check(get('#retry-count').textContent === '1', 'section navigation preserves the in-page simulation');
    check(JSON.stringify(await counts()) === JSON.stringify(original), 'reading and section changes do not write progress');

    step = 'review and remediation';
    await openMode('Review');
    check(mode('Review').getAttribute('aria-current') === 'page', 'Review is current');
    check(new URLSearchParams(frame.contentWindow.location.search).get('practice_session') === selected, 'review keeps selected session');
    check(!get('#concept-answer'), 'answer is absent until explicitly revealed');
    await follow('button:not([name])');
    check(get('#concept-answer'), 'explicit reveal shows the comparison');
    check(get('input[name="practice_session"]').value === selected, 'review form carries session context');
    const remediation = get('.concept-answer a').getAttribute('href');
    await follow('.concept-answer a');
    await wait(() => get('.is-sectioned'), 'remediation lesson');
    const target = remediation.split('#')[1];
    check(!get(`#${target}`).hidden, 'remediation opens the matching lesson section');
    check(new URLSearchParams(frame.contentWindow.location.search).get('practice_session') === selected, 'remediation retains session');
    check(JSON.stringify(await counts()) === JSON.stringify(original), 'reveal and remediation do not change progress');

    step = 'Build, saved work and conversation';
    await openMode('Build');
    await wait(() => get('[data-practice-workspace].is-enhanced'), 'practice enhancement');
    check(frame.contentWindow.location.pathname.endsWith(selected), 'Build opens the selected older session');
    check(get('[data-practice-workspace]').dataset.view === 'build', 'Build link opens Build');
    check(get('h1').textContent === 'Idempotency', 'practice has the same concept header');
    click('[data-work-target="artifact-api"]');
    check(get('#artifacts-0-body').value === 'POST /orders — saved work', 'original confirmed artifact is present');
    fill('#artifacts-0-body', 'POST /orders — my evolving design');
    check(leaving(), 'unsaved work still warns before leaving for Learn or Review');
    await follow('button[value="save"]:not(.practice-default-action)');
    await wait(() => get('[data-practice-workspace].is-enhanced'), 'saved workspace');
    check(!leaving(), 'confirmed save clears the leave warning');
    await openMode('Learn');
    await openMode('Discuss');
    await wait(() => get('[data-practice-workspace].is-enhanced'), 'discussion enhancement');
    check(frame.contentWindow.location.pathname.endsWith(selected), 'Discuss returns to the selected session');
    check(get('[data-practice-workspace]').dataset.view === 'discuss', 'Discuss link opens Discuss');
    check(get('#artifacts-0-body').value === 'POST /orders — my evolving design', 'saved artifact survives Learn round trip');
    check(get('#transcript').textContent.includes('How would you begin scoping'), 'original interviewer conversation remains');
    fill('#message', 'I would clarify what the client knows after a timeout.');
    await follow('button[value="send"]');
    await wait(() => get('[data-practice-workspace].is-enhanced'), 'sent workspace');
    check(get('#transcript').textContent.includes('I would clarify what the client knows'), 'learner turn is saved in this conversation');
    const saved = await counts();
    check(saved.artifacts === original.artifacts + 1 && saved.turns === original.turns + 1, 'one artifact revision and one turn saved');

    step = 'mobile lesson';
    await openMode('Learn');
    for (const width of [390, 320]) {
      frame.style.width = `${width}px`;
      await delay(50);
      check(noOverflow(), `${width}-pixel lesson has no horizontal overflow`);
      check(get('#lesson-section').getClientRects().length > 0, 'phone section picker is visible');
      check(get('.lesson-section-nav').getClientRects().length === 0, 'phone avoids a second section menu');
    }
    get('#lesson-section').value = 'design';
    get('#lesson-section').dispatchEvent(new frame.contentWindow.Event('change', { bubbles: true }));
    await wait(() => !get('#design').hidden, 'phone section selection');
    check(frame.contentWindow.location.hash === '#design', 'phone section picker updates the deep link');

    step = 'complete review and return to practice';
    await openMode('Review');
    for (let number = 0; number < 4; number += 1) {
      check(!get('#concept-answer'), 'each next question starts unrevealed');
      await follow('button:not([name])');
      check(noOverflow(), 'revealed review and rating controls fit a phone');
      check(get('button[name="rating"]').getBoundingClientRect().height >= 44, 'rating target is touch sized');
      await follow('button[name="rating"][value="4"]');
      check(new URLSearchParams(frame.contentWindow.location.search).get('practice_session') === selected, 'rating redirect retains selected session');
    }
    check(get('.concept-review-complete h2').textContent === 'No questions due right now', 'review has a clear completion state');
    await follow('.concept-review-complete .button');
    await wait(() => get('[data-practice-workspace].is-enhanced'), 'return to conversation');
    check(frame.contentWindow.location.pathname.endsWith(selected), 'completion returns to the same conversation');
    check(get('#transcript').textContent.includes('I would clarify what the client knows'), 'saved conversation survives review');
    check(get('#artifacts-0-body').value === 'POST /orders — my evolving design', 'saved artifact survives review');
    const completed = await counts();
    check(completed.ratings === 4 && completed.receipts === 4, 'four durable concept ratings');
    check(completed.sessions === original.sessions && completed.artifacts === saved.artifacts, 'mode navigation creates no extra sessions or artifact revisions');

    step = 'without scripts';
    frame.setAttribute('sandbox', 'allow-same-origin allow-forms');
    await load(() => { frame.src = lessonURL + '&fixture_scripts=off#design'; });
    check(!get('.is-sectioned'), 'fixture blocks lesson scripts');
    check(doc().querySelectorAll('[data-lesson-section]').length === 3, 'full lesson remains available without scripts');
    check([...doc().querySelectorAll('[data-lesson-section]')].every((section) => !section.hidden), 'no section is hidden without enhancement');
    check(mode('Review').href.includes(selected) && mode('Build').href.includes(selected), 'native navigation preserves context without scripts');
    result.textContent = `PASS: ${checks} concept workspace browser checks`;
    document.documentElement.dataset.testResult = 'pass';
  } catch (error) {
    result.textContent = `FAIL: ${step}: ${error.message}\n${error.stack}`;
    document.documentElement.dataset.testResult = 'fail';
  }
})();
