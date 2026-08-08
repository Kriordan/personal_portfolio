import { useQuery } from '@tanstack/react-query';
import { Redirect, useRouter } from 'expo-router';
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
import { learningApi, learningKeys, type NoteSummary } from '@/lib/learning-api';

function NoteRow({ note, onPress }: { note: NoteSummary; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}
    >
      <View style={styles.rowBody}>
        <ThemedText>{note.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {note.flashcard_count} card{note.flashcard_count === 1 ? '' : 's'}
          {note.tags && note.tags.length > 0 ? ` · ${note.tags.join(', ')}` : ''}
        </ThemedText>
      </View>
      {note.due_count > 0 && (
        <View style={styles.dueBadge}>
          <ThemedText type="smallBold" style={styles.dueBadgeText}>
            {note.due_count}
          </ThemedText>
        </View>
      )}
      <ThemedText type="small" themeColor="textSecondary">
        ›
      </ThemedText>
    </Pressable>
  );
}

export default function LearningScreen() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const notesQuery = useQuery({
    queryKey: learningKeys.notes(),
    queryFn: learningApi.getNotes,
    enabled: isAuthenticated === true,
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (notesQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (notesQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Couldn’t load your notes.</ThemedText>
        <Pressable style={styles.button} onPress={() => notesQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const { notes, total_due: totalDue } = notesQuery.data;

  return (
    <ThemedView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={notesQuery.isRefetching}
            onRefresh={() => notesQuery.refetch()}
          />
        }
      >
        <Pressable
          style={[styles.button, totalDue === 0 && styles.buttonDisabled]}
          disabled={totalDue === 0}
          onPress={() => router.push('/learning/review')}
        >
          <ThemedText type="smallBold" style={styles.buttonText}>
            {totalDue > 0
              ? `Start Review (${totalDue} due)`
              : 'No cards due'}
          </ThemedText>
        </Pressable>

        <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
          NOTES
        </ThemedText>
        {notes.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            No notes yet.
          </ThemedText>
        ) : (
          notes.map((note) => (
            <NoteRow key={note.id} note={note} onPress={() => router.push(`/learning/${note.id}`)} />
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
  dueBadge: {
    backgroundColor: '#3c87f7',
    borderRadius: 999,
    minWidth: 24,
    paddingHorizontal: Spacing.two,
    paddingVertical: Spacing.half,
    alignItems: 'center',
  },
  dueBadgeText: {
    color: '#ffffff',
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#ffffff',
  },
});
