import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, StyleSheet, View } from 'react-native';

import { GiftForm } from '@/components/gift-form';
import { GiftPhoto } from '@/components/gift-photo';
import { InlineError, NativeAction, PageHeading, Screen, ScreenState } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useGift } from '@/hooks/use-wishlist';
import { ApiError } from '@/lib/api-client';
import { validGiftId, type Gift } from '@/lib/wishlist-model';

export default function GiftDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const giftId = Number(id);
  const query = useGift(giftId);
  const router = useRouter();
  const [editing, setEditing] = useState<Gift | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const unavailable = !validGiftId(giftId) || query.error instanceof ApiError && [403, 404].includes(query.error.status);
  // Keep an open draft mounted when a background refresh discovers deletion.
  if (unavailable && !editing) return <Screen><PageHeading title="Gift unavailable" subtitle="It may have been deleted or belong to another account." /><NativeAction label="Back to Wishlist" onPress={() => router.replace('/wishlist')} /></Screen>;
  if (!query.data && !editing && query.isPending) return <ScreenState loading={!query.isPaused} title={query.isPaused ? 'You’re offline' : 'Loading gift'} message={query.isPaused ? 'Reconnect to load this gift.' : undefined} />;
  if (!query.data && !editing) return <ScreenState title="Couldn’t load gift" message="Check your connection and try again." onRetry={() => void query.refetch()} />;
  const gift = query.data?.gift ?? editing!;
  const date = gift.timestamp ? new Date(gift.timestamp) : null;
  return <>
    <Stack.Screen options={{ title: 'Gift' }} />
    <Screen refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void query.refetch().finally(() => setRefreshing(false)); }} />}>
      <View style={styles.heading}>
        <View style={styles.title}><PageHeading title={gift.title} /></View>
        <Pressable accessibilityRole="button" accessibilityLabel={`Options for ${gift.title}`} accessibilityHint="Edit or delete gift" style={styles.options} onPress={() => setEditing(gift)}><ThemedText type="subtitle">•••</ThemedText></Pressable>
      </View>
      <GiftPhoto uri={gift.image_url} />
      <ThemedText>{gift.body}</ThemedText>
      {date && Number.isFinite(date.getTime()) ? <ThemedText type="small" themeColor="textSecondary">Added {date.toLocaleDateString()}</ThemedText> : null}
      {query.isError ? <InlineError message="Couldn’t refresh. This is the last loaded gift." onRetry={() => void query.refetch()} /> : null}
    </Screen>
    {/* Preserve the draft's text baseline while renewing its existing photo URL. */}
    {editing ? <GiftForm gift={{ ...editing, image_url: gift.image_url }} onSaved={() => setEditing(null)} onClose={() => setEditing(null)} onDeleted={() => { setEditing(null); router.dismissTo('/wishlist'); }} /> : null}
  </>;
}
const styles = StyleSheet.create({
  heading: { flexDirection: 'row', alignItems: 'flex-start', gap: 8 },
  title: { flex: 1 },
  options: { width: 48, height: 48, alignItems: 'center', justifyContent: 'center' },
});
