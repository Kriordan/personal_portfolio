import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useIsFocused } from 'expo-router';

import { useAuth } from '@/lib/auth-context';
import { ApiError } from '@/lib/api-client';
import { emitListEvent, useListRoom } from '@/lib/list-socket';
import { listsApi, type ListItemInput } from '@/lib/lists-api';
import {
  listMutationOptions,
  requireConnection,
} from '@/lib/list-mutation-policy';
import {
  createListRoomHandlers,
  listsKeys,
  listsRefreshOptions,
  patchList,
  withCategoryAdded,
  withItemAdded,
  withItemToggled,
} from '@/lib/lists-cache';

export function useListsOverview() {
  const { isAuthenticated } = useAuth();
  return useQuery({
    ...listsRefreshOptions,
    queryKey: listsKeys.overview(),
    queryFn: listsApi.getLists,
    enabled: isAuthenticated === true,
  });
}

export function useCreateList() {
  const client = useQueryClient();
  return useMutation({
    ...listMutationOptions,
    mutationFn: (title: string) => {
      requireConnection();
      return listsApi.createList(title);
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: listsKeys.overview() });
    },
  });
}

export function useGroceryList(listId: number) {
  const client = useQueryClient();
  const { isAuthenticated } = useAuth();
  const focused = useIsFocused();
  const validId = Number.isSafeInteger(listId) && listId > 0;
  const query = useQuery({
    ...listsRefreshOptions,
    queryKey: listsKeys.detail(listId),
    queryFn: () => listsApi.getList(listId),
    enabled: validId && isAuthenticated === true,
  });
  const status = useListRoom(listId, createListRoomHandlers(client, listId), {
    enabled:
      validId &&
      focused &&
      isAuthenticated === true &&
      !!query.data &&
      !(
        query.error instanceof ApiError &&
        [403, 404].includes(query.error.status)
      ),
  });
  const addCategory = useMutation({
    ...listMutationOptions,
    mutationFn: (name: string) => {
      requireConnection();
      return listsApi.addCategory(listId, name);
    },
    onSuccess: async ({ category }) => {
      await patchList(client, listId, (list) =>
        withCategoryAdded(list, category),
      );
      emitListEvent('category_added', { list_id: listId, category });
    },
  });
  const addItem = useMutation({
    ...listMutationOptions,
    mutationFn: (input: Parameters<typeof listsApi.addItem>[1]) => {
      requireConnection();
      return listsApi.addItem(listId, input);
    },
    onSuccess: async ({ item }) => {
      await patchList(client, listId, (list) =>
        withItemAdded(list, item.category_id, item),
      );
      emitListEvent('item_added', {
        list_id: listId,
        category_id: item.category_id,
        item,
      });
    },
  });
  const toggle = useMutation({
    ...listMutationOptions,
    mutationFn: (itemId: number) => {
      requireConnection();
      return listsApi.toggleItem(listId, itemId);
    },
    onSuccess: async ({ completed }, itemId) => {
      await patchList(client, listId, (list) =>
        withItemToggled(list, itemId, completed),
      );
      emitListEvent('item_toggled', {
        list_id: listId,
        item_id: itemId,
        completed,
      });
    },
    // A network failure can mean a lost response after persistence. Refetch; never toggle again automatically.
    onError: () => {
      void client.invalidateQueries({
        queryKey: listsKeys.detail(listId),
        exact: true,
      });
    },
  });
  const refreshList = () => {
    void client.invalidateQueries({ queryKey: listsKeys.detail(listId), exact: true });
  };
  const refreshListAndOverview = () => {
    refreshList();
    void client.invalidateQueries({ queryKey: listsKeys.overview(), exact: true });
  };
  const editOptions = { ...listMutationOptions, onSuccess: refreshList, onError: refreshList };
  const updateItem = useMutation({
    ...editOptions,
    mutationFn: ({ itemId, input }: { itemId: number; input: ListItemInput }) => {
      requireConnection();
      return listsApi.updateItem(listId, itemId, input);
    },
  });
  const deleteItem = useMutation({
    ...editOptions,
    mutationFn: (itemId: number) => {
      requireConnection();
      return listsApi.deleteItem(listId, itemId);
    },
  });
  const renameCategory = useMutation({
    ...editOptions,
    mutationFn: ({ categoryId, name }: { categoryId: number; name: string }) => {
      requireConnection();
      return listsApi.renameCategory(listId, categoryId, name);
    },
  });
  const deleteCategory = useMutation({
    ...editOptions,
    mutationFn: (categoryId: number) => {
      requireConnection();
      return listsApi.deleteCategory(listId, categoryId);
    },
  });
  const renameList = useMutation({
    ...editOptions,
    mutationFn: (title: string) => {
      requireConnection();
      return listsApi.renameList(listId, title);
    },
    onSuccess: refreshListAndOverview,
  });
  const deleteList = useMutation({
    ...editOptions,
    mutationFn: () => {
      requireConnection();
      return listsApi.deleteList(listId);
    },
    onSuccess: refreshListAndOverview,
  });
  return { query, status, validId, addCategory, addItem, toggle, updateItem, deleteItem, renameCategory, deleteCategory, renameList, deleteList };
}
