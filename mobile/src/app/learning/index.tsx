import { useRouter } from 'expo-router';
import { RefreshControl } from 'react-native';
import { LearningAccountState } from '@/components/learning-content';
import { LearningStatus } from '@/components/learning-status';
import { StudyStatus } from '@/components/concept-workspace';
import {
  Card,
  InlineError,
  NativeAction,
  NavRow,
  PageHeading,
  Screen,
  ScreenState,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useConcepts, useConceptStudy } from '@/hooks/use-concepts';
import { useLearningActivity } from '@/hooks/use-learning';
import { useAuth } from '@/lib/auth-context';
import { ApiError } from '@/lib/api-client';

export default function LearningHome() {
  const { user } = useAuth();
  return user ? (
    <ConceptLibrary key={user.id} userId={user.id} />
  ) : (
    <LearningAccountState />
  );
}
function ConceptLibrary({ userId }: { userId: number }) {
  const router = useRouter();
  const query = useConcepts(userId);
  const study = useConceptStudy(userId);
  const ratings = useLearningActivity(userId);
  const reload = () => {
    void query.refetch();
  };
  if (query.error instanceof ApiError && query.error.status === 404)
    return (
      <ScreenState
        title="Learning unavailable"
        message="This account or app version cannot open the private concept pilot yet."
        onRetry={reload}
      />
    );
  if (!query.data && query.isPending)
    return (
      <ScreenState
        loading={!query.isPaused}
        title={query.isPaused ? 'You’re offline' : 'Loading Learning'}
        message="Connect to load your concepts and saved progress."
      />
    );
  if (!query.data)
    return (
      <ScreenState
        title="Couldn’t load Learning"
        message="Your saved progress is still available. Reconnect and try again."
        onRetry={reload}
      />
    );
  return (
    <Screen
      refreshControl={
        <RefreshControl refreshing={query.isFetching} onRefresh={reload} />
      }
    >
      <PageHeading
        title="Learning"
        subtitle="Understand an idea. Recall it. Put it to work."
      />
      <StudyStatus activity={study} onReload={reload} />
      <LearningStatus activity={ratings} />
      {query.isError ? (
        <InlineError
          message="Couldn’t refresh your progress. Showing the last loaded view."
          onRetry={reload}
        />
      ) : null}
      {query.data.concepts.map((item) => (
        <Card key={item.id}>
          {item.draft ? (
            <ThemedText type="small" themeColor="textSecondary">
              Private pilot · Draft content
            </ThemedText>
          ) : null}
          <ThemedText type="subtitle" accessibilityRole="header">
            {item.title}
          </ThemedText>
          <ThemedText themeColor="textSecondary">{item.summary}</ThemedText>
          <ThemedText type="small">
            {item.progress
              ? item.due_count + ' questions due'
              : 'Start when you’re ready'}
          </ThemedText>
          <NativeAction
            label={item.progress ? 'Continue lesson' : 'Explore concept'}
            onPress={() =>
              router.push({
                pathname: '/learning/concepts/[id]',
                params: { id: item.id },
              })
            }
          />
          {item.progress ? (
            <NativeAction
              label="Review"
              secondary
              onPress={() =>
                router.push({
                  pathname: '/learning/concepts/[id]/review',
                  params: { id: item.id },
                })
              }
            />
          ) : null}
        </Card>
      ))}
      {!query.data.concepts.length ? (
        <ThemedText>No concepts are available yet.</ThemedText>
      ) : null}
      <NavRow
        title="Notes and flashcards"
        subtitle="Browse your existing notes and review cards."
        href="/learning/notes"
      />
    </Screen>
  );
}
