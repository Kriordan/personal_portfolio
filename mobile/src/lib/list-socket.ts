import { useEffect, useRef, useState } from 'react';
import { io, type Socket } from 'socket.io-client';

import { refreshAccessToken } from '@/lib/api-client';
import { API_BASE_URL } from '@/lib/config';
import type { ListCategory, ListItem } from '@/lib/lists-api';

// Payloads mirror the broadcasts in project/sockets.py.

export interface ItemToggledEvent {
  list_id: number;
  item_id: number;
  completed: boolean;
  toggled_by: string;
}

export interface ItemAddedEvent {
  list_id: number;
  category_id: number;
  item: ListItem;
  added_by: string;
}

export interface ItemsReorderedEvent {
  list_id: number;
  items: { id: number; ordering: number; category_id?: number }[];
  reordered_by: string;
}

export interface CategoryAddedEvent {
  list_id: number;
  category: ListCategory;
  added_by: string;
}

export interface CategoriesReorderedEvent {
  list_id: number;
  categories: { id: number; ordering: number }[];
  reordered_by: string;
}

export interface SettingsUpdatedEvent {
  list_id: number;
  completed_display_mode: string;
  updated_by: string;
}

export interface ListRoomHandlers {
  onItemToggled?: (event: ItemToggledEvent) => void;
  onItemAdded?: (event: ItemAddedEvent) => void;
  onItemsReordered?: (event: ItemsReorderedEvent) => void;
  onCategoryAdded?: (event: CategoryAddedEvent) => void;
  onCategoriesReordered?: (event: CategoriesReorderedEvent) => void;
  onSettingsUpdated?: (event: SettingsUpdatedEvent) => void;
  /** Fired on every (re)connect after the room is joined; use to refetch missed state. */
  onJoined?: () => void;
}

export type SocketStatus = 'connecting' | 'connected' | 'disconnected';

let socket: Socket | null = null;

/**
 * Lazily create the shared Socket.IO connection.
 *
 * The server validates a JWT access token in the connect handler
 * (project/sockets.py), so each connection attempt refreshes the access token
 * first: connects are infrequent and a stale token would be rejected outright.
 */
export function getListSocket(): Socket {
  if (socket) return socket;

  socket = io(API_BASE_URL, {
    autoConnect: false,
    reconnection: true,
    reconnectionDelay: 1_000,
    reconnectionDelayMax: 10_000,
    auth: (cb) => {
      refreshAccessToken()
        .then((token) => cb({ token }))
        .catch(() => cb({ token: null }));
    },
  });
  return socket;
}

/** Tear down the shared socket on sign-out so a new user gets a fresh connection. */
export function disconnectListSocket(): void {
  if (!socket) return;
  socket.disconnect();
  socket.removeAllListeners();
  socket = null;
}

/**
 * Join a list room for the lifetime of the component and wire realtime
 * handlers. Handlers are kept in a ref so callers can pass fresh closures on
 * every render without resubscribing.
 */
export function useListRoom(
  listId: number,
  handlers: ListRoomHandlers,
  { enabled = true }: { enabled?: boolean } = {},
): SocketStatus {
  const [status, setStatus] = useState<SocketStatus>('connecting');
  const handlersRef = useRef(handlers);

  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    if (!enabled) return;
    const activeSocket = getListSocket();
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    const joinRoom = () => {
      setStatus('connected');
      activeSocket.emit('join_list', { list_id: listId }, (response?: { success?: boolean }) => {
        if (response?.success) {
          handlersRef.current.onJoined?.();
        }
      });
    };

    const handleDisconnect = () => setStatus('disconnected');

    // Engine-level failures reconnect automatically, but a server-side
    // rejection (bad/missing token) does not, so schedule a manual retry —
    // the auth callback fetches a fresh token on each attempt.
    const handleConnectError = () => {
      setStatus('disconnected');
      if (retryTimer) clearTimeout(retryTimer);
      retryTimer = setTimeout(() => {
        if (!activeSocket.connected && activeSocket === socket) {
          setStatus('connecting');
          activeSocket.connect();
        }
      }, 5_000);
    };

    const forList =
      <T extends { list_id: number }>(handler: (event: T) => void) =>
      (event: T) => {
        if (event.list_id === listId) handler(event);
      };

    const onItemToggled = forList<ItemToggledEvent>((e) => handlersRef.current.onItemToggled?.(e));
    const onItemAdded = forList<ItemAddedEvent>((e) => handlersRef.current.onItemAdded?.(e));
    const onItemsReordered = forList<ItemsReorderedEvent>((e) =>
      handlersRef.current.onItemsReordered?.(e),
    );
    const onCategoryAdded = forList<CategoryAddedEvent>((e) =>
      handlersRef.current.onCategoryAdded?.(e),
    );
    const onCategoriesReordered = forList<CategoriesReorderedEvent>((e) =>
      handlersRef.current.onCategoriesReordered?.(e),
    );
    const onSettingsUpdated = forList<SettingsUpdatedEvent>((e) =>
      handlersRef.current.onSettingsUpdated?.(e),
    );

    activeSocket.on('connect', joinRoom);
    activeSocket.on('disconnect', handleDisconnect);
    activeSocket.on('connect_error', handleConnectError);
    activeSocket.on('item_toggled', onItemToggled);
    activeSocket.on('item_added', onItemAdded);
    activeSocket.on('items_reordered', onItemsReordered);
    activeSocket.on('category_added', onCategoryAdded);
    activeSocket.on('categories_reordered', onCategoriesReordered);
    activeSocket.on('settings_updated', onSettingsUpdated);

    if (activeSocket.connected) {
      joinRoom();
    } else {
      setStatus('connecting');
      activeSocket.connect();
    }

    return () => {
      if (retryTimer) clearTimeout(retryTimer);
      activeSocket.off('connect', joinRoom);
      activeSocket.off('disconnect', handleDisconnect);
      activeSocket.off('connect_error', handleConnectError);
      activeSocket.off('item_toggled', onItemToggled);
      activeSocket.off('item_added', onItemAdded);
      activeSocket.off('items_reordered', onItemsReordered);
      activeSocket.off('category_added', onCategoryAdded);
      activeSocket.off('categories_reordered', onCategoriesReordered);
      activeSocket.off('settings_updated', onSettingsUpdated);
      if (activeSocket.connected) {
        activeSocket.emit('leave_list', { list_id: listId });
      }
    };
  }, [listId, enabled]);

  return status;
}

/**
 * Notify other clients in the room after a successful local mutation.
 * Mirrors the web client (project/static/js/lists.js): the REST call persists,
 * then the socket event fans out to everyone else in the room.
 */
export function emitListEvent(
  event: 'item_toggled' | 'item_added' | 'category_added',
  payload: Record<string, unknown>,
): void {
  if (socket?.connected) {
    socket.emit(event, payload);
  }
}
