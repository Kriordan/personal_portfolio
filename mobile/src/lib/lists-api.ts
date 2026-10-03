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

export interface ListItemInput {
  name: string;
  category_id: number;
  quantity?: string;
  notes?: string;
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

  renameList(listId: number, title: string): Promise<{ list: ListSummary }> {
    return apiRequest(`/lists/${listId}`, { method: 'PATCH', body: { title } });
  },

  deleteList(listId: number): Promise<void> {
    return apiRequest(`/lists/${listId}`, { method: 'DELETE' });
  },

  renameCategory(listId: number, categoryId: number, name: string): Promise<{ category: ListCategory }> {
    return apiRequest(`/lists/${listId}/categories/${categoryId}`, { method: 'PATCH', body: { name } });
  },

  deleteCategory(listId: number, categoryId: number): Promise<void> {
    return apiRequest(`/lists/${listId}/categories/${categoryId}`, { method: 'DELETE' });
  },

  updateItem(listId: number, itemId: number, input: ListItemInput): Promise<{ item: ListItem }> {
    return apiRequest(`/lists/${listId}/items/${itemId}`, { method: 'PATCH', body: input });
  },

  deleteItem(listId: number, itemId: number): Promise<void> {
    return apiRequest(`/lists/${listId}/items/${itemId}`, { method: 'DELETE' });
  },

  addCategory(listId: number, name: string): Promise<{ category: ListCategory }> {
    return apiRequest<{ category: ListCategory }>(`/lists/${listId}/categories`, {
      method: 'POST',
      body: { name },
    });
  },

  addItem(
    listId: number,
    input: ListItemInput,
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

export { listsKeys } from './lists-cache';
