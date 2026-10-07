import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useFocusEffect } from 'expo-router';
import { useCallback } from 'react';

import { useAuth } from '@/lib/auth-context';
import { wishlistApi } from '@/lib/wishlist-api';
import { wishlistMutations, wishlistRefreshOptions } from '@/lib/wishlist-cache';
import { validGiftId, wishlistKeys } from '@/lib/wishlist-model';

export function useWishlist() {
  const { isAuthenticated } = useAuth();
  const query = useQuery({ ...wishlistRefreshOptions, queryKey: wishlistKeys.gifts(), queryFn: wishlistApi.getGifts, enabled: isAuthenticated === true });
  const { refetch } = query;
  useFocusEffect(useCallback(() => {
    if (isAuthenticated) void refetch();
  }, [isAuthenticated, refetch]));
  return query;
}

export function useGift(id: number) {
  const { isAuthenticated } = useAuth();
  const enabled = isAuthenticated === true && validGiftId(id);
  const query = useQuery({ ...wishlistRefreshOptions, queryKey: wishlistKeys.gift(id), queryFn: () => wishlistApi.getGift(id), enabled });
  const { refetch } = query;
  useFocusEffect(useCallback(() => { if (enabled) void refetch(); }, [enabled, refetch]));
  return query;
}

export function useWishlistActions() {
  const client = useQueryClient();
  const options = wishlistMutations(client, wishlistApi);
  return { create: useMutation(options.create), update: useMutation(options.update), remove: useMutation(options.delete) };
}
