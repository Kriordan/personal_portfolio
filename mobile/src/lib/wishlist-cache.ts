import { onlineManager, type QueryClient } from '@tanstack/react-query';

import { wishlistKeys, type Gift, type GiftInput } from './wishlist-model.ts';

export const wishlistRefreshOptions = {
  refetchOnWindowFocus: 'always',
  refetchOnReconnect: 'always',
  refetchOnMount: 'always',
  // Private photo URLs expire after 15 minutes. Renew while the app is active;
  // focus/reconnect also recover links after sleep or an offline interval.
  refetchInterval: 10 * 60 * 1000,
  refetchIntervalInBackground: false,
} as const;

export class OfflineWishlistError extends Error {
  constructor() {
    super('You’re offline. Reconnect, then save again. Your draft is still here.');
    this.name = 'ApiError';
  }
}

type WishlistClient = {
  createGift: (input: GiftInput) => Promise<{ gift: Gift }>;
  updateGift: (id: number, input: GiftInput) => Promise<{ gift: Gift }>;
  deleteGift: (id: number) => Promise<{ message: string }>;
};

/** A removed mutation (logout clears the cache) must never repopulate private data. */
export function wishlistMutations(client: QueryClient, api: WishlistClient) {
  const base = { retry: false, networkMode: 'always' } as const;
  const requireOnline = () => { if (!onlineManager.isOnline()) throw new OfflineWishlistError(); };
  const sessionKey = [...wishlistKeys.all, 'mutation-session'];
  const onMutate = () => {
    if (!client.getQueryData(sessionKey)) client.setQueryData(sessionKey, {});
    return { session: client.getQueryData(sessionKey) };
  };
  type Context = ReturnType<typeof onMutate> | undefined;
  const active = (context: Context) => !!context && context.session === client.getQueryData(sessionKey);
  const reconcile = async ({ gift }: { gift: Gift }, _variables: unknown, context: Context) => {
    if (!active(context)) return;
    await client.cancelQueries({ queryKey: wishlistKeys.all });
    if (!active(context)) return;
    client.setQueryData(wishlistKeys.gift(gift.id), { gift });
    client.setQueryData<{ gifts: Gift[] }>(wishlistKeys.gifts(), (old) => old ? {
      gifts: [...old.gifts.filter((entry) => entry.id !== gift.id), gift],
    } : undefined);
    void client.invalidateQueries({ queryKey: wishlistKeys.gifts() });
  };
  const recover = (_error: Error, _variables: unknown, context: Context) => { if (active(context)) void client.invalidateQueries({ queryKey: wishlistKeys.all }); };
  return {
    create: {
      ...base, onMutate, mutationKey: ['wishlist', 'create'],
      mutationFn: (input: GiftInput) => { requireOnline(); return api.createGift(input); },
      onSuccess: reconcile, onError: recover,
    },
    update: {
      ...base, onMutate, mutationKey: ['wishlist', 'update'],
      mutationFn: ({ id, input }: { id: number; input: GiftInput }) => { requireOnline(); return api.updateGift(id, input); },
      onSuccess: reconcile, onError: recover,
    },
    delete: {
      ...base, onMutate, mutationKey: ['wishlist', 'delete'],
      mutationFn: (id: number) => { requireOnline(); return api.deleteGift(id); },
      onSuccess: async (_result: { message: string }, id: number, context: Context) => {
        if (!active(context)) return;
        await client.cancelQueries({ queryKey: wishlistKeys.all });
        if (!active(context)) return;
        client.removeQueries({ queryKey: wishlistKeys.gift(id), exact: true });
        client.setQueryData<{ gifts: Gift[] }>(wishlistKeys.gifts(), (old) => old ? { gifts: old.gifts.filter((gift) => gift.id !== id) } : undefined);
        void client.invalidateQueries({ queryKey: wishlistKeys.gifts() });
      },
      onError: recover,
    },
  };
}
