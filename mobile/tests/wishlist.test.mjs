import assert from 'node:assert/strict';
import { test } from 'node:test';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
import { QueryClient, QueryObserver, MutationObserver, focusManager, onlineManager } from '@tanstack/react-query';
import { browseGifts, draftInput, giftRequestBody, giftValidation, photoPreview, validGiftId, wishlistKeys } from '../src/lib/wishlist-model.ts';
import { wishlistMutations, wishlistRefreshOptions } from '../src/lib/wishlist-cache.ts';

const tick = () => new Promise((resolve) => setImmediate(resolve));
const gift = (id = 1, overrides = {}) => ({ id, title: `Gift ${id}`, body: 'Description', timestamp: null, image_url: null, user_id: 1, ...overrides });
const input = { title: 'New gift', body: 'Description' };
const api = {
  createGift: async () => ({ gift: gift(3) }),
  updateGift: async (id) => ({ gift: gift(id, { title: 'Changed' }) }),
  deleteGift: async () => ({ message: 'Gift deleted.' }),
};

test('browse sorts deterministically without mutating the cache and searches both fields', () => {
  const gifts = [gift(1), gift(2, { timestamp: '2026-10-01T00:00:00Z', body: 'Coffee grinder' }), gift(3, { timestamp: '2026-10-01T00:00:00Z' }), gift(4)];
  assert.deepEqual(browseGifts(gifts, '').map((gift) => gift.id), [3, 2, 4, 1]);
  assert.deepEqual(gifts.map((gift) => gift.id), [1, 2, 3, 4]);
  assert.deepEqual(browseGifts(gifts, ' COFFEE ').map((gift) => gift.id), [2]);
  assert.equal(browseGifts(gifts, 'Gift 3')[0].id, 3);
  assert.equal(browseGifts(gifts, 'unmatched').length, 0);
});

test('validation matches Python Unicode lengths and rejects invalid route IDs', () => {
  assert.equal(giftValidation('😀'.repeat(140), ' description '), null);
  assert.match(giftValidation('x'.repeat(141), 'description'), /140/);
  assert.match(giftValidation('title', ' '), /Enter/);
  for (const id of [0, -1, NaN, Infinity, 1.2, Number.MAX_SAFE_INTEGER + 1]) assert.equal(validGiftId(id), false);
  assert.equal(validGiftId(1), true);
});

test('keep, replace, remove and undo produce distinct previews and request bodies', () => {
  const image = { uri: 'file:///photo.jpg', name: 'photo.jpg', type: 'image/jpeg' };
  assert.equal(photoPreview({ kind: 'keep' }, 'original'), 'original');
  assert.equal(photoPreview({ kind: 'replace', image }, 'original'), image.uri);
  assert.equal(photoPreview({ kind: 'remove' }, 'original'), null);
  assert.deepEqual(giftRequestBody(draftInput(' title ', ' body ', { kind: 'keep' })), { title: 'title', body: 'body' });
  assert.deepEqual(giftRequestBody(draftInput('title', 'body', { kind: 'remove' })), { title: 'title', body: 'body', remove_image: true });
  assert.throws(() => giftRequestBody({ ...input, image, removeImage: true }));
});

test('multipart uses actual file bytes, compatible with Expo 57 fetch', async () => {
  const image = { uri: 'blob:photo', name: 'photo.jpg', type: 'image/jpeg', file: new Blob(['photo bytes'], { type: 'image/jpeg' }) };
  const web = giftRequestBody({ ...input, image });
  assert.equal(web.get('image').size, 11);
  assert.equal(web.get('image').name, 'photo.jpg');
  assert.equal(web.get('title'), input.title);
  // Execute the installed SDK's converter, replacing only its native Blob reader.
  const source = readFileSync(new URL('../node_modules/expo/src/winter/fetch/convertFormData.ts', import.meta.url), 'utf8')
    .replace("import { blobToArrayBufferAsync } from '../../utils/blobUtils';", 'const blobToArrayBufferAsync = (blob: Blob) => blob.arrayBuffer();');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  const { convertFormDataAsync } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
  const result = await convertFormDataAsync(web, 'test-boundary');
  assert.match(new TextDecoder().decode(result.body), /photo bytes/);
  assert.match(new TextDecoder().decode(result.body), /filename="photo.jpg"/);
  const nativeFile = { name: 'native.jpg', type: 'image/jpeg', bytes: async () => new TextEncoder().encode('native file bytes') };
  const nativeBody = { entries: () => [['image', nativeFile]] };
  assert.match(new TextDecoder().decode((await convertFormDataAsync(nativeBody)).body), /native file bytes/);
  await assert.rejects(convertFormDataAsync({ entries: () => [['image', { uri: 'file:///old.jpg', name: 'old.jpg', type: 'image/jpeg' }]] }), /Unsupported FormDataPart/);
});

test('authoritative CRUD updates overview/detail, cancels stale reads, and removes deleted detail', async () => {
  const client = new QueryClient();
  client.setQueryData(wishlistKeys.gifts(), { gifts: [gift()] });
  let finishOldRead;
  const oldRead = client.fetchQuery({ queryKey: wishlistKeys.gift(1), queryFn: () => new Promise((resolve) => { finishOldRead = resolve; }) }).catch(() => {});
  await tick();
  const mutations = wishlistMutations(client, api);
  await new MutationObserver(client, mutations.update).mutate({ id: 1, input });
  finishOldRead({ gift: gift(1, { title: 'Stale' }) });
  await oldRead;
  assert.equal(client.getQueryData(wishlistKeys.gift(1)).gift.title, 'Changed');
  assert.equal(client.getQueryData(wishlistKeys.gifts()).gifts[0].title, 'Changed');
  await new MutationObserver(client, mutations.create).mutate(input);
  assert.equal(client.getQueryData(wishlistKeys.gifts()).gifts.length, 2);
  await new MutationObserver(client, mutations.delete).mutate(1);
  assert.equal(client.getQueryData(wishlistKeys.gift(1)), undefined);
  assert.deepEqual(client.getQueryData(wishlistKeys.gifts()).gifts.map((gift) => gift.id), [3]);
  client.clear();
});

test('offline changes fail now, never queue or replay on reconnect', async () => {
  const client = new QueryClient();
  client.mount();
  let calls = 0;
  const options = wishlistMutations(client, { ...api, createGift: async () => { calls++; return api.createGift(); } });
  try {
    onlineManager.setOnline(false);
    const observer = new MutationObserver(client, options.create);
    await assert.rejects(observer.mutate(input), /offline/);
    assert.equal(observer.getCurrentResult().isPaused, false);
    onlineManager.setOnline(true);
    await tick();
    assert.equal(calls, 0);
  } finally { onlineManager.setOnline(true); client.unmount(); client.clear(); }
});

test('lost responses invalidate authoritative reads without repeating creation', async () => {
  const client = new QueryClient();
  client.setQueryData(wishlistKeys.gifts(), { gifts: [] });
  let calls = 0;
  const options = wishlistMutations(client, { ...api, createGift: async () => { calls++; throw new Error('Lost response'); } });
  await assert.rejects(new MutationObserver(client, options.create).mutate(input), /Lost response/);
  assert.equal(calls, 1);
  assert.equal(client.getQueryState(wishlistKeys.gifts()).isInvalidated, true);
  client.clear();
});

test('logout cache clearing prevents a late save from restoring private gifts, including after another account saves', async () => {
  const client = new QueryClient();
  let finish;
  const options = wishlistMutations(client, { ...api, createGift: () => new Promise((resolve) => { finish = resolve; }) });
  const pending = new MutationObserver(client, options.create).mutate(input);
  await tick();
  client.clear();
  await new MutationObserver(client, wishlistMutations(client, api).create).mutate(input);
  finish({ gift: gift(99) });
  await pending;
  assert.equal(client.getQueryData(wishlistKeys.gift(99)), undefined);
  assert.equal(client.getQueryData(wishlistKeys.gift(3)).gift.id, 3);
  client.clear();
});

for (const kind of ['foreground', 'reconnect', 'remount']) test(`${kind} refreshes fresh Wishlist data`, async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } });
  client.mount();
  let reads = 0;
  const query = new QueryObserver(client, { ...wishlistRefreshOptions, queryKey: wishlistKeys.gifts(), queryFn: async () => ({ gifts: [gift(++reads)] }) });
  let unsubscribe = query.subscribe(() => {});
  try {
    await tick();
    assert.equal(reads, 1);
    if (kind === 'foreground') { focusManager.setFocused(false); focusManager.setFocused(true); }
    else if (kind === 'reconnect') { onlineManager.setOnline(false); onlineManager.setOnline(true); }
    else { unsubscribe(); unsubscribe = query.subscribe(() => {}); }
    await tick();
    assert.equal(reads, 2);
  } finally { unsubscribe(); client.unmount(); client.clear(); focusManager.setFocused(undefined); onlineManager.setOnline(true); }
});
