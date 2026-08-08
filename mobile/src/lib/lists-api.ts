import { apiRequest } from '@/lib/api-client';

// Shapes mirror the serializers in project/api/lists.py.

export interface ListItem {
  id: number;
  name: string;
  quantity: string | null;
  notes: string | null;
  completed: boolean;
  ordering: number;
  category_id: number;
}

export interface ListCategory {
  id: number;
  name: string;
  ordering: number;
  items: ListItem[];
}

export interface ListSummary {
  id: number;
  title: string;
  owner_id: number;
  completed_display_mode: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface ListDetail extends ListSummary {
  categories: ListCategory[];
}

export interface ListsOverview {
  owned: ListSummary[];
  shared: ListSummary[];
}

export const listsApi = {
  getLists(): Promise<ListsOverview> {
    return apiRequest<ListsOverview>('/lists/');
  },

  createList(title: string): Promise<{ list: ListSummary }> {
    return apiRequest<{ list: ListSummary }>('/lists/', {
      method: 'POST',
      body: { title },
    });
  },

  getList(listId: number): Promise<{ list: ListDetail }> {
    return apiRequest<{ list: ListDetail }>(`/lists/${listId}`);
  },

  addCategory(listId: number, name: string): Promise<{ category: ListCategory }> {
    return apiRequest<{ category: ListCategory }>(`/lists/${listId}/categories`, {
      method: 'POST',
      body: { name },
    });
  },

  addItem(
    listId: number,
    input: { name: string; category_id: number; quantity?: string; notes?: string },
  ): Promise<{ item: ListItem }> {
    return apiRequest<{ item: ListItem }>(`/lists/${listId}/items`, {
      method: 'POST',
      body: input,
    });
  },

  toggleItem(listId: number, itemId: number): Promise<{ completed: boolean }> {
    return apiRequest<{ completed: boolean }>(`/lists/${listId}/items/${itemId}/toggle`, {
      method: 'POST',
    });
  },
};

export const listsKeys = {
  all: ['lists'] as const,
  overview: () => ['lists', 'overview'] as const,
  detail: (listId: number) => ['lists', 'detail', listId] as const,
};
