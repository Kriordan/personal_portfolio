import { useQuery } from '@tanstack/react-query';
import { Redirect, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Image,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { wishlistApi, wishlistKeys, type Gift } from '@/lib/wishlist-api';

function GiftRow({ gift, onPress }: { gift: Gift; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}
    >
      {gift.image_url ? (
        <Image source={{ uri: gift.image_url }} style={styles.thumbnail} resizeMode="cover" />
      ) : null}
      <View style={styles.rowBody}>
        <ThemedText>{gift.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>
          {gift.body}
        </ThemedText>
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        ›
      </ThemedText>
    </Pressable>
  );
}

export default function WishlistScreen() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const giftsQuery = useQuery({
    queryKey: wishlistKeys.gifts(),
    queryFn: wishlistApi.getGifts,
    enabled: isAuthenticated === true,
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (giftsQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (giftsQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Couldn’t load your wishlist.</ThemedText>
        <Pressable style={styles.button} onPress={() => giftsQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const { gifts } = giftsQuery.data;

  return (
    <ThemedView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={giftsQuery.isRefetching}
            onRefresh={() => giftsQuery.refetch()}
          />
        }
      >
        <Pressable style={styles.button} onPress={() => router.push('/wishlist/new')}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Add Gift
          </ThemedText>
        </Pressable>

        <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
          GIFTS
        </ThemedText>
        {gifts.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            No gifts yet. Add one above.
          </ThemedText>
        ) : (
          gifts.map((gift) => (
            <GiftRow key={gift.id} gift={gift} onPress={() => router.push(`/wishlist/${gift.id}`)} />
          ))
        )}
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.three,
  },
  scrollContent: {
    padding: Spacing.three,
    gap: Spacing.two,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  sectionHeader: {
    marginTop: Spacing.three,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
  },
  rowBody: {
    flex: 1,
    gap: Spacing.half,
  },
  thumbnail: {
    width: 48,
    height: 48,
    borderRadius: Spacing.one,
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    color: '#ffffff',
  },
});
