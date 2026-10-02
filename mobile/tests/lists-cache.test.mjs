import assert from 'node:assert/strict';
import { test } from 'node:test';
import { focusManager, onlineManager, QueryClient, QueryObserver } from '@tanstack/react-query';
import {
  createListRoomHandlers,
  grocerySections,
  listsKeys,
  listsRefreshOptions,
  patchList,
  withCategoryAdded,
  withItemAdded,
  withItemToggled,
} from '../src/lib/lists-cache.ts';

const item = (id, completed = false, category_id = 10, ordering = id) => ({
  id,
  name: `Item ${id}`,
  quantity: null,
  notes: null,
  completed,
  ordering,
  category_id,
});
const detail = (mode = 'category_section') => ({
  id: 1,
  title: 'Groceries',
  owner_id: 1,
  completed_display_mode: mode,
  created_at: null,
  updated_at: null,
  categories: [
    {
      id: 20,
      name: 'Household',
      ordering: 2,
      items: [item(4, true, 20), item(3, false, 20)],
    },
    { id: 10, name: 'Produce', ordering: 1, items: [item(2, true), item(1)] },
  ],
});
const tick = () => new Promise((resolve) => setImmediate(resolve));

for (const recovery of ['foreground', 'network reconnect']) {
  test(`${recovery} fetches missed items even when the list is still fresh and the socket has not rejoined`, async (t) => {
    const client = new QueryClient({
      defaultOptions: { queries: { retry: false, staleTime: 30_000 } },
    });
    focusManager.setFocused(true);
    onlineManager.setOnline(true);
    client.mount();
    let server = detail();
    let reads = 0;
    const queryKey = listsKeys.detail(1);
    const observer = new QueryObserver(client, {
      ...listsRefreshOptions,
      queryKey,
      queryFn: async () => {
        reads++;
        return { list: structuredClone(server) };
      },
    });
    const unsubscribe = observer.subscribe(() => {});
    t.after(() => {
      unsubscribe();
      client.unmount();
      client.clear();
      focusManager.setFocused(undefined);
      onlineManager.setOnline(true);
    });
    await tick();
    assert.equal(reads, 1);
    assert.equal(observer.getCurrentResult().isStale, false);
    if (recovery === 'foreground') focusManager.setFocused(false);
    else onlineManager.setOnline(false);
    server = withItemAdded(server, 10, item(99));
    // No socket callback: iOS can suspend JS without an immediate disconnect.
    if (recovery === 'foreground') focusManager.setFocused(true);
    else onlineManager.setOnline(true);
    await tick();
    assert.equal(reads, 2);
    assert.deepEqual(client.getQueryData(queryKey), { list: server });
  });
}

test('website item events add one row immediately, and fetch a missed category when needed', async (t) => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  let server = detail();
  let reads = 0;
  const queryKey = listsKeys.detail(1);
  const observer = new QueryObserver(client, {
    queryKey,
    queryFn: async () => {
      reads++;
      return { list: structuredClone(server) };
    },
  });
  const unsubscribe = observer.subscribe(() => {});
  t.after(() => { unsubscribe(); client.clear(); });
  await tick();
  const handlers = createListRoomHandlers(client, 1);
  const added = item(99);
  server = withItemAdded(server, 10, added);
  const event = { list_id: 1, category_id: 10, item: added, added_by: 'website' };
  handlers.onItemAdded(event);
  handlers.onItemAdded(event);
  await tick();
  assert.equal(reads, 1, 'A received item in a known category needs no manual refresh');
  assert.deepEqual(client.getQueryData(queryKey), { list: server });

  const missedItem = item(100, false, 30);
  server = withCategoryAdded(server, { id: 30, name: 'New', ordering: 3, items: [missedItem] });
  handlers.onItemAdded({ list_id: 1, category_id: 30, item: missedItem, added_by: 'website' });
  await tick();
  assert.equal(reads, 2);
  assert.deepEqual(client.getQueryData(queryKey), { list: server });
});

test('website DOM string IDs update the same item as mobile numeric IDs', async () => {
  const client = new QueryClient();
  client.setQueryData(listsKeys.detail(1), { list: detail() });
  const handlers = createListRoomHandlers(client, 1);
  handlers.onItemToggled({
    list_id: 1,
    item_id: '1',
    completed: true,
    toggled_by: 'website',
  });
  await tick();
  const readItem = () =>
    client
      .getQueryData(listsKeys.detail(1))
      .list.categories.find((category) => category.id === 10)
      .items.find((item) => item.id === 1);
  assert.equal(readItem().completed, true);
  handlers.onItemToggled({
    list_id: 1,
    item_id: 1,
    completed: false,
    toggled_by: 'mobile',
  });
  await tick();
  assert.equal(readItem().completed, false);
  client.clear();
});

test('display modes preserve every item exactly once and keep category/item ordering', () => {
  const expected = {
    inline_bottom: [
      [1, 2],
      [3, 4],
    ],
    category_section: [[1], [2], [3], [4]],
    global_section: [[1], [3], [2, 4]],
  };
  for (const [mode, rows] of Object.entries(expected)) {
    const source = detail(mode);
    const original = structuredClone(source);
    const sections = grocerySections(source);
    assert.deepEqual(
      sections.map((section) => section.data.map((row) => row.id)),
      rows,
    );
    assert.deepEqual(source, original, 'rendering must not mutate query data');
  }
  assert.equal(
    grocerySections(detail('global_section')).at(-1).title,
    'Completed',
  );
  assert.match(grocerySections(detail()).at(1).title, /Produce.*Completed/);
});

test('REST success and echoed events do not duplicate categories/items or invert a toggle', () => {
  const source = detail();
  const added = item(5);
  const category = { id: 30, name: 'Frozen', ordering: 3, items: [] };
  let updated = withItemAdded(withItemAdded(source, 10, added), 10, added);
  updated = withCategoryAdded(withCategoryAdded(updated, category), category);
  updated = withItemToggled(withItemToggled(updated, 1, true), 1, true);
  assert.equal(
    updated.categories
      .find((entry) => entry.id === 10)
      .items.filter((entry) => entry.id === 5).length,
    1,
  );
  assert.equal(updated.categories.filter((entry) => entry.id === 30).length, 1);
  assert.equal(
    updated.categories
      .find((entry) => entry.id === 10)
      .items.find((entry) => entry.id === 1).completed,
    true,
  );
  assert.equal(
    source.categories
      .find((entry) => entry.id === 10)
      .items.find((entry) => entry.id === 1).completed,
    false,
  );
});

test('an older in-flight fetch cannot overwrite a confirmed mutation or socket event', async () => {
  const client = new QueryClient();
  const queryKey = listsKeys.detail(1);
  client.setQueryData(queryKey, { list: detail() });
  let finishFetch;
  const pending = client
    .fetchQuery({
      queryKey,
      queryFn: () =>
        new Promise((resolve) => {
          finishFetch = resolve;
        }),
    })
    .catch(() => {});
  await patchList(client, 1, (list) => withItemToggled(list, 1, true));
  finishFetch({ list: detail() });
  await pending;
  const cached = client.getQueryData(queryKey).list;
  assert.equal(
    cached.categories
      .find((entry) => entry.id === 10)
      .items.find((entry) => entry.id === 1).completed,
    true,
  );
  client.clear();
});

test('joining again fetches changes missed while disconnected', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const queryKey = listsKeys.detail(1);
  let server = detail();
  let requests = 0;
  const observer = new QueryObserver(client, {
    queryKey,
    queryFn: async () => {
      requests++;
      return { list: structuredClone(server) };
    },
  });
  const unsubscribe = observer.subscribe(() => {});
  await tick();
  server = withItemToggled(server, 1, true);
  server.completed_display_mode = 'global_section';
  createListRoomHandlers(client, 1).onJoined();
  await tick();
  assert.equal(requests, 2);
  assert.deepEqual(client.getQueryData(queryKey), { list: server });
  unsubscribe();
  client.clear();
});

test('a live event during reconnect does not discard other missed changes', async () => {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity } },
  });
  const queryKey = listsKeys.detail(1);
  let server = detail();
  let requests = 0;
  let finishOldRead;
  const observer = new QueryObserver(client, {
    queryKey,
    queryFn: () => {
      requests++;
      if (requests === 2)
        return new Promise((resolve) => {
          finishOldRead = resolve;
        });
      return Promise.resolve({ list: structuredClone(server) });
    },
  });
  const unsubscribe = observer.subscribe(() => {});
  await tick();
  server = withCategoryAdded(server, {
    id: 30,
    name: 'Missed while offline',
    ordering: 3,
    items: [],
  });
  const handlers = createListRoomHandlers(client, 1);
  handlers.onJoined();
  server = withItemToggled(server, 1, true);
  handlers.onItemToggled({
    list_id: 1,
    item_id: 1,
    completed: true,
    toggled_by: 'owner',
  });
  await tick();
  finishOldRead({ list: detail() });
  await tick();
  assert.equal(requests, 3);
  assert.deepEqual(client.getQueryData(queryKey), { list: server });
  unsubscribe();
  client.clear();
});

test('reorder and settings events invalidate only their list, and logout cache stays empty', async () => {
  const client = new QueryClient();
  client.setQueryData(listsKeys.detail(1), { list: detail() });
  client.setQueryData(listsKeys.detail(2), { list: { ...detail(), id: 2 } });
  const handlers = createListRoomHandlers(client, 1);
  handlers.onSettingsUpdated({
    list_id: 1,
    completed_display_mode: 'global_section',
    updated_by: 'owner',
  });
  assert.equal(client.getQueryState(listsKeys.detail(1)).isInvalidated, true);
  assert.equal(client.getQueryState(listsKeys.detail(2)).isInvalidated, false);
  client.clear();
  handlers.onItemToggled({
    list_id: 1,
    item_id: 1,
    completed: true,
    toggled_by: 'owner',
  });
  await tick();
  assert.equal(client.getQueryData(listsKeys.detail(1)), undefined);
  client.clear();
});
