import { onlineManager, type QueryClient } from '@tanstack/react-query';
import { libraryKeys, type LibraryMove, type Playlist, type Video } from './library-model.ts';

export type MoveAttempt = { pending: boolean; error?: string; uncertain?: boolean; move?: LibraryMove; requestId?: string };
export const idleMove: MoveAttempt = { pending: false };

export async function startLibraryMove(client: QueryClient, userId: number, requestId: string, send: () => Promise<{ move: LibraryMove }>) {
  const key = libraryKeys.moveAttempt(userId);
  if (client.getQueryData<MoveAttempt>(key)?.pending) return;
  if (!onlineManager.isOnline()) {
    client.setQueryData(key, { pending: false, error: 'Reconnect to move a video. Nothing has been queued.' });
    return;
  }
  client.setQueryData(key, { pending: true, requestId });
  const pending = client.getQueryData(key);
  const active = () => client.getQueryData(key) === pending;
  try {
    const response = await send();
    if (!active()) return;
    await client.cancelQueries({ queryKey: libraryKeys.moves(userId) });
    if (!active()) return;
    client.setQueryData(key, { pending: false, requestId, move: response.move });
    void client.invalidateQueries({ queryKey: libraryKeys.moves(userId) });
  } catch (error) {
    if (!active()) return;
    const status = error && typeof error === 'object' && 'status' in error ? error.status : undefined;
    const rejected = [400, 401, 403, 404, 409].includes(Number(status));
    client.setQueryData(key, { pending: false, requestId, uncertain: !rejected,
      error: rejected ? 'The move could not start. Refresh to check permissions, setup, or another running operation.' : 'Waiting for server confirmation. We’ll check status; the move will not be sent again automatically.' });
    void client.invalidateQueries({ queryKey: libraryKeys.moves(userId) });
    void client.invalidateQueries({ queryKey: libraryKeys.workflow(userId) });
  }
}

/** Remove the exact entry immediately after confirmed success; preserve every
 * other occurrence. A subsequent refresh recovers metadata and badge changes. */
export async function observeLibraryMove(client: QueryClient, userId: number, move: LibraryMove) {
  if (move.status === 'running') return;
  const key = libraryKeys.observedMoves(userId);
  const observed = client.getQueryData<Record<string, string>>(key) ?? {};
  if (observed[move.id] === move.updated_at) return;
  client.setQueryData(key, { ...observed, [move.id]: move.updated_at });
  const marker = client.getQueryData(key);
  const catalog = (query: { queryKey: readonly unknown[] }) => ['playlist', 'playlists'].includes(String(query.queryKey[1]));
  await client.cancelQueries({ queryKey: libraryKeys.all, predicate: catalog });
  if (client.getQueryData(key) !== marker) return;
  if (move.status === 'succeeded') {
    client.setQueryData<{ playlist: Playlist; videos: Video[] }>(libraryKeys.playlist(move.source_playlist_id), (data) => data ? { ...data, videos: data.videos.filter((video) => video.id !== move.source_entry_id) } : undefined);
  }
  void client.invalidateQueries({ queryKey: libraryKeys.all, predicate: catalog });
}
