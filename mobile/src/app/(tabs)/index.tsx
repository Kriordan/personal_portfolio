import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, StyleSheet, View } from 'react-native';
import {
  Card,
  InlineError,
  NativeAction,
  NavRow,
  Screen,
  SectionHeading,
} from '@/components/screen';
import { DrawQuickReference } from '@/components/lottery-content';
import { ThemedText } from '@/components/themed-text';
import { useQueryClient } from '@tanstack/react-query';
import { mobileTools } from '@/constants/tools';
import { useConcepts } from '@/hooks/use-concepts';
import { useListsOverview } from '@/hooks/use-lists';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { mostRecentLesson, type ConceptSummary } from '@/lib/concept-model';

const wishlist = mobileTools.find((tool) => tool.href === '/wishlist');

function LearningCard({ lesson }: { lesson?: ConceptSummary }) {
  const router = useRouter();
  return (
    <Card>
      <View style={styles.learningHeading}>
        <ThemedText type="subtitle" accessibilityRole="header">
          Learning
        </ThemedText>
        {lesson ? (
          <Pressable
            accessibilityRole="link"
            onPress={() => router.push('/learning')}
            style={styles.link}
          >
            <ThemedText type="smallBold" themeColor="accent">
              All lessons
            </ThemedText>
          </Pressable>
        ) : null}
      </View>
      {lesson ? (
        <View style={styles.lesson}>
          <ThemedText>{lesson.title}</ThemedText>
          {lesson.draft ? (
            <ThemedText type="small" themeColor="textSecondary">
              Private pilot · Draft content
            </ThemedText>
          ) : null}
        </View>
      ) : null}
      <NativeAction
        label={lesson ? 'Continue lesson' : 'Open Learning'}
        onPress={() => router.push(
          lesson
            ? { pathname: '/learning/concepts/[id]', params: { id: lesson.id } }
            : '/learning',
        )}
      />
    </Card>
  );
}

export default function HomeScreen() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const lists = useListsOverview();
  const concepts = useConcepts(user?.id);
  const learningUnavailable =
    concepts.error instanceof ApiError &&
    (concepts.error.status === 403 || concepts.error.status === 404);
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  async function refresh() {
    setRefreshing(true);
    try {
      await Promise.all([
        lists.refetch(),
        user && concepts.refetch(),
        queryClient.invalidateQueries({ queryKey: ['lottery', 'draws'] }),
      ]);
    } finally {
      setRefreshing(false);
    }
  }
  return (
    <Screen
      tab
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => void refresh()}
        />
      }
    >
      {learningUnavailable ? null : (
        <LearningCard lesson={mostRecentLesson(concepts.data?.concepts ?? [])} />
      )}
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
      <SectionHeading>Other tools</SectionHeading>
      {wishlist ? (
        <NavRow
          title={wishlist.title}
          subtitle={wishlist.description}
          href={wishlist.href}
          badge={wishlist.badge}
        />
      ) : null}
      <NativeAction
        label="Explore all tools"
        secondary
        onPress={() => router.navigate('/tools')}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  learningHeading: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    columnGap: 12,
  },
  lesson: { gap: 2 },
  link: { minHeight: 44, justifyContent: 'center' },
});
