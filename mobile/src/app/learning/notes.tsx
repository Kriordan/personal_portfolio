import { Host } from '@expo/ui';
import { useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, RefreshControl, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import {
  LearningAccountState,
  LearningNoteRow,
  learningStyles,
  noteKey,
} from '@/components/learning-content';
import { LearningStatus } from '@/components/learning-status';
import { NativeChoice } from '@/components/native-choice';
import { NativeField } from '@/components/native-form';
import {
  Card,
  InlineError,
  NativeAction,
  PageHeading,
  ScreenState,
  screenStyles,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useLearningActivity, useLearningNotes } from '@/hooks/use-learning';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import {
  browseNotes,
  NOTE_FILTERS,
  NOTE_SORTS,
  type NoteFilter,
  type NoteSort,
  type NoteSummary,
} from '@/lib/learning-model';

const renderNote = ({ item }: { item: NoteSummary }) => (
  <LearningNoteRow note={item} />
);
export default function LearningScreen() {
  const { user } = useAuth();
  return user ? (
    <LearningOverview userId={user.id} />
  ) : (
    <LearningAccountState />
  );
}
function LearningOverview({ userId }: { userId: number }) {
  const query = useLearningNotes();
  const activity = useLearningActivity(userId);
  const theme = useTheme();
  const router = useRouter();
  const search = useNativeText();
  const [sort, setSort] = useState<NoteSort>('due');
  const [filter, setFilter] = useState<NoteFilter>('all');
  const [refreshing, setRefreshing] = useState(false);
  const notes = useMemo(
    () => browseNotes(query.data?.notes ?? [], search.text, filter, sort),
    [query.data?.notes, search.text, filter, sort],
  );
  const refresh = () => {
    setRefreshing(true);
    void query.refetch().finally(() => setRefreshing(false));
  };
  if (!query.data && query.isPending)
    return (
      <ScreenState
        loading={!query.isPaused}
        title={query.isPaused ? 'You’re offline' : 'Loading Learning'}
        message={
          query.isPaused
            ? 'Reconnect to load your notes and progress.'
            : undefined
        }
      />
    );
  if (!query.data)
    return (
      <ScreenState
        title="Couldn’t load Learning"
        message="Check your connection and try again."
        onRetry={refresh}
      />
    );
  const totalDue = query.data.total_due;
  return (
    <SafeAreaView
      edges={['left', 'right', 'bottom']}
      style={[learningStyles.fill, { backgroundColor: theme.background }]}
    >
      <FlatList
        data={notes}
        renderItem={renderNote}
        keyExtractor={noteKey}
        contentContainerStyle={screenStyles.collection}
        contentInsetAdjustmentBehavior="automatic"
        automaticallyAdjustKeyboardInsets
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} />
        }
        ListHeaderComponent={
          <View style={screenStyles.gap}>
            <PageHeading
              title="Learning"
              subtitle="Shared notes. Your own progress, one review at a time."
            />
            <Card>
              <ThemedText type="subtitle">
                {totalDue ? `${totalDue} cards due` : 'No cards due'}
              </ThemedText>
              <ThemedText themeColor="textSecondary">
                {totalDue
                  ? 'Review a short session from all your due notes.'
                  : 'You can still browse notes and study their answers.'}
              </ThemedText>
              {totalDue ? (
                <NativeAction
                  label={`Review ${Math.min(20, totalDue)} cards · All notes`}
                  disabled={!activity.ready || !!activity.attempt}
                  onPress={() => router.push('/learning/review')}
                />
              ) : null}
            </Card>
            <LearningStatus activity={activity} />
            {query.isError ? (
              <InlineError
                message="Couldn’t refresh. Showing the last loaded notes and counts."
                onRetry={refresh}
              />
            ) : null}
            {query.isPaused ? (
              <ThemedText themeColor="textSecondary">
                You’re offline. Showing the last loaded notes and counts.
              </ThemedText>
            ) : null}
            <Host matchContents={{ vertical: true }}>
              <NativeField
                label="Search notes"
                placeholder="Title, summary, or tag"
                {...search.input}
                autoCorrect={false}
              />
            </Host>
            {search.text ? (
              <NativeAction
                label="Clear search"
                secondary
                onPress={search.clear}
              />
            ) : null}
            <NativeChoice
              label="Show"
              value={filter}
              options={NOTE_FILTERS}
              onChange={setFilter}
            />
            <NativeChoice
              label="Sort"
              value={sort}
              options={NOTE_SORTS}
              onChange={setSort}
            />
            <ThemedText
              type="smallBold"
              themeColor="textSecondary"
              style={learningStyles.count}
            >
              {notes.length} of {query.data.notes.length} notes
            </ThemedText>
          </View>
        }
        ListEmptyComponent={
          <View style={learningStyles.empty}>
            <ThemedText type="subtitle">
              {query.data.notes.length ? 'No matching notes' : 'No notes yet'}
            </ThemedText>
            <ThemedText themeColor="textSecondary">
              {query.data.notes.length
                ? 'Try another search or show all notes.'
                : 'Learning notes will appear here when they are added to the collection.'}
            </ThemedText>
            {query.data.notes.length ? (
              <NativeAction
                label="Show all notes"
                secondary
                onPress={() => {
                  search.clear();
                  setFilter('all');
                }}
              />
            ) : null}
          </View>
        }
      />
    </SafeAreaView>
  );
}
