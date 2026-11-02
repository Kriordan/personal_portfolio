// Served only by test_practice_browser.py. Drive real same-origin documents and
// native submissions; the fixture controls failures and steps a fake AI worker.
(async () => {
  let checks = 0;
  let step = 'initial load';
  const result = document.getElementById('result');
  const frame = document.getElementById('workspace');
  const doc = (target = frame) => target.contentDocument;
  const get = (selector, target = frame) => doc(target).querySelector(selector);
  const check = (condition, name) => { if (!condition) throw new Error(`${step}: ${name}`); checks += 1; };
  const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const wait = async (predicate, name) => {
    const deadline = Date.now() + 20000;
    while (!predicate()) {
      if (Date.now() > deadline) throw new Error(`${step}: timed out waiting for ${name}`);
      await delay(25);
    }
  };
  const ready = (target = frame) => wait(() => get('.is-enhanced', target), 'workspace enhancement');
  const load = async (target, action) => {
    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error(`${step}: navigation timed out`)), 20000);
      target.addEventListener('load', () => { clearTimeout(timeout); resolve(); }, { once: true });
      action();
    });
  };
  const click = (selector, target = frame) => {
    const element = get(selector, target);
    element.focus();
    element.click();
  };
  const fill = (selector, value, target = frame) => {
    const field = get(selector, target);
    field.focus();
    field.value = value;
    field.dispatchEvent(new target.contentWindow.Event('input', { bubbles: true }));
  };
  const submit = (action, target = frame) => load(target, () => click(`button[name="action"][value="${action}"]:not(.practice-default-action)`, target));
  const view = (name, target = frame) => click(`[data-practice-view="${name}"]`, target);
  const work = (name, target = frame) => click(`[data-work-target="${name}"]`, target);
  const visible = (selector, target = frame) => !!get(selector, target)?.getClientRects().length;
  const leaving = (target = frame) => {
    const event = new target.contentWindow.Event('beforeunload', { cancelable: true });
    target.contentWindow.dispatchEvent(event);
    return event.defaultPrevented;
  };
  const control = async (values = {}) => (await fetch('/__browser_control__', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(values),
  })).json();
  const key = () => `learning-practice-ui:${frame.contentWindow.location.pathname}`;
  try {
    await ready();
    const sessionURL = frame.contentWindow.location.pathname;
    const original = await control();
    check(get('[data-view-tabs]').getAttribute('role') === 'tablist', 'view tabs expose their semantics');
    check(get('[data-work-tabs]').getAttribute('role') === 'tablist', 'work tabs expose their semantics');
    check(doc().querySelectorAll('[data-work-panel]:not([hidden])').length === 1, 'one work panel is shown');
    check(get('#requirements').hidden === false, 'a new session starts with its brief');
    check(get('.learning-shell-header') && !get('.Header'), 'workspace uses compact navigation');
    const html = doc().documentElement.outerHTML;
    ['HIDDEN_SENTINEL', 'HINT_SENTINEL', 'INSTRUCTION_SENTINEL', 'EVALUATOR_SENTINEL',
      'clarification_cues', 'reference_reasoning', 'permitted_hints', 'hotjar', 'googletagmanager'].forEach(
      (secret) => check(!html.includes(secret), `private material absent: ${secret}`));

    step = 'tabs and drafts';
    view('build');
    work('artifact-api');
    fill('#artifacts-0-body', 'POST /orders — browser draft');
    const api = get('#artifacts-0-body');
    api.setSelectionRange(5, 11);
    work('artifact-schema');
    fill('#artifacts-1-body', 'CREATE TABLE orders (id bigint);');
    view('discuss');
    fill('#message', 'Who owns the key?');
    work('artifact-api');
    check(api.value === 'POST /orders — browser draft' && api.selectionStart === 5, 'switches retain artifact text and selection');
    check(get('#artifacts-1-body').value.includes('CREATE TABLE'), 'hidden draft stays in the form');
    check(get('#message').value === 'Who owns the key?', 'switches retain the unsent message');
    check(leaving(), 'unsaved drafts still guard navigation');
    check(get('#practice-save-state').textContent === 'Unsaved work · unsent message', 'save indicator describes unconfirmed work');
    const stored = frame.contentWindow.localStorage.getItem(key());
    check(!stored.includes('POST /orders') && !stored.includes('Who owns'), 'view storage contains no learner text');
    check((await control()).learner_turns === original.learner_turns, 'tabs never send messages');
    check(get('#artifacts-0-body').getBoundingClientRect().bottom < 720, 'active artifact is within the desktop viewport');
    check(get('#message').getBoundingClientRect().bottom < 720, 'composer is within the desktop viewport');
    check(get('button[value="send"]').getBoundingClientRect().bottom <= get('.practice-composer').getBoundingClientRect().bottom,
      `Send is not clipped inside the composer (send: ${get('button[value="send"]').getBoundingClientRect().bottom}, composer: ${get('.practice-composer').getBoundingClientRect().bottom})`);
    const schemaTab = get('[data-work-target="artifact-schema"]');
    schemaTab.focus();
    schemaTab.dispatchEvent(new frame.contentWindow.KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true }));
    check(doc().activeElement.dataset.workTarget === 'artifact-algorithm', 'arrow keys switch work tabs and focus');
    check(get('#artifact-algorithm').hidden === false, 'keyboard-selected panel is exposed');
    work('session-brief');
    check(doc().querySelectorAll('[data-blank-note]:not([hidden])').length === 0, 'blank note forms are initially tucked away');
    click('[data-add-note]');
    check(doc().activeElement.id === 'brief-0-text', 'adding a note focuses its field');
    fill('#brief-0-text', 'Assume retries preserve their key.');
    work('artifact-api');

    step = 'native send and polling';
    await submit('send');
    await ready();
    check(get('#message').value === '', 'successful send clears only the submitted message');
    check(doc().activeElement.id === 'message', 'successful send restores composer focus');
    check(frame.contentWindow.scrollY < 40, 'send leaves the compact workspace in view');
    check(get('#artifact-api').hidden === false, 'send restores the active artifact');
    check(get('#artifacts-0-body').value === 'POST /orders — browser draft', 'send saves the active artifact');
    check(get('#artifacts-1-body').value.includes('CREATE TABLE'), 'send also saves hidden artifacts');
    check(get('#brief-0-text').value === 'Assume retries preserve their key.', 'send saves hidden notes');
    check(get('button[value="send"]').disabled, 'pending reply still gates another send');
    check(get('button[value="send"]').getBoundingClientRect().bottom <= get('.practice-composer').getBoundingClientRect().bottom,
      'pending reply status leaves the composer action visible');
    check((await control()).learner_turns === original.learner_turns + 1, 'exactly one learner turn was saved');
    const transcript = get('#transcript');
    check(transcript.scrollHeight - transcript.clientHeight - transcript.scrollTop < 32, 'send shows the latest exchange');
    fill('#message', 'Drafting while the interviewer thinks.');
    transcript.scrollTop = 0;
    transcript.dispatchEvent(new frame.contentWindow.Event('scroll'));
    await control({ reply: true });
    await wait(() => !get('button[value="send"]').disabled, 'interviewer reply');
    check(get('#transcript').scrollTop < 10, 'reply does not drag a reader away from older turns');
    check(!get('[data-new-messages]').hidden, 'new reply offers a jump to the latest messages');
    check(doc().activeElement.id === 'message', 'polling does not steal focus');
    check(get('#message').value === 'Drafting while the interviewer thinks.', 'polling preserves typing');
    click('[data-new-messages]');
    check(get('[data-new-messages]').hidden, 'jump control clears at the latest message');
    check(get('#transcript').scrollHeight - get('#transcript').clientHeight - get('#transcript').scrollTop < 32,
      'jump reaches the newest reply');

    step = 'save without sending, pause, and resume';
    work('artifact-algorithm');
    fill('#artifacts-2-body', 'lookup(key)\ncreate_order()\nremember(key)');
    get('#artifacts-2-body').setSelectionRange(3, 8);
    await submit('save');
    await ready();
    check(get('#message').value === 'Drafting while the interviewer thinks.', 'saving keeps the unsent message');
    check(doc().activeElement.id === 'artifacts-2-body', 'saving returns to the edited artifact');
    check(get('#artifacts-2-body').selectionStart === 3, 'saving restores the editing selection');
    check(leaving(), 'saved artifacts do not make an unsent message safe to discard');
    check((await control()).learner_turns === original.learner_turns + 1, 'Save does not send');
    work('session-brief');
    click('[data-add-note]');
    fill('#brief-1-text', 'Keep this decision after removing an earlier note.');
    await submit('save');
    await ready();
    click('#brief-0-remove');
    fill('#brief-1-text', 'This is the surviving decision.');
    get('#brief-1-text').setSelectionRange(4, 10);
    await submit('save');
    await ready();
    check(doc().activeElement.value === 'This is the surviving decision.', 'saving restores the same note after its form index changes');
    check(doc().activeElement.selectionStart === 4, 'note selection survives removing an earlier entry');
    work('artifact-algorithm');
    fill('#message', '');
    view('build');
    await submit('pause');
    await ready();
    check(get('.practice-paused') && get('button[value="resume"]'), 'pause keeps its existing semantics');
    await load(frame, () => click('.practice-views a[href*="/concepts/idempotency?practice_session="]'));
    check(get('.concept-study'), 'Learn still opens the existing lesson');
    await load(frame, () => { frame.src = sessionURL; });
    await ready();
    check(get('[data-practice-workspace]').dataset.view === 'build', 'resume remembers the view without URL parameters');
    check(!get('#artifact-algorithm').hidden && get('#artifacts-2-body').value.includes('remember'), 'resume restores artifact selection and saved work');
    await submit('resume');
    await ready();
    check(!get('.practice-paused'), 'Resume reopens the same session');

    step = 'conflict in a hidden tab';
    const other = document.createElement('iframe');
    other.style.cssText = 'width:1280px;height:720px;border:0';
    document.body.appendChild(other);
    await load(other, () => { other.src = sessionURL; });
    await ready(other);
    work('artifact-api', other);
    fill('#artifacts-0-body', 'Another tab saved this API.', other);
    await submit('save', other);
    work('artifact-api');
    fill('#artifacts-0-body', 'My conflicting API draft.');
    work('artifact-schema');
    fill('#artifacts-1-body', 'My independent schema draft.');
    fill('#message', 'Keep this message through the conflict.');
    await submit('send');
    await ready();
    check(doc().activeElement.id === 'practice-alert', 'conflict focuses its error summary');
    check(!get('#artifact-api').hidden && get('#artifact-api .practice-conflict'), 'hidden conflicting artifact is automatically revealed');
    check(get('#artifacts-0-body').value === 'My conflicting API draft.', 'conflict preserves the local artifact');
    check(get('#artifacts-1-body').value === 'My independent schema draft.', 'conflict preserves other hidden work');
    check(get('#message').value === 'Keep this message through the conflict.', 'conflict preserves the message');
    check((await control()).learner_turns === original.learner_turns + 1, 'conflict does not create a turn');
    work('session-brief');
    click('#practice-alert a[href="#artifact-api"]');
    check(!get('#artifact-api').hidden, 'error-summary links reveal hidden panels');
    await submit('save');
    await ready();
    fill('#message', '');
    other.remove();

    step = 'unconfirmed save and replay';
    work('artifact-schema');
    fill('#artifacts-1-body', 'This save commits but its response is lost.');
    const requestId = get('[name="request_id"]').value;
    await control({ mode: 'lost' });
    await submit('save');
    check(get('#rescue-title'), 'unconfirmed save uses the existing standalone rescue page');
    check(get('[name="request_id"]').value === requestId, 'rescue keeps the original request ID');
    check(get('#artifacts-1-body').value.includes('response is lost'), 'rescue preserves the submitted artifact');
    check(leaving(), 'rescue still guards its unconfirmed work');
    const committed = await control({ mode: 'success' });
    await submit('save');
    await ready();
    check((await control()).revisions === committed.revisions, 'retry replays the receipt without duplicating revisions');
    check(!get('#artifact-schema').hidden, 'recovery returns to the selected artifact');
    check(get('#artifacts-1-body').value.includes('response is lost'), 'confirmed work survives recovery');

    step = 'failed send before commit';
    view('discuss');
    fill('#message', 'A recoverable message.');
    const beforeFailure = await control({ mode: 'failure' });
    await submit('send');
    check(get('#rescue-title') && get('#message').value === 'A recoverable message.', 'failed send keeps the message in rescue');
    check((await control({ mode: 'success' })).learner_turns === beforeFailure.learner_turns, 'failed write created no turn');
    await submit('send');
    await ready();
    check(doc().activeElement.id === 'message', 'successful recovery returns focus to the conversation');
    check((await control()).learner_turns === beforeFailure.learner_turns + 1, 'retry creates exactly one turn');
    await control({ reply: true });
    await wait(() => !get('button[value="send"]').disabled, 'recovered reply');
    check(get('#transcript').scrollHeight - get('#transcript').clientHeight - get('#transcript').scrollTop < 32,
      'reply follows when the learner stays at the latest exchange');

    step = 'narrow screens';
    frame.style.width = '390px';
    frame.style.height = '844px';
    await delay(100);
    view('build');
    work('artifact-api');
    check(visible('#artifacts-0-body') && !visible('#message'), 'mobile Build focuses the selected artifact');
    check(doc().documentElement.scrollWidth <= 390, 'mobile workspace has no horizontal overflow');
    fill('#artifacts-0-body', 'Mobile draft retained across views.');
    view('discuss');
    check(visible('#message') && !visible('#artifacts-0-body'), 'mobile Discuss focuses the conversation');
    check(get('#message').getBoundingClientRect().bottom < 844, 'mobile composer stays in view');
    check(get('button[value="send"]').getBoundingClientRect().bottom <= get('.practice-composer').getBoundingClientRect().bottom,
      'mobile Send is not clipped inside the composer');
    fill('#message', 'Mobile conversation draft.');
    view('build');
    check(get('#artifacts-0-body').value === 'Mobile draft retained across views.', 'mobile switches keep work');
    view('discuss');
    check(get('#message').value === 'Mobile conversation draft.', 'mobile switches keep the message');
    await submit('send');
    await ready();
    check(visible('#message') && doc().activeElement.id === 'message', 'mobile send restores visible composer focus');
    view('build');
    await control({ reply: true });
    await wait(() => !get('button[value="send"]').disabled, 'mobile reply');
    check(!get('[data-discussion-new]').hidden, 'mobile Build signals that a reply arrived');
    view('discuss');
    check(get('[data-discussion-new]').hidden, 'opening the latest conversation clears the signal');
    frame.style.width = '320px';
    await delay(100);
    check(doc().documentElement.scrollWidth <= 320, '320px view has no horizontal overflow');

    step = 'storage blocked';
    await load(frame, () => { frame.src = sessionURL + '?fixture_storage=blocked&view=build&work=artifact-api'; });
    await ready();
    check(!get('#artifact-api').hidden, 'URL restores the requested work tab without browser storage');
    view('discuss');
    check(visible('#message'), 'tabs still work with storage unavailable');
    check(get('#artifacts-0-body').value === 'Mobile draft retained across views.', 'server remains the source of saved work');

    step = 'JavaScript unavailable';
    const plain = document.createElement('iframe');
    plain.setAttribute('sandbox', 'allow-forms allow-same-origin');
    plain.style.cssText = 'width:1280px;height:720px;border:0';
    document.body.appendChild(plain);
    await load(plain, () => { plain.src = sessionURL; });
    check(!get('.is-enhanced', plain), 'plain form does not depend on enhancement');
    ['#artifacts-0-body', '#artifacts-1-body', '#artifacts-2-body', '#brief-0-text', '#message'].forEach(
      (selector) => check(visible(selector, plain), `no-JS form exposes ${selector}`));
    fill('#artifacts-0-body', 'Saved without JavaScript.', plain);
    await submit('save', plain);
    check(get('#artifacts-0-body', plain).value === 'Saved without JavaScript.', 'native saving works without JavaScript');
    plain.remove();
    document.body.dataset.testResult = 'pass';
    result.textContent = `PASS: ${checks} integrated practice browser checks`;
  } catch (error) {
    result.textContent = `FAIL: ${step}: ${error.message}\n${error.stack}`;
  }
})();
