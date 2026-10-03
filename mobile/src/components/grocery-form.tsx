import { Button, Picker, Text } from '@expo/ui';
import { useRouter } from 'expo-router';
import { useState } from 'react';

import { NativeField, NativeFormSheet } from '@/components/native-form';
import type { useGroceryList } from '@/hooks/use-lists';
import { useNativeText } from '@/hooks/use-native-text';
import { useSubmission } from '@/hooks/use-submission';
import { findDuplicateItems, normalizeItemName, type DuplicateMatch } from '@/lib/grocery-duplicates';
import type { ListCategory, ListDetail, ListItem, ListItemInput } from '@/lib/lists-api';

export type GroceryEditor =
  | { kind: 'item'; item?: ListItem }
  | { kind: 'category'; category?: ListCategory }
  | { kind: 'list' };

type Actions = Pick<
  ReturnType<typeof useGroceryList>,
  | 'addItem'
  | 'updateItem'
  | 'deleteItem'
  | 'addCategory'
  | 'renameCategory'
  | 'deleteCategory'
  | 'renameList'
  | 'deleteList'
>;

export function GroceryForm({
  editor,
  list,
  actions,
  initialCategoryId,
  onClose,
  onCategoryCreated,
}: {
  editor: GroceryEditor;
  list: ListDetail;
  actions: Actions;
  initialCategoryId?: number;
  onClose: () => void;
  onCategoryCreated: (id: number) => void;
}) {
  const router = useRouter();
  const item = editor.kind === 'item' ? editor.item : undefined;
  const category = editor.kind === 'category' ? editor.category : undefined;
  const initialName = item?.name ?? category?.name ?? (editor.kind === 'list' ? list.title : '');
  const name = useNativeText(initialName);
  const quantity = useNativeText(item?.quantity ?? '');
  const notes = useNativeText(item?.notes ?? '');
  const [categoryId, setCategoryId] = useState<number | undefined>(
    item?.category_id ?? initialCategoryId ?? list.categories[0]?.id,
  );
  const submission = useSubmission();
  const [deleting, setDeleting] = useState(false);
  const [duplicate, setDuplicate] = useState<{
    input: ListItemInput;
    matches: DuplicateMatch[];
  } | null>(null);
  const editing = !!item || !!category || editor.kind === 'list';
  const noun = editor.kind === 'list' ? 'list' : editor.kind;
  const selectedCategory = list.categories.some((entry) => entry.id === categoryId) ? categoryId : undefined;
  const matching = editor.kind === 'item' ? findDuplicateItems(list, name.text, item?.id) : [];
  const changedName = normalizeItemName(name.text) !== normalizeItemName(initialName);

  const saveItem = async (input: ListItemInput) => {
    if (item) await actions.updateItem.mutateAsync({ itemId: item.id, input });
    else await actions.addItem.mutateAsync(input);
    onClose();
  };
  const submit = () => {
    if (deleting) {
      void submission.run(async () => {
        if (item) await actions.deleteItem.mutateAsync(item.id);
        else if (category) await actions.deleteCategory.mutateAsync(category.id);
        else {
          await actions.deleteList.mutateAsync();
          router.replace('/lists');
        }
        onClose();
      });
      return;
    }
    if (duplicate) {
      void submission.run(() => saveItem(duplicate.input));
      return;
    }
    const currentName = name.read().trim();
    if (!currentName) return;
    if (editor.kind === 'item') {
      if (!selectedCategory) return;
      const input = {
        name: currentName,
        category_id: selectedCategory,
        quantity: quantity.read().trim(),
        notes: notes.read().trim(),
      };
      // Read native text again here: the final keystroke can precede its React event.
      const matches = !item || normalizeItemName(currentName) !== normalizeItemName(initialName)
        ? findDuplicateItems(list, currentName, item?.id) : [];
      if (matches.length) setDuplicate({ input, matches });
      else void submission.run(() => saveItem(input));
    } else {
      void submission.run(async () => {
        if (editor.kind === 'list') await actions.renameList.mutateAsync(currentName);
        else if (category) await actions.renameCategory.mutateAsync({ categoryId: category.id, name: currentName });
        else {
          const result = await actions.addCategory.mutateAsync(currentName);
          onCategoryCreated(result.category.id);
        }
        onClose();
      });
    }
  };
  const deletionMessage = item
    ? `Delete “${item.name}”? Only this item will be removed.`
    : category
      ? `Delete “${category.name}” and all its items? This category currently has ${list.categories.find((entry) => entry.id === category.id)?.items.length ?? 0} items, including completed items.`
      : `Delete “${list.title}” and all its categories and items? Everyone sharing this list will lose access.`;

  return (
    <NativeFormSheet
      title={deleting ? `Delete ${noun}?` : duplicate ? 'Already on your list?' : editing ? `Edit ${noun}` : `New ${noun}`}
      presented
      onDismiss={() => {
        if (!submission.pending) onClose();
      }}
      onSubmit={submit}
      submitLabel={deleting ? `Delete ${noun}` : duplicate ? (item ? 'Save anyway' : 'Add anyway') : editing ? 'Save changes' : `Add ${noun}`}
      destructive={deleting}
      pendingLabel={deleting ? 'Deleting…' : 'Saving…'}
      pending={submission.pending}
      disabled={!deleting && !duplicate && (!name.text.trim() || (editor.kind === 'item' && !selectedCategory))}
      error={submission.error}
    >
      {deleting ? (
        <>
          <Text>{deletionMessage}</Text>
          <Text>This cannot be undone.</Text>
          <Button
            label="Keep editing"
            variant="outlined"
            disabled={submission.pending}
            onPress={() => setDeleting(false)}
          />
        </>
      ) : duplicate ? (
        <>
          <Text>{`“${duplicate.input.name}” matches or resembles an existing item:`}</Text>
          {duplicate.matches.slice(0, 5).map((match) => (
            <Text key={match.item.id}>{`${match.item.name}${match.item.quantity ? ` (${match.item.quantity})` : ''} · ${match.category}${match.item.completed ? ' · completed' : ''}`}</Text>
          ))}
          {duplicate.matches.length > 5 ? <Text>{`And ${duplicate.matches.length - 5} more matches.`}</Text> : null}
          <Text>You can update an existing item or keep this as a separate entry.</Text>
          <Button
            label="Keep editing"
            variant="outlined"
            disabled={submission.pending}
            onPress={() => setDuplicate(null)}
          />
        </>
      ) : (
        <>
          <NativeField
            label={editor.kind === 'list' ? 'List name' : editor.kind === 'item' ? 'Item name' : 'Category name'}
            {...name.input}
            editable={!submission.pending}
            maxLength={editor.kind === 'category' ? 64 : 128}
            returnKeyType={editor.kind === 'item' ? 'next' : 'done'}
            onSubmitEditing={editor.kind === 'item' ? undefined : submit}
          />
          {editor.kind === 'item' ? (
            <>
              {matching.length && (!item || changedName) ? <Text>{`Already on this list: ${matching.slice(0, 3).map((match) => `${match.item.name}${match.item.completed ? ' (completed)' : ''}`).join(', ')}. We’ll ask before adding a duplicate.`}</Text> : null}
              <Text>Category</Text>
              <Picker
                selectedValue={selectedCategory ?? 0}
                onValueChange={(value) =>
                  setCategoryId(typeof value === 'number' && value > 0 ? value : undefined)
                }
                enabled={!submission.pending}
              >
                {!selectedCategory ? <Picker.Item label="Choose a category" value={0} /> : null}
                {list.categories.map((entry) => (
                  <Picker.Item key={entry.id} label={entry.name} value={entry.id} />
                ))}
              </Picker>
              <NativeField label="Quantity (optional)" {...quantity.input} editable={!submission.pending} maxLength={32} />
              <NativeField label="Notes (optional)" {...notes.input} editable={!submission.pending} multiline />
            </>
          ) : null}
          {editing ? (
            <Button
              label={`Delete ${noun}…`}
              variant="text"
              disabled={submission.pending}
              onPress={() => setDeleting(true)}
            />
          ) : null}
        </>
      )}
    </NativeFormSheet>
  );
}
