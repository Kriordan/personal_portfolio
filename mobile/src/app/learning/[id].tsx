import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { FlatList, RefreshControl, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  LearningText,
  LearningUnavailable,
  StudyCard,
  learningStyles,
} from '@/components/learning-content';
import {
  InlineError,
  NativeAction,
  PageHeading,
  ScreenState,
  screenStyles,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useLearningNote } from '@/hooks/use-learning';
import { useTheme } from '@/hooks/use-theme';
import { ApiError } from '@/lib/api-client';
import { validNoteId, type ReviewCard } from '@/lib/learning-model';

const keyForCard = (card: ReviewCard) => card.card_id;
const renderCard = ({ item }: { item: ReviewCard }) => (
  <StudyCard card={item} />
);
export default function NoteDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const noteId = typeof id === 'string' ? id : '';
  const query = useLearningNote(noteId);
  const theme = useTheme();
  const router = useRouter();
  const [refreshing, setRefreshing] = useState(false);
  const refresh = () => {
    setRefreshing(true);
    void query.refetch().finally(() => setRefreshing(false));
  };
  if (
    !validNoteId(noteId) ||
    (query.error instanceof ApiError && query.error.status === 404)
  )
    return <LearningUnavailable />;
  if (!query.data && query.isPending)
    return (
      <ScreenState
        loading={!query.isPaused}
        title={query.isPaused ? 'You’re offline' : 'Loading note'}
        message={query.isPaused ? 'Reconnect to load this note.' : undefined}
      />
    );
  if (!query.data)
    return (
      <ScreenState
        title="Couldn’t load this note"
        message="Check your connection and try again."
        onRetry={refresh}
      />
    );
  const note = query.data.note;
  return (
    <SafeAreaView
      edges={['left', 'right', 'bottom']}
      style={[learningStyles.fill, { backgroundColor: theme.background }]}
    >
      <Stack.Screen options={{ title: 'Learning note' }} />
      <FlatList
        data={note.flashcards}
        renderItem={renderCard}
        keyExtractor={keyForCard}
        contentContainerStyle={screenStyles.collection}
        contentInsetAdjustmentBehavior="automatic"
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} />
        }
        ListHeaderComponent={
          <View style={screenStyles.gap}>
            <PageHeading
              title={note.title}
              subtitle={`${note.flashcard_count} cards · ${note.due_count} due for you`}
            />
            {note.tags?.length ? (
              <ThemedText themeColor="textSecondary">
                {note.tags.join(' · ')}
              </ThemedText>
            ) : null}
            {note.summary ? <LearningText text={note.summary} /> : null}
            {note.due_count ? (
              <NativeAction
                label={`Review ${Math.min(20, note.due_count)} due cards in this note`}
                onPress={() =>
                  router.push({
                    pathname: '/learning/review',
                    params: { note_id: noteId },
                  })
                }
              />
            ) : (
              <ThemedText themeColor="textSecondary">
                No cards due in this note.
              </ThemedText>
            )}
            <ThemedText type="small" themeColor="textSecondary">
              Show answers to study freely. Only rating during a review changes
              your progress.
            </ThemedText>
            {query.isError ? (
              <InlineError
                message="Couldn’t refresh. Showing the last loaded note and counts."
                onRetry={refresh}
              />
            ) : null}
            {query.isPaused ? (
              <ThemedText themeColor="textSecondary">
                You’re offline. Showing the last loaded note.
              </ThemedText>
            ) : null}
            <ThemedText
              type="subtitle"
              accessibilityRole="header"
              style={learningStyles.count}
            >
              Cards
            </ThemedText>
          </View>
        }
        ListEmptyComponent={
          <View style={learningStyles.empty}>
            <ThemedText type="subtitle">This note has no cards</ThemedText>
          </View>
        }
      />
    </SafeAreaView>
  );
}
