(() => {
  // Presentation only. Native form POSTs, request IDs, CSRF, conflict responses, and
  // the standalone rescue page remain the authority for saving and recovery.
  const workspace = document.querySelector('[data-practice-workspace]');
  const form = workspace?.querySelector('[data-practice-form]');
  if (!form) return;
  const layout = document.getElementById('practice-layout');
  const transcript = document.getElementById('transcript');
  const workScroll = workspace.querySelector('.practice-work-panels');
  const newMessages = workspace.querySelector('[data-new-messages]');
  const discussionNew = workspace.querySelector('[data-discussion-new]');
  const viewTabs = [...workspace.querySelectorAll('[data-practice-view]')];
  const workTabs = [...workspace.querySelectorAll('[data-work-target]')];
  const panels = [...workspace.querySelectorAll('[data-work-panel]')];
  const views = ['discuss', 'build'];
  const noteControls = ['text', 'kind', 'pinned', 'remove'];
  const panelIds = panels.map((panel) => panel.id);
  const storageKey = `learning-practice-ui:${location.pathname}`;
  const pendingKey = `${storageKey}:submission`;
  const read = (store, key) => {
    try { return JSON.parse(window[store].getItem(key)) || {}; } catch { return {}; }
  };
  const write = (store, key, value) => {
    try { window[store].setItem(key, JSON.stringify(value)); } catch { /* Storage is optional. */ }
  };
  const saved = read('localStorage', storageKey);
  const position = (value) => Number.isFinite(value) && value >= 0 ? value : 0;
  const query = new URLSearchParams(location.search);
  const state = {
    view: views.includes(query.get('view')) ? query.get('view') : views.includes(saved.view) ? saved.view : 'discuss',
    work: panelIds.includes(query.get('work')) ? query.get('work') : panelIds.includes(saved.work) ? saved.work : 'requirements',
    top: position(saved.top), atEnd: saved.atEnd !== false, workTop: position(saved.workTop),
  };
  const workPositions = { [state.work]: state.workTop };
  let following = state.atEnd;
  let lastEditor = null;
  let persistTimer;
  const chatPosition = () => transcript.clientHeight ? {
    top: transcript.scrollTop,
    atEnd: transcript.scrollHeight - transcript.clientHeight - transcript.scrollTop < 32,
  } : { top: state.top, atEnd: state.atEnd };
  const persist = () => {
    Object.assign(state, chatPosition());
    if (workScroll.clientHeight) state.workTop = workScroll.scrollTop;
    // Never store learner text, session content, tokens, or server revision state.
    write('localStorage', storageKey, state);
  };
  const rememberScroll = () => {
    Object.assign(state, chatPosition());
    clearTimeout(persistTimer);
    persistTimer = setTimeout(persist, 150);
  };
  const restoreChat = () => {
    if (!transcript.clientHeight) return;
    transcript.scrollTop = state.atEnd ? transcript.scrollHeight : state.top;
    if (state.atEnd) { newMessages.hidden = true; discussionNew.hidden = true; }
  };
  const sizeLayout = () => {
    // Leave room for Save/Pause below the panes. Short windows can scroll the page;
    // the composer never covers the transcript or consumes its entire height.
    const top = layout.getBoundingClientRect().top + window.scrollY;
    layout.style.setProperty('--workspace-height', `${Math.max(400, window.innerHeight - top - 86)}px`);
  };
  const updateURL = () => {
    try {
      const url = new URL(location.href);
      url.searchParams.set('view', state.view);
      url.searchParams.set('work', state.work);
      history.replaceState(history.state, '', url);
    } catch { /* Tabs still work without history access. */ }
  };
  const select = (view, work, { keepHash = false } = {}) => {
    Object.assign(state, chatPosition());
    if (workScroll.clientHeight) workPositions[state.work] = workScroll.scrollTop;
    if (views.includes(view)) state.view = view;
    if (panelIds.includes(work)) state.work = work;
    workspace.dataset.view = state.view;
    viewTabs.forEach((tab) => {
      const active = tab.dataset.practiceView === state.view;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    layout.setAttribute('aria-labelledby', `practice-view-${state.view}`);
    workTabs.forEach((tab) => {
      const active = tab.dataset.workTarget === state.work;
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    panels.forEach((panel) => { panel.hidden = panel.id !== state.work; });
    workScroll.scrollTop = workPositions[state.work] || 0;
    if (state.work === 'requirements' && workScroll.clientHeight) {
      workspace.querySelector('[data-requirements-new]').hidden = true;
    }
    if (!keepHash && location.hash) {
      try { history.replaceState(history.state, '', location.pathname + location.search); } catch { /* Optional. */ }
    }
    restoreChat();
    updateURL();
    persist();
  };
  const setupTabs = (tabs, group, label, target, activate) => {
    group.hidden = false;
    group.setAttribute('role', 'tablist');
    group.setAttribute('aria-label', label);
    tabs.forEach((tab, index) => {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('aria-controls', target(tab));
      tab.addEventListener('click', (event) => { event.preventDefault(); activate(tab); });
      tab.addEventListener('keydown', (event) => {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        if (next === undefined) return;
        event.preventDefault();
        activate(tabs[next]);
        tabs[next].focus({ preventScroll: true });
      });
    });
  };
  workspace.classList.add('is-enhanced');
  setupTabs(viewTabs, workspace.querySelector('[data-view-tabs]'), 'Practice view', () => layout.id,
    (tab) => select(tab.dataset.practiceView, state.work));
  setupTabs(workTabs, workspace.querySelector('[data-work-tabs]'), 'Work and reference', (tab) => tab.dataset.workTarget,
    (tab) => select(state.view, tab.dataset.workTarget));
  layout.setAttribute('role', 'tabpanel');
  panels.forEach((panel) => {
    panel.setAttribute('role', 'tabpanel');
    panel.setAttribute('aria-labelledby', workTabs.find((tab) => tab.dataset.workTarget === panel.id).id);
  });
  workScroll.tabIndex = 0;
  workScroll.setAttribute('role', 'region');
  workScroll.setAttribute('aria-label', 'Work content');

  // Blank note fields are still submitted, preserving the server's original form
  // shape. Reveal them deliberately; with JS absent they are all visible.
  const addNote = workspace.querySelector('[data-add-note]');
  const blankNotes = [...workspace.querySelectorAll('[data-blank-note]')];
  blankNotes.forEach((note) => { note.hidden = true; });
  const updateAddNote = () => {
    addNote.hidden = false;
    addNote.disabled = !blankNotes.some((note) => note.hidden);
    addNote.textContent = addNote.disabled ? 'Save work to add more notes' : 'Add a note';
  };
  addNote.addEventListener('click', () => {
    const note = blankNotes.find((row) => row.hidden);
    if (note) { note.hidden = false; note.querySelector('textarea').focus(); }
    updateAddNote();
  });
  updateAddNote();

  const reveal = (element, focus = false) => {
    if (!element) return;
    const panel = element.closest('[data-work-panel]');
    const inConversation = element.closest('.practice-discuss');
    select(panel || element.id === 'work' ? 'build' : inConversation ? 'discuss' : state.view,
      panel ? panel.id : state.work, { keepHash: true });
    const blank = element.closest('[data-blank-note]');
    if (blank) { blank.hidden = false; updateAddNote(); }
    for (let parent = element.parentElement; parent && parent !== workspace; parent = parent.parentElement) {
      if (parent.tagName === 'DETAILS') parent.open = true;
    }
    if (focus) {
      const field = element.matches('textarea,select,input,button,a') ? element
        : element.querySelector('[aria-invalid="true"],textarea,select') || element;
      if (field === element && !field.matches('textarea,select,input,button,a')) field.tabIndex = -1;
      field.focus({ preventScroll: true });
      element.scrollIntoView({ block: 'nearest' });
    }
  };
  const hashTarget = () => {
    try { return document.getElementById(decodeURIComponent(location.hash.slice(1))); } catch { return null; }
  };
  workspace.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link || link.hasAttribute('data-practice-view') || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || url.pathname !== location.pathname || !url.hash) return;
    let target;
    try { target = document.getElementById(decodeURIComponent(url.hash.slice(1))); } catch { return; }
    if (!target || !workspace.contains(target)) return;
    event.preventDefault();
    try { history.replaceState(history.state, '', location.pathname + location.search + url.hash); } catch { /* Optional. */ }
    reveal(target, true);
  });
  window.addEventListener('hashchange', () => reveal(hashTarget(), true));
  form.addEventListener('invalid', (event) => reveal(event.target), true);

  sizeLayout();
  // On initial load the pane has not been scrolled yet: don't overwrite its saved
  // position with zero while initializing the tabs.
  const initialPosition = { top: state.top, atEnd: state.atEnd };
  select(state.view, state.work, { keepHash: true });
  Object.assign(state, initialPosition);
  restoreChat();
  const pending = read('sessionStorage', pendingKey);
  try { sessionStorage.removeItem(pendingKey); } catch { /* Optional. */ }
  const alert = document.getElementById('practice-alert');
  if (alert) {
    const firstLink = alert.querySelector('a[href^="#"]');
    if (firstLink) reveal(document.getElementById(firstLink.getAttribute('href').slice(1)));
    panels.forEach((panel) => {
      if (panel.querySelector('.practice-conflict,.practice-error,.practice-refreshed')) {
        workTabs.find((tab) => tab.dataset.workTarget === panel.id).classList.add('has-attention');
      }
    });
    // learning-practice.js focuses the error summary after hidden panels are exposed.
  } else if (pending.action === 'submit' && pending.time && Date.now() - pending.time < 5 * 60 * 1000) {
    select('build', 'work-checks');
    document.getElementById('work-tab-checks').focus({ preventScroll: true });
  } else if (pending.time && Date.now() - pending.time < 5 * 60 * 1000) {
    const sending = ['send', 'reply', 'recent'].includes(pending.action);
    const editorId = typeof pending.editor?.id === 'string' ? pending.editor.id : '';
    // Note form indices can change when an earlier entry is removed. Restore by
    // the entry's stable ID so focus cannot jump to a different learner note.
    const savedEditor = typeof pending.editor?.note === 'string'
      ? noteControls.includes(pending.editor.control)
        ? document.getElementById(pending.editor.note)?.querySelector(`[name$="-${pending.editor.control}"]`)
        : null
      : document.getElementById(editorId);
    const field = sending ? document.getElementById('message')
      : savedEditor || workTabs.find((tab) => tab.dataset.workTarget === state.work);
    if (sending) {
      // Keep Build on desktop; on narrow screens focus must be visible in Discuss.
      if (window.matchMedia('(max-width: 760px)').matches) select('discuss', state.work);
      state.atEnd = true;
      restoreChat();
    }
    if (field && form.contains(field)) {
      field.focus({ preventScroll: true });
      if (!sending && field.setSelectionRange && pending.editor) {
        field.setSelectionRange(position(pending.editor.start), position(pending.editor.end));
        field.scrollTop = position(pending.editor.scroll);
      }
    }
  } else if (hashTarget()) reveal(hashTarget(), true);
  persist();

  const rememberEditor = (field) => {
    if (field.matches('textarea,select,input:not([type="hidden"])')) {
      lastEditor = {
        id: field.id, start: field.selectionStart, end: field.selectionEnd, scroll: field.scrollTop,
        note: field.closest('.practice-entry')?.id,
        control: noteControls.find((name) => field.name.endsWith(`-${name}`)),
      };
    }
  };
  const keepFocusedPaneVisible = (field) => {
    if (!window.matchMedia('(max-width: 760px)').matches || !field || field.getClientRects().length) return;
    const view = field.closest('.practice-discuss') ? 'discuss' : field.closest('.practice-build') ? 'build' : null;
    if (!view) return;
    select(view, state.work);
    field.focus({ preventScroll: true });
  };
  form.addEventListener('focusout', (event) => {
    rememberEditor(event.target);
    // Some browsers blur a newly hidden pane before resize is dispatched.
    // Repair only that lost focus, never a deliberate move to another control.
    if (!event.relatedTarget && !event.target.getClientRects().length) {
      queueMicrotask(() => {
        if (document.activeElement === document.body) keepFocusedPaneVisible(event.target);
      });
    }
  });
  form.addEventListener('submit', (event) => {
    if (event.defaultPrevented) return;
    rememberEditor(document.activeElement);
    persist();
    const editor = lastEditor && document.getElementById(lastEditor.id)?.getClientRects().length ? lastEditor : null;
    write('sessionStorage', pendingKey, { time: Date.now(), action: event.submitter?.value || 'save', editor });
  });
  transcript.addEventListener('scroll', () => {
    if (chatPosition().atEnd) { newMessages.hidden = true; discussionNew.hidden = true; }
    rememberScroll();
  });
  workScroll.addEventListener('scroll', rememberScroll);
  form.addEventListener('practice:before-turns', () => { following = chatPosition().atEnd; });
  form.addEventListener('practice:turns', () => {
    if (!transcript.clientHeight) discussionNew.hidden = false;
    if (following) { state.atEnd = true; restoreChat(); }
    else newMessages.hidden = false;
    persist();
  });
  form.addEventListener('practice:requirements', () => {
    workspace.querySelector('[data-requirements-new]').hidden = state.work === 'requirements' && workScroll.clientHeight > 0;
  });
  newMessages.addEventListener('click', () => {
    state.atEnd = true;
    restoreChat();
    transcript.focus({ preventScroll: true });
    persist();
  });
  window.addEventListener('resize', () => { sizeLayout(); keepFocusedPaneVisible(document.activeElement); restoreChat(); });
  window.addEventListener('pagehide', persist);
})();
