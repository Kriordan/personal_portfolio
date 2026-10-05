import type { QueryClient } from '@tanstack/react-query';

import type { ListRoomHandlers } from './list-socket';
import type { ListCategory, ListDetail, ListItem } from './lists-api';

// Kept independent of native modules so the realtime reconciliation can be tested in Node.
export const listsKeys = {
  all: ['lists'] as const,
  overview: () => ['lists', 'overview'] as const,
  detail: (listId: number) => ['lists', 'detail', listId] as const,
};

// A short background/offline interval can miss website changes while this cache
// is still fresh. Recover independently of whether Socket.IO has disconnected.
export const listsRefreshOptions = {
  refetchOnWindowFocus: 'always',
  refetchOnReconnect: 'always',
} as const;

export function withItemToggled(
  detail: ListDetail,
  itemId: number,
  completed: boolean,
): ListDetail {
  return {
    ...detail,
    categories: detail.categories.map((category) => ({
      ...category,
      items: category.items.map((item) =>
        item.id === itemId ? { ...item, completed } : item,
      ),
    })),
  };
}

export function withItemAdded(
  detail: ListDetail,
  categoryId: number,
  item: ListItem,
): ListDetail {
  return {
    ...detail,
    categories: detail.categories.map((category) => {
      if (
        category.id !== categoryId ||
        category.items.some((existing) => existing.id === item.id)
      )
        return category;
      return { ...category, items: [...category.items, item] };
    }),
  };
}

export function withCategoryAdded(
  detail: ListDetail,
  category: ListCategory,
): ListDetail {
  if (detail.categories.some((existing) => existing.id === category.id))
    return detail;
  return {
    ...detail,
    categories: [
      ...detail.categories,
      { ...category, items: category.items ?? [] },
    ],
  };
}

export async function patchList(
  client: QueryClient,
  listId: number,
  update: (list: ListDetail) => ListDetail,
) {
  const queryKey = listsKeys.detail(listId);
  const state = client.getQueryState(queryKey);
  const needsReconciliation =
    state?.isInvalidated || state?.fetchStatus === 'fetching';
  // A fetch started before this event must not overwrite the newly confirmed state.
  await client.cancelQueries({ queryKey, exact: true });
  client.setQueryData<{ list: ListDetail }>(queryKey, (cached) =>
    cached ? { list: update(cached.list) } : cached,
  );
  // Preserve a reconnect/settings refresh: this event may describe only one of
  // several changes missed while disconnected. Start a new read after patching.
  if (needsReconciliation) {
    void client.invalidateQueries({ queryKey, exact: true });
  }
}

export function createListRoomHandlers(
  client: QueryClient,
  listId: number,
): ListRoomHandlers {
  const refresh = () => {
    void client.invalidateQueries({
      queryKey: listsKeys.detail(listId),
      exact: true,
    });
  };
  return {
    onContentChanged: refresh,
    onListChanged: () => {
      refresh();
      void client.invalidateQueries({ queryKey: listsKeys.overview(), exact: true });
    },
    onItemToggled: ({ item_id, completed }) => {
      void patchList(client, listId, (list) =>
        withItemToggled(list, Number(item_id), completed),
      );
    },
    onItemAdded: ({ category_id, item }) => {
      void patchList(client, listId, (list) =>
        withItemAdded(list, category_id, item),
      ).then(() => {
        // The category creation event may have been missed while reconnecting.
        const cached = client.getQueryData<{ list: ListDetail }>(
          listsKeys.detail(listId),
        );
        if (
          !cached?.list.categories.some(
            (category) => category.id === category_id,
          )
        )
          refresh();
      });
    },
    onCategoryAdded: ({ category }) => {
      void patchList(client, listId, (list) =>
        withCategoryAdded(list, category),
      );
    },
    onItemsReordered: refresh,
    onCategoriesReordered: refresh,
    onSettingsUpdated: refresh,
    onJoined: refresh,
  };
}

export interface GrocerySection {
  key: string;
  title: string;
  categoryId?: number;
  completed: boolean;
  data: ListItem[];
}

export function grocerySections(list: ListDetail): GrocerySection[] {
  const sections: GrocerySection[] = [];
  const allCompleted: ListItem[] = [];
  for (const category of [...list.categories].sort(
    (a, b) => a.ordering - b.ordering,
  )) {
    const ordered = [...category.items].sort((a, b) => a.ordering - b.ordering);
    const pending = ordered.filter((item) => !item.completed);
    const completed = ordered.filter((item) => item.completed);
    sections.push({
      key: `category-${category.id}`,
      title: category.name,
      categoryId: category.id,
      completed: false,
      data:
        list.completed_display_mode === 'inline_bottom'
          ? [...pending, ...completed]
          : pending,
    });
    if (list.completed_display_mode === 'global_section')
      allCompleted.push(...completed);
    else if (
      list.completed_display_mode !== 'inline_bottom' &&
      completed.length
    ) {
      sections.push({
        key: `completed-${category.id}`,
        title: `${category.name} · Completed`,
        completed: true,
        data: completed,
      });
    }
  }
  if (allCompleted.length)
    sections.push({
      key: 'completed',
      title: 'Completed',
      completed: true,
      data: allCompleted,
    });
  return sections;
}
