import { useRouter } from 'expo-router';
import { RefreshControl } from 'react-native';
import {
  InlineError,
  NativeAction,
  NavRow,
  PageHeading,
  Screen,
  SectionHeading,
} from '@/components/screen';
import { DrawQuickReference } from '@/components/lottery-content';
import { useQueryClient } from '@tanstack/react-query';
import { mobileTools } from '@/constants/tools';
import { useListsOverview } from '@/hooks/use-lists';
import { useAuth } from '@/lib/auth-context';

export default function HomeScreen() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
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
          onRefresh={() => {
            void lists.refetch();
            void queryClient.invalidateQueries({
              queryKey: ['lottery', 'draws'],
            });
          }}
        />
      }
    >
      <PageHeading
        eyebrow="YOUR EVERYDAY TOOLS"
        title={user ? `${greeting}, ${user.username}.` : `${greeting}.`}
        subtitle="A little less to keep in your head."
      />
      <DrawQuickReference />
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
