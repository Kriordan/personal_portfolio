// Only served by test_learning_hub_browser.py. These are the actual Flask pages,
// forms, and review scheduler. The fixture CSP keeps external resources offline.
(async () => {
  const frame = document.getElementById('hub');
  const result = document.getElementById('result');
  const doc = () => frame.contentDocument;
  const get = (selector) => doc().querySelector(selector);
  let checks = 0;
  let step = 'home';
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
  const counts = async () => (await fetch('/__hub_counts__')).json();
  const noOverflow = () => doc().documentElement.scrollWidth <= frame.clientWidth + 1;
  const home = () => follow('a[href="/learning/"]');
  try {
    await wait(() => get('[data-learning-continue]'), 'continuation card');
    const original = await counts();
    const sessionURL = get('[data-learning-continue]').getAttribute('href');
    check(get('.learning-shell-header') && !get('.Header'), 'compact header');
    check(doc().querySelectorAll('h1').length === 1, 'one page heading');
    check(doc().querySelectorAll('[data-learning-continue]').length === 1, 'one primary continuation');
    check(doc().body.textContent.includes('Paused'), 'saved paused state');
    check(!get('a[href^="/learning/note/"]'), 'note library is absent from home');
    check(noOverflow(), 'desktop home fits viewport');
    ['HIDDEN_SENTINEL', 'HINT_SENTINEL', 'INSTRUCTION_SENTINEL', 'EVALUATOR_SENTINEL',
      'Private answer', 'hotjar', 'googletagmanager'].forEach((value) =>
      check(!doc().documentElement.outerHTML.includes(value), `private material absent: ${value}`));
    click('.learning-skip');
    await wait(() => doc().activeElement.id === 'learning-main', 'skip-link focus');
    check(doc().activeElement.id === 'learning-main', 'skip link moves focus to content');

    step = 'resume';
    await follow('[data-learning-continue]');
    await wait(() => get('.is-enhanced'), 'practice enhancement');
    check(frame.contentWindow.location.pathname === sessionURL, 'Continue opens the original session');
    check(get('#artifacts-0-body').value === 'POST /orders — saved work', 'confirmed artifact retained');
    check(get('button[value="resume"]'), 'opening a paused session does not resume it implicitly');
    click('[data-practice-view="build"]');
    click('[data-work-target="artifact-api"]');
    await home();
    await follow('[data-learning-continue]');
    await wait(() => get('.is-enhanced'), 'practice enhancement');
    check(get('[data-practice-workspace]').dataset.view === 'build', 'last practice view survives a home round trip');
    check(!get('#artifact-api').hidden, 'last artifact tab survives a home round trip');
    await home();

    step = 'references';
    await follow('a[href="/learning/references"]');
    check(get('h1').textContent === 'Reference articles', 'dedicated reference catalog');
    await follow('.learning-text-action');
    check(get('.reference-page') && get('h1').textContent.includes('Modern Images'), 'existing article destination');
    await follow('a[href="/learning/references#web-performance-heading"]');
    check(get('#web-performance-heading'), 'article breadcrumb returns to its catalog');
    await home();

    step = 'flashcard browsing';
    await follow('a[href="/learning/flashcards"]');
    check(get('h1').textContent === 'My flashcards', 'dedicated personal flashcards');
    check(get('#flashcard-due-heading').textContent === '28 cards due', 'future and suspended cards excluded');
    check(doc().querySelectorAll('.learning-hub-notes a').length === 25, 'bounded first page');
    await follow('a[rel="next"]');
    check(doc().querySelectorAll('.learning-hub-notes a').length === 5, 'remaining notes on next page');
    check(frame.contentWindow.location.search.includes('page=2'), 'pagination has a reloadable URL');
    check(get('.learning-hub-notes').textContent.includes('<script>'), 'adversarial title is displayed as text');
    check(!get('.learning-hub-notes script'), 'adversarial title creates no script');
    frame.style.width = '320px';
    await delay(50);
    check(noOverflow(), 'long note title and search controls fit 320 pixels');
    get('#note-query').value = 'nOtE 28';
    await load(() => get('.learning-note-search').requestSubmit());
    check(doc().querySelectorAll('.learning-hub-notes a').length === 1, 'native search is case insensitive');
    check(get('#note-query').value === 'nOtE 28', 'search value survives navigation');
    check(!frame.contentWindow.location.search.includes('page='), 'search resets pagination');
    check(get('#flashcard-due-heading').textContent === '28 cards due', 'search does not narrow the review queue');
    await follow('.learning-hub-notes a');
    check(get('h1').textContent.includes('Note 28'), 'existing note opens');
    await follow('.learning-back');
    check(get('h1').textContent === 'My flashcards', 'note returns to flashcards');
    check(JSON.stringify(await counts()) === JSON.stringify(original), 'browsing has no progress or session writes');

    step = 'review persistence';
    await follow('a[href="/learning/review"]');
    await wait(() => get('#card-question')?.textContent.startsWith('Question '), 'legacy review renderer');
    const firstQuestion = get('#card-question').textContent;
    check(!['Question 00', 'Question 01'].includes(firstQuestion), 'scheduled and suspended cards stay out of review');
    click('[data-review-card]');
    click('[data-rating="4"]');
    await wait(() => get('#card-question').textContent !== firstQuestion, 'next question after save');
    const rated = await counts();
    check(rated.ratings === 1 && rated.receipts === 1, 'one legacy rating and receipt committed');
    await follow('.learning-back');
    check(get('#flashcard-due-heading').textContent === '27 cards due', 'dedicated page reflects saved rating');
    await load(() => frame.contentWindow.location.reload());
    check(get('#flashcard-due-heading').textContent === '27 cards due', 'rating survives a reload');
    await home();
    check(doc().body.textContent.includes('Review · 4 due'), 'personal review leaves concept review independent');
    check(get('[data-learning-continue]').getAttribute('href') === sessionURL, 'review preserves practice continuation');

    step = 'mobile and no JavaScript';
    for (const width of [390, 320]) {
      frame.style.width = `${width}px`;
      await delay(50);
      check(noOverflow(), `${width}-pixel home has no horizontal scroll`);
      check(get('.learning-destinations').getBoundingClientRect().width <= width, 'secondary destinations fit');
      check(get('[data-learning-continue]').getBoundingClientRect().height >= 44, 'Continue has a touch-sized target');
    }
    await load(() => { frame.src = '/learning/?fixture_scripts=off'; });
    check(get('[data-learning-continue]'), 'home works with scripts blocked');
    await follow('a[href="/learning/references"]');
    check(get('h1').textContent === 'Reference articles', 'navigation works with scripts blocked');

    step = 'signed out';
    await follow('a[href="/logout"]');
    await load(() => { frame.src = '/learning/'; });
    check(!get('[data-learning-continue]'), 'anonymous home has no private continuation');
    await follow('a[href="/learning/references"]');
    check(get('h1').textContent === 'Reference articles', 'references remain public');
    await home();
    await follow('a[href="/learning/flashcards"]');
    check(frame.contentWindow.location.pathname === '/login', 'private flashcards require sign-in');
    check(frame.contentWindow.location.search.includes('next='), 'login preserves the flashcard destination');
    check(JSON.stringify(await counts()) === JSON.stringify(rated), 'later navigation adds no writes');
    result.textContent = `PASS: ${checks} Learning hub browser checks`;
    document.documentElement.dataset.testResult = 'pass';
  } catch (error) {
    result.textContent = `FAIL: ${error.message}\n${error.stack}`;
    document.documentElement.dataset.testResult = 'fail';
  }
})();
