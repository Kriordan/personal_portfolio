import { useRouter } from 'expo-router';
import { RefreshControl, StyleSheet, View } from 'react-native';
import {
  Card,
  InlineError,
  NativeAction,
  NavRow,
  PageHeading,
  Screen,
  SectionHeading,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { mobileTools } from '@/constants/tools';
import { useListsOverview } from '@/hooks/use-lists';
import { useAuth } from '@/lib/auth-context';

export default function HomeScreen() {
  const { user } = useAuth();
  const lists = useListsOverview();
  const router = useRouter();
  const hour = new Date().getHours();
  const greeting =
    hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  return (
    <Screen
      tab
      refreshControl={
        <RefreshControl
          refreshing={lists.isRefetching}
          onRefresh={() => void lists.refetch()}
        />
      }
    >
      <PageHeading
        eyebrow="YOUR EVERYDAY TOOLS"
        title={user ? `${greeting}, ${user.username}.` : `${greeting}.`}
        subtitle="A little less to keep in your head."
      />
      <Card>
        <ThemedText type="subtitle" accessibilityRole="header">
          Ready for your next shop
        </ThemedText>
        {lists.data ? (
          <View style={styles.counts}>
            <View style={styles.count}>
              <ThemedText type="title">{lists.data.owned.length}</ThemedText>
              <ThemedText themeColor="textSecondary">Your lists</ThemedText>
            </View>
            <View style={styles.count}>
              <ThemedText type="title">{lists.data.shared.length}</ThemedText>
              <ThemedText themeColor="textSecondary">
                Shared with you
              </ThemedText>
            </View>
          </View>
        ) : (
          <ThemedText themeColor="textSecondary">
            {lists.isPaused
              ? 'Connect to load your lists.'
              : lists.isPending
                ? 'Loading your lists…'
                : 'Your lists are unavailable right now.'}
          </ThemedText>
        )}
        <NativeAction
          label="Open Grocery"
          onPress={() => router.push('/lists')}
        />
      </Card>
      {lists.isError ? (
        <InlineError
          message="Couldn’t refresh your lists."
          onRetry={() => void lists.refetch()}
        />
      ) : null}
      {lists.data && lists.data.owned.length + lists.data.shared.length > 0 ? (
        <>
          <SectionHeading>Your grocery lists</SectionHeading>
          {[
            ...lists.data.owned.map((list) => ({ ...list, shared: false })),
            ...lists.data.shared.map((list) => ({ ...list, shared: true })),
          ]
            .slice(0, 3)
            .map((list) => (
              <NavRow
                key={list.id}
                title={list.title}
                subtitle={list.shared ? 'Shared with you' : 'Your list'}
                href={`/lists/${list.id}`}
              />
            ))}
        </>
      ) : null}
      <SectionHeading>Make a little room</SectionHeading>
      {mobileTools
        .filter(
          (tool) => tool.title === 'Wishlist' || tool.title === 'Learning',
        )
        .map((tool) => (
          <NavRow
            key={tool.href}
            title={tool.title}
            subtitle={tool.description}
            href={tool.href}
            badge={tool.badge}
          />
        ))}
      <NativeAction
        label="Explore all tools"
        secondary
        onPress={() => router.navigate('/tools')}
      />
    </Screen>
  );
}
const styles = StyleSheet.create({
  counts: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 28,
    paddingVertical: 8,
  },
  count: { flex: 1, minWidth: 110, gap: 2 },
});
