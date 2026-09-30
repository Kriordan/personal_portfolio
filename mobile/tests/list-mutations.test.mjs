import assert from 'node:assert/strict';
import { test } from 'node:test';
import {
  MutationObserver,
  QueryClient,
  onlineManager,
} from '@tanstack/react-query';
import {
  listMutationOptions,
  requireConnection,
} from '../src/lib/list-mutation-policy.ts';

test('offline toggles fail immediately and are not replayed on reconnect', async () => {
  const client = new QueryClient();
  client.mount();
  let calls = 0;
  const observer = new MutationObserver(client, {
    ...listMutationOptions,
    mutationFn: async () => {
      requireConnection();
      calls++;
      return { completed: true };
    },
  });
  try {
    onlineManager.setOnline(false);
    await assert.rejects(observer.mutate(1), /offline/);
    assert.equal(observer.getCurrentResult().isPaused, false);
    onlineManager.setOnline(true);
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(calls, 0);
  } finally {
    onlineManager.setOnline(true);
    client.unmount();
    client.clear();
  }
});

test('a lost toggle response is never retried automatically', async () => {
  const client = new QueryClient();
  let calls = 0;
  const observer = new MutationObserver(client, {
    ...listMutationOptions,
    mutationFn: async () => {
      calls++;
      throw new Error('Lost response');
    },
  });
  await assert.rejects(observer.mutate(1), /Lost response/);
  assert.equal(calls, 1);
  client.clear();
});
