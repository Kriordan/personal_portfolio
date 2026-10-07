import assert from 'node:assert/strict';
import { test } from 'node:test';

// Query's timer lifecycle is browser/native only (disabled in Node's SSR mode).
globalThis.window = {};
const { QueryClient, QueryObserver, focusManager, onlineManager } = await import('@tanstack/react-query');
const { wishlistRefreshOptions } = await import('../src/lib/wishlist-cache.ts');
const tick = () => new Promise((resolve) => setImmediate(resolve));

test('active Wishlist renews photo URLs before expiry, pauses asleep, and recovers on foreground', async (context) => {
  context.mock.timers.enable({ apis: ['setInterval', 'setTimeout', 'Date'] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.mount();
  focusManager.setFocused(true);
  let reads = 0;
  const observer = new QueryObserver(client, {
    ...wishlistRefreshOptions, queryKey: ['wishlist', 'gifts'],
    queryFn: async () => ({ gifts: [{ image_url: `https://example.test/photo?signature=${++reads}` }] }),
  });
  const unsubscribe = observer.subscribe(() => {});
  try {
    await tick();
    const first = observer.getCurrentResult().data.gifts[0].image_url;
    context.mock.timers.tick(10 * 60 * 1000);
    await tick();
    assert.equal(reads, 2);
    assert.notEqual(observer.getCurrentResult().data.gifts[0].image_url, first);
    focusManager.setFocused(false);
    context.mock.timers.tick(20 * 60 * 1000);
    await tick();
    assert.equal(reads, 2);
    focusManager.setFocused(true);
    await tick();
    assert.equal(reads, 3);
    onlineManager.setOnline(false);
    context.mock.timers.tick(10 * 60 * 1000);
    await tick();
    assert.equal(reads, 3);
    onlineManager.setOnline(true);
    await tick();
    assert.equal(reads, 4);
  } finally {
    unsubscribe(); client.unmount(); client.clear();
    focusManager.setFocused(undefined); onlineManager.setOnline(true);
    context.mock.timers.reset();
  }
});
