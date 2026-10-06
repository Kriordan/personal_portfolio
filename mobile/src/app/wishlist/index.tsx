import { Host } from '@expo/ui';
import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { GiftPhoto } from '@/components/gift-photo';
import { NativeField } from '@/components/native-form';
import { InlineError, NativeAction, PageHeading, ScreenState, screenStyles } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { useWishlist } from '@/hooks/use-wishlist';
import { browseGifts, type Gift } from '@/lib/wishlist-model';

function GiftRow({ gift }: { gift: Gift }) {
  const theme = useTheme();
  const router = useRouter();
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={`${gift.title}. ${gift.body}`} accessibilityHint="Opens gift details" onPress={() => router.push(`/wishlist/${gift.id}`)} style={({ pressed }) => [styles.row, { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement }]}>
      <GiftPhoto uri={gift.image_url} thumbnail />
      <View style={styles.rowBody}>
        <ThemedText style={styles.title}>{gift.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>{gift.body}</ThemedText>
      </View>
      <ThemedText accessible={false} themeColor="textSecondary">›</ThemedText>
    </Pressable>
  );
}
const keyForGift = (gift: Gift) => String(gift.id);
const renderGift = ({ item }: { item: Gift }) => <GiftRow gift={item} />;

export default function WishlistScreen() {
  const query = useWishlist();
  const router = useRouter();
  const theme = useTheme();
  const search = useNativeText();
  const [refreshing, setRefreshing] = useState(false);
  const gifts = useMemo(() => browseGifts(query.data?.gifts ?? [], search.text), [query.data?.gifts, search.text]);
  if (!query.data && query.isPending) return <ScreenState loading={!query.isPaused} title={query.isPaused ? 'You’re offline' : 'Loading your wishlist'} message={query.isPaused ? 'Reconnect to load your gifts.' : undefined} />;
  if (!query.data) return <ScreenState title="Couldn’t load Wishlist" message="Check your connection and try again." onRetry={() => void query.refetch()} />;
  return (
    <SafeAreaView edges={['left', 'right', 'bottom']} style={[styles.screen, { backgroundColor: theme.background }]}>
      <FlatList data={gifts} keyExtractor={keyForGift} renderItem={renderGift} contentContainerStyle={screenStyles.collection} contentInsetAdjustmentBehavior="automatic" keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); void query.refetch().finally(() => setRefreshing(false)); }} />}
        ListHeaderComponent={<View style={screenStyles.gap}>
          <PageHeading title="Good things to wish for." subtitle="Keep the ideas you love in one place." />
          <NativeAction label="Add gift" onPress={() => router.push('/wishlist/new')} />
          <Host matchContents={{ vertical: true }}><NativeField label="Search wishlist" {...search.input} placeholder="Title or description" /></Host>
          {search.text ? <NativeAction label="Clear search" secondary onPress={search.clear} /> : null}
          {query.isError ? <InlineError message="Couldn’t refresh. These are your last loaded gifts." onRetry={() => void query.refetch()} /> : null}
          <ThemedText type="smallBold" themeColor="textSecondary" style={styles.count}>{`${gifts.length} ${gifts.length === 1 ? 'gift' : 'gifts'} · Newest first`}</ThemedText>
        </View>}
        ListEmptyComponent={<View style={styles.empty}><ThemedText type="subtitle">{query.data.gifts.length ? 'No matching gifts' : 'A little inspiration starts here.'}</ThemedText><ThemedText themeColor="textSecondary">{query.data.gifts.length ? 'Try a different title or description.' : 'Save your first idea with Add gift. A photo is optional.'}</ThemedText></View>}
      />
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1 },
  row: { minHeight: 96, padding: 16, gap: 14, borderRadius: 16, marginBottom: 10, flexDirection: 'row', alignItems: 'center' },
  rowBody: { flex: 1, gap: 4 },
  title: { fontWeight: '600' },
  count: { paddingVertical: 12 },
  empty: { paddingVertical: 24, gap: 12 },
});
