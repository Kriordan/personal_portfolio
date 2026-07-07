import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Redirect, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TextInput,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { listsApi, listsKeys, type ListSummary } from '@/lib/lists-api';

function ListRow({ list, onPress }: { list: ListSummary; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}
    >
      <ThemedText>{list.title}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        ›
      </ThemedText>
    </Pressable>
  );
}

export default function ListsScreen() {
  const theme = useTheme();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();
  const [newTitle, setNewTitle] = useState('');

  const overviewQuery = useQuery({
    queryKey: listsKeys.overview(),
    queryFn: listsApi.getLists,
    enabled: isAuthenticated === true,
  });

  const createMutation = useMutation({
    mutationFn: (title: string) => listsApi.createList(title),
    onSuccess: ({ list }) => {
      setNewTitle('');
      queryClient.invalidateQueries({ queryKey: listsKeys.overview() });
      router.push(`/lists/${list.id}`);
    },
  });

  const canCreate = newTitle.trim().length > 0 && !createMutation.isPending;

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (overviewQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (overviewQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Couldn’t load your lists.</ThemedText>
        <Pressable style={styles.button} onPress={() => overviewQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const { owned, shared } = overviewQuery.data;

  return (
    <ThemedView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={overviewQuery.isRefetching}
            onRefresh={() => overviewQuery.refetch()}
          />
        }
      >
        <ThemedView style={styles.createRow}>
          <TextInput
            style={[styles.input, { color: theme.text, backgroundColor: theme.backgroundElement }]}
            placeholder="New list title"
            placeholderTextColor={theme.textSecondary}
            value={newTitle}
            onChangeText={setNewTitle}
            onSubmitEditing={() => canCreate && createMutation.mutate(newTitle.trim())}
            editable={!createMutation.isPending}
          />
          <Pressable
            style={[styles.button, !canCreate && styles.buttonDisabled]}
            disabled={!canCreate}
            onPress={() => createMutation.mutate(newTitle.trim())}
          >
            {createMutation.isPending ? (
              <ActivityIndicator color="#ffffff" />
            ) : (
              <ThemedText type="smallBold" style={styles.buttonText}>
                Create
              </ThemedText>
            )}
          </Pressable>
        </ThemedView>
        {createMutation.isError && (
          <ThemedText type="small" style={styles.error}>
            {createMutation.error instanceof Error
              ? createMutation.error.message
              : 'Failed to create list.'}
          </ThemedText>
        )}

        <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
          MY LISTS
        </ThemedText>
        {owned.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            No lists yet. Create one above.
          </ThemedText>
        ) : (
          owned.map((list) => (
            <ListRow key={list.id} list={list} onPress={() => router.push(`/lists/${list.id}`)} />
          ))
        )}

        {shared.length > 0 && (
          <>
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
              SHARED WITH ME
            </ThemedText>
            {shared.map((list) => (
              <ListRow key={list.id} list={list} onPress={() => router.push(`/lists/${list.id}`)} />
            ))}
          </>
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
  createRow: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
  input: {
    flex: 1,
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
    fontSize: 16,
  },
  sectionHeader: {
    marginTop: Spacing.three,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.two,
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
  error: {
    color: '#d64545',
  },
});
