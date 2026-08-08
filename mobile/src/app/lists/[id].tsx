import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Redirect, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import {
  emitListEvent,
  useListRoom,
  type SocketStatus,
} from '@/lib/list-socket';
import {
  listsApi,
  listsKeys,
  type ListCategory,
  type ListDetail,
  type ListItem,
} from '@/lib/lists-api';

/** Immutable cache helpers so realtime events and mutations update in place. */

function withItemToggled(detail: ListDetail, itemId: number, completed: boolean): ListDetail {
  return {
    ...detail,
    categories: detail.categories.map((category) => ({
      ...category,
      items: category.items.map((item) => (item.id === itemId ? { ...item, completed } : item)),
    })),
  };
}

function withItemAdded(detail: ListDetail, categoryId: number, item: ListItem): ListDetail {
  return {
    ...detail,
    categories: detail.categories.map((category) => {
      if (category.id !== categoryId) return category;
      if (category.items.some((existing) => existing.id === item.id)) return category;
      return { ...category, items: [...category.items, item] };
    }),
  };
}

function withCategoryAdded(detail: ListDetail, category: ListCategory): ListDetail {
  if (detail.categories.some((existing) => existing.id === category.id)) return detail;
  return { ...detail, categories: [...detail.categories, { ...category, items: category.items ?? [] }] };
}

function ConnectionBadge({ status }: { status: SocketStatus }) {
  const label =
    status === 'connected' ? 'Live' : status === 'connecting' ? 'Connecting…' : 'Offline';
  const color = status === 'connected' ? '#2e9e5b' : status === 'connecting' ? '#b58a2e' : '#d64545';
  return (
    <View style={styles.badge}>
      <View style={[styles.badgeDot, { backgroundColor: color }]} />
      <ThemedText type="small" themeColor="textSecondary">
        {label}
      </ThemedText>
    </View>
  );
}

function ItemRow({
  item,
  onToggle,
  disabled,
}: {
  item: ListItem;
  onToggle: () => void;
  disabled: boolean;
}) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onToggle}
      disabled={disabled}
      style={({ pressed }) => [
        styles.itemRow,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}
    >
      <ThemedText type="small" style={styles.checkbox}>
        {item.completed ? '☑' : '☐'}
      </ThemedText>
      <View style={styles.itemBody}>
        <ThemedText style={item.completed && styles.completedText}>
          {item.name}
          {item.quantity ? ` (${item.quantity})` : ''}
        </ThemedText>
        {item.notes ? (
          <ThemedText type="small" themeColor="textSecondary">
            {item.notes}
          </ThemedText>
        ) : null}
      </View>
    </Pressable>
  );
}

function CategorySection({
  listId,
  category,
}: {
  listId: number;
  category: ListCategory;
}) {
  const theme = useTheme();
  const queryClient = useQueryClient();
  const [newItemName, setNewItemName] = useState('');

  const toggleMutation = useMutation({
    mutationFn: (item: ListItem) => listsApi.toggleItem(listId, item.id),
    onSuccess: ({ completed }, item) => {
      queryClient.setQueryData<{ list: ListDetail }>(listsKeys.detail(listId), (cached) =>
        cached ? { list: withItemToggled(cached.list, item.id, completed) } : cached,
      );
      emitListEvent('item_toggled', { list_id: listId, item_id: item.id, completed });
    },
  });

  const addItemMutation = useMutation({
    mutationFn: (name: string) => listsApi.addItem(listId, { name, category_id: category.id }),
    onSuccess: ({ item }) => {
      setNewItemName('');
      queryClient.setQueryData<{ list: ListDetail }>(listsKeys.detail(listId), (cached) =>
        cached ? { list: withItemAdded(cached.list, category.id, item) } : cached,
      );
      emitListEvent('item_added', { list_id: listId, category_id: category.id, item });
    },
  });

  const canAddItem = newItemName.trim().length > 0 && !addItemMutation.isPending;
  const sortedItems = [...category.items].sort((a, b) => a.ordering - b.ordering);
  const pending = sortedItems.filter((item) => !item.completed);
  const completed = sortedItems.filter((item) => item.completed);

  return (
    <View style={styles.category}>
      <ThemedText type="smallBold" themeColor="textSecondary">
        {category.name.toUpperCase()}
      </ThemedText>

      {[...pending, ...completed].map((item) => (
        <ItemRow
          key={item.id}
          item={item}
          disabled={toggleMutation.isPending}
          onToggle={() => toggleMutation.mutate(item)}
        />
      ))}

      <View style={styles.addRow}>
        <TextInput
          style={[styles.input, { color: theme.text, backgroundColor: theme.backgroundElement }]}
          placeholder="Add item"
          placeholderTextColor={theme.textSecondary}
          value={newItemName}
          onChangeText={setNewItemName}
          onSubmitEditing={() => canAddItem && addItemMutation.mutate(newItemName.trim())}
          editable={!addItemMutation.isPending}
        />
        <Pressable
          style={[styles.button, !canAddItem && styles.buttonDisabled]}
          disabled={!canAddItem}
          onPress={() => addItemMutation.mutate(newItemName.trim())}
        >
          <ThemedText type="smallBold" style={styles.buttonText}>
            Add
          </ThemedText>
        </Pressable>
      </View>
      {(toggleMutation.isError || addItemMutation.isError) && (
        <ThemedText type="small" style={styles.error}>
          {(toggleMutation.error ?? addItemMutation.error) instanceof Error
            ? ((toggleMutation.error ?? addItemMutation.error) as Error).message
            : 'Something went wrong.'}
        </ThemedText>
      )}
    </View>
  );
}

export default function ListDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const listId = Number(id);
  const theme = useTheme();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();
  const [newCategoryName, setNewCategoryName] = useState('');

  const detailQuery = useQuery({
    queryKey: listsKeys.detail(listId),
    queryFn: () => listsApi.getList(listId),
    enabled: Number.isFinite(listId) && isAuthenticated === true,
  });

  const socketStatus = useListRoom(
    listId,
    {
      onItemToggled: ({ item_id, completed }) => {
        queryClient.setQueryData<{ list: ListDetail }>(listsKeys.detail(listId), (cached) =>
          cached ? { list: withItemToggled(cached.list, item_id, completed) } : cached,
        );
      },
      onItemAdded: ({ category_id, item }) => {
        queryClient.setQueryData<{ list: ListDetail }>(listsKeys.detail(listId), (cached) =>
          cached ? { list: withItemAdded(cached.list, category_id, item) } : cached,
        );
      },
      onCategoryAdded: ({ category }) => {
        queryClient.setQueryData<{ list: ListDetail }>(listsKeys.detail(listId), (cached) =>
          cached ? { list: withCategoryAdded(cached.list, category) } : cached,
        );
      },
      // Reorders and settings changes touch many rows; refetching is simpler
      // than replaying the payload and matches the source of truth.
      onItemsReordered: () => {
        queryClient.invalidateQueries({ queryKey: listsKeys.detail(listId) });
      },
      onCategoriesReordered: () => {
        queryClient.invalidateQueries({ queryKey: listsKeys.detail(listId) });
      },
      onSettingsUpdated: () => {
        queryClient.invalidateQueries({ queryKey: listsKeys.detail(listId) });
      },
      // Refetch on every (re)join to pick up anything missed while disconnected.
      onJoined: () => {
        queryClient.invalidateQueries({ queryKey: listsKeys.detail(listId) });
      },
    },
    { enabled: Number.isFinite(listId) && isAuthenticated === true },
  );

  const addCategoryMutation = useMutation({
    mutationFn: (name: string) => listsApi.addCategory(listId, name),
    onSuccess: ({ category }) => {
      setNewCategoryName('');
      queryClient.setQueryData<{ list: ListDetail }>(listsKeys.detail(listId), (cached) =>
        cached ? { list: withCategoryAdded(cached.list, category) } : cached,
      );
      emitListEvent('category_added', { list_id: listId, category });
    },
  });

  const canAddCategory = newCategoryName.trim().length > 0 && !addCategoryMutation.isPending;

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (detailQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (detailQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">
          {detailQuery.error instanceof Error ? detailQuery.error.message : 'Couldn’t load list.'}
        </ThemedText>
        <Pressable style={styles.button} onPress={() => detailQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const list = detailQuery.data.list;
  const categories = [...list.categories].sort((a, b) => a.ordering - b.ordering);

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen
        options={{
          title: list.title,
          headerRight: () => <ConnectionBadge status={socketStatus} />,
        }}
      />
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={detailQuery.isRefetching}
            onRefresh={() => detailQuery.refetch()}
          />
        }
      >
        {categories.length === 0 && (
          <ThemedText type="small" themeColor="textSecondary">
            No categories yet. Add one below to start adding items.
          </ThemedText>
        )}

        {categories.map((category) => (
          <CategorySection key={category.id} listId={listId} category={category} />
        ))}

        <View style={styles.addRow}>
          <TextInput
            style={[styles.input, { color: theme.text, backgroundColor: theme.backgroundElement }]}
            placeholder="New category"
            placeholderTextColor={theme.textSecondary}
            value={newCategoryName}
            onChangeText={setNewCategoryName}
            onSubmitEditing={() => canAddCategory && addCategoryMutation.mutate(newCategoryName.trim())}
            editable={!addCategoryMutation.isPending}
          />
          <Pressable
            style={[styles.button, !canAddCategory && styles.buttonDisabled]}
            disabled={!canAddCategory}
            onPress={() => addCategoryMutation.mutate(newCategoryName.trim())}
          >
            <ThemedText type="smallBold" style={styles.buttonText}>
              Add
            </ThemedText>
          </Pressable>
        </View>
        {addCategoryMutation.isError && (
          <ThemedText type="small" style={styles.error}>
            {addCategoryMutation.error instanceof Error
              ? addCategoryMutation.error.message
              : 'Failed to add category.'}
          </ThemedText>
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
    gap: Spacing.three,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.one,
  },
  badgeDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  category: {
    gap: Spacing.two,
  },
  itemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.two,
  },
  checkbox: {
    fontSize: 20,
  },
  itemBody: {
    flex: 1,
  },
  completedText: {
    textDecorationLine: 'line-through',
    opacity: 0.6,
  },
  addRow: {
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
