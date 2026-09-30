import { Picker, Text } from '@expo/ui';
import { Stack, useLocalSearchParams } from 'expo-router';
import { memo, useCallback, useState } from 'react';
import {
  AccessibilityInfo,
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SectionList,
  StyleSheet,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { NativeField, NativeFormSheet } from '@/components/native-form';
import {
  InlineError,
  NativeAction,
  PageHeading,
  ScreenState,
  SectionHeading,
  screenStyles,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useGroceryList } from '@/hooks/use-lists';
import { useSubmission } from '@/hooks/use-submission';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { grocerySections } from '@/lib/lists-cache';
import { ApiError } from '@/lib/api-client';
import type { ListItem } from '@/lib/lists-api';

const ItemRow = memo(function ItemRow({
  item,
  pending,
  disabled,
  onToggle,
}: {
  item: ListItem;
  pending: boolean;
  disabled: boolean;
  onToggle: (item: ListItem) => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="checkbox"
      accessibilityLabel={[item.name, item.quantity, item.notes]
        .filter(Boolean)
        .join(', ')}
      accessibilityState={{ checked: item.completed, disabled, busy: pending }}
      accessibilityHint={
        item.completed ? 'Mark as still needed' : 'Mark as completed'
      }
      disabled={disabled}
      onPress={() => onToggle(item)}
      style={({ pressed }) => [
        styles.item,
        {
          backgroundColor: pressed
            ? theme.backgroundSelected
            : theme.backgroundElement,
        },
      ]}
    >
      <View
        accessible={false}
        style={[
          styles.checkbox,
          {
            borderColor: item.completed ? theme.accent : theme.textSecondary,
            backgroundColor: item.completed ? theme.accent : 'transparent',
          },
        ]}
      >
        {pending ? (
          <ActivityIndicator
            size="small"
            color={item.completed ? theme.background : theme.accent}
          />
        ) : item.completed ? (
          <ThemedText style={{ color: theme.background }} accessible={false}>
            ✓
          </ThemedText>
        ) : null}
      </View>
      <View style={styles.itemBody}>
        <ThemedText
          style={item.completed ? styles.completed : undefined}
          themeColor={item.completed ? 'textSecondary' : 'text'}
        >
          {item.name}
        </ThemedText>
        {item.quantity ? (
          <ThemedText type="small" themeColor="textSecondary">
            {item.quantity}
          </ThemedText>
        ) : null}
        {item.notes ? (
          <ThemedText type="small" themeColor="textSecondary">
            {item.notes}
          </ThemedText>
        ) : null}
      </View>
    </Pressable>
  );
});

export default function ListDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  // A new route id gets fresh local drafts, even when Router reuses the screen instance.
  return <GroceryDetail key={id} listId={Number(id)} />;
}

function GroceryDetail({ listId }: { listId: number }) {
  const { query, status, validId, addCategory, addItem, toggle } =
    useGroceryList(listId);
  const theme = useTheme();
  const categorySubmission = useSubmission();
  const itemSubmission = useSubmission();
  const toggleSubmission = useSubmission();
  const [form, setForm] = useState<'category' | 'item' | null>(null);
  const categoryName = useNativeText();
  const [categoryId, setCategoryId] = useState<number | null>(null);
  const itemName = useNativeText();
  const quantity = useNativeText();
  const notes = useNativeText();

  const { run: runToggle } = toggleSubmission;
  const { mutateAsync: toggleItem } = toggle;
  const onToggle = useCallback(
    (item: ListItem) => {
      void runToggle(async () => {
        const result = await toggleItem(item.id);
        AccessibilityInfo.announceForAccessibility(
          `${item.name}, ${result.completed ? 'completed' : 'still needed'}`,
        );
      });
    },
    [runToggle, toggleItem],
  );

  if (!validId)
    return (
      <ScreenState
        title="Invalid list link"
        message="Open Grocery to choose one of your lists."
      />
    );
  if (!query.data && query.isPending)
    return (
      <ScreenState
        loading={!query.isPaused}
        title={query.isPaused ? 'You’re offline' : 'Loading your list'}
        message={query.isPaused ? 'Reconnect to load this list.' : undefined}
      />
    );
  if (
    !query.data ||
    (query.error instanceof ApiError && [403, 404].includes(query.error.status))
  )
    return (
      <ScreenState
        title="Couldn’t open this list"
        message={
          query.error instanceof ApiError
            ? query.error.message
            : 'Check your connection and access to this list.'
        }
        onRetry={() => void query.refetch()}
      />
    );

  const { list } = query.data;
  const sections = grocerySections(list);
  const items = list.categories.flatMap((category) => category.items);
  const completed = items.filter((item) => item.completed).length;
  const selectedCategory = list.categories.some(
    (category) => category.id === categoryId,
  )
    ? categoryId!
    : list.categories[0]?.id;
  const connectionLabel =
    status === 'connected'
      ? 'Live updates connected'
      : status === 'connecting'
        ? 'Connecting to live updates…'
        : 'Live updates disconnected · Pull to refresh';
  const submitCategory = () => {
    const currentName = categoryName.read();
    if (!currentName.trim()) return;
    void categorySubmission.run(async () => {
      const result = await addCategory.mutateAsync(currentName.trim());
      categoryName.clear();
      setCategoryId(result.category.id);
      setForm(null);
    });
  };
  const submitItem = () => {
    const name = itemName.read().trim();
    const currentQuantity = quantity.read().trim();
    const currentNotes = notes.read().trim();
    if (!name || !selectedCategory) return;
    void itemSubmission.run(async () => {
      await addItem.mutateAsync({
        name,
        category_id: selectedCategory,
        quantity: currentQuantity || undefined,
        notes: currentNotes || undefined,
      });
      itemName.clear();
      quantity.clear();
      notes.clear();
      setForm(null);
    });
  };

  return (
    <SafeAreaView
      edges={['left', 'right', 'bottom']}
      style={[styles.screen, { backgroundColor: theme.background }]}
    >
      <Stack.Screen options={{ title: list.title }} />
      <SectionList
        sections={sections}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={screenStyles.collection}
        contentInsetAdjustmentBehavior="automatic"
        stickySectionHeadersEnabled={false}
        initialNumToRender={16}
        windowSize={7}
        refreshControl={
          <RefreshControl
            refreshing={query.isRefetching}
            onRefresh={() => void query.refetch()}
          />
        }
        ListHeaderComponent={
          <View style={screenStyles.gap}>
            <PageHeading
              title={list.title}
              subtitle={
                items.length
                  ? `${items.length - completed} still needed · ${completed} completed`
                  : 'A little planning. A smoother shop.'
              }
            />
            <View style={styles.connection}>
              <View
                style={[
                  styles.dot,
                  {
                    backgroundColor:
                      status === 'connected'
                        ? theme.success
                        : theme.textSecondary,
                  },
                ]}
              />
              <ThemedText
                type="small"
                themeColor="textSecondary"
                style={styles.itemBody}
              >
                {connectionLabel}
              </ThemedText>
            </View>
            <NativeAction
              label={
                list.categories.length
                  ? 'Add an item'
                  : 'Add your first category'
              }
              onPress={() =>
                setForm(list.categories.length ? 'item' : 'category')
              }
            />
            {query.isError ? (
              <InlineError
                message="Couldn’t refresh. Showing the last loaded list."
                onRetry={() => void query.refetch()}
              />
            ) : null}
            {toggleSubmission.error ? (
              <InlineError
                message={`${toggleSubmission.error} Refresh to confirm the item’s current state before toggling again.`}
                retryLabel="Refresh list"
                onRetry={() => void query.refetch()}
              />
            ) : null}
          </View>
        }
        renderSectionHeader={({ section }) => (
          <SectionHeading>{section.title}</SectionHeading>
        )}
        renderItem={({ item }) => (
          <ItemRow
            item={item}
            pending={toggle.isPending && toggle.variables === item.id}
            disabled={toggleSubmission.pending}
            onToggle={onToggle}
          />
        )}
        renderSectionFooter={({ section }) =>
          section.data.length ? null : (
            <ThemedText style={styles.empty} themeColor="textSecondary">
              Nothing still needed in this category.
            </ThemedText>
          )
        }
        ListFooterComponent={
          <View style={styles.footer}>
            {list.categories.length === 0 ? (
              <ThemedText themeColor="textSecondary">
                Start with a category like Produce or Household. Then add what
                you need.
              </ThemedText>
            ) : (
              <NativeAction
                label="Add a category"
                secondary
                onPress={() => setForm('category')}
              />
            )}
          </View>
        }
      />
      <NativeFormSheet
        title="New category"
        presented={form === 'category'}
        onDismiss={() => setForm(null)}
        onSubmit={() => submitCategory()}
        submitLabel="Add category"
        pending={categorySubmission.pending}
        disabled={!categoryName.text.trim()}
        error={categorySubmission.error}
      >
        <NativeField
          label="Category name"
          placeholder="For example, Produce"
          {...categoryName.input}
          editable={!categorySubmission.pending}
          onSubmitEditing={submitCategory}
          returnKeyType="done"
        />
      </NativeFormSheet>
      <NativeFormSheet
        title="Add an item"
        presented={form === 'item'}
        onDismiss={() => setForm(null)}
        onSubmit={submitItem}
        submitLabel="Add item"
        pending={itemSubmission.pending}
        disabled={!itemName.text.trim() || !selectedCategory}
        error={itemSubmission.error}
      >
        <NativeField
          label="Item name"
          placeholder="For example, Apples"
          {...itemName.input}
          editable={!itemSubmission.pending}
        />
        <Text>Category</Text>
        {selectedCategory ? (
          <Picker
            selectedValue={selectedCategory}
            onValueChange={setCategoryId}
            enabled={!itemSubmission.pending}
          >
            {list.categories.map((category) => (
              <Picker.Item
                key={category.id}
                label={category.name}
                value={category.id}
              />
            ))}
          </Picker>
        ) : null}
        <NativeField
          label="Quantity (optional)"
          placeholder="For example, 6 or 1 kg"
          {...quantity.input}
          editable={!itemSubmission.pending}
        />
        <NativeField
          label="Notes (optional)"
          {...notes.input}
          editable={!itemSubmission.pending}
          multiline
        />
      </NativeFormSheet>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  screen: { flex: 1 },
  item: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 16,
    minHeight: 64,
    gap: 14,
    borderRadius: 14,
    marginBottom: 6,
  },
  itemBody: { flex: 1, gap: 3 },
  checkbox: {
    width: 28,
    height: 28,
    borderRadius: 14,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
  },
  completed: { textDecorationLine: 'line-through' },
  connection: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dot: { width: 7, height: 7, borderRadius: 4 },
  empty: { padding: 12 },
  footer: { gap: 16, marginTop: 24 },
});
