import { useQuery } from '@tanstack/react-query';
import { Redirect, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
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
import { learningApi, learningKeys, type ReviewCard } from '@/lib/learning-api';
import { ApiError } from '@/lib/api-client';

function CardRow({ card }: { card: ReviewCard }) {
  const theme = useTheme();
  const [revealed, setRevealed] = useState(false);

  return (
    <Pressable
      onPress={() => setRevealed((current) => !current)}
      style={({ pressed }) => [
        styles.card,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}
    >
      <View style={styles.cardHeader}>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {card.type.toUpperCase()}
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {revealed ? 'Hide answer' : 'Show answer'}
        </ThemedText>
      </View>
      <ThemedText>{card.prompt}</ThemedText>
      {revealed && (
        <ThemedText type="small" themeColor="textSecondary">
          {card.response}
        </ThemedText>
      )}
    </Pressable>
  );
}

export default function NoteDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const noteId = id ?? '';
  const { isAuthenticated } = useAuth();

  const noteQuery = useQuery({
    queryKey: learningKeys.note(noteId),
    queryFn: () => learningApi.getNote(noteId),
    enabled: noteId.length > 0 && isAuthenticated === true,
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (noteQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (noteQuery.isError) {
    const notFound = noteQuery.error instanceof ApiError && noteQuery.error.status === 404;
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">
          {notFound
            ? 'Note not found.'
            : noteQuery.error instanceof Error
              ? noteQuery.error.message
              : 'Couldn’t load note.'}
        </ThemedText>
        {!notFound && (
          <Pressable style={styles.button} onPress={() => noteQuery.refetch()}>
            <ThemedText type="smallBold" style={styles.buttonText}>
              Retry
            </ThemedText>
          </Pressable>
        )}
      </ThemedView>
    );
  }

  const note = noteQuery.data.note;

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen options={{ title: note.title }} />
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={noteQuery.isRefetching}
            onRefresh={() => noteQuery.refetch()}
          />
        }
      >
        {note.tags && note.tags.length > 0 && (
          <ThemedText type="small" themeColor="textSecondary">
            {note.tags.join(' · ')}
          </ThemedText>
        )}
        {note.summary ? <ThemedText>{note.summary}</ThemedText> : null}

        <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
          CARDS ({note.flashcards.length})
        </ThemedText>
        {note.flashcards.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            This note has no cards.
          </ThemedText>
        ) : (
          note.flashcards.map((card) => <CardRow key={card.card_id} card={card} />)
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
  card: {
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
    gap: Spacing.two,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.two,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    color: '#ffffff',
  },
});
