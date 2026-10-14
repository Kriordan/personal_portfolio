export interface Playlist {
  id: string;
  title: string;
  description: string | null;
  published_at: string | null;
  updated_at: string | null;
  thumbnail_url: string | null;
}

export interface Video {
  id: string;
  playlist_id: string;
  video_url_id: string;
  title: string;
  description: string | null;
  published_at: string | null;
  thumbnail_url: string | null;
  embed_url: string;
  watched: boolean;
  in_watched_playlist?: boolean;
  position?: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export const libraryKeys = {
  all: ['library'] as const,
  playlists: () => ['library', 'playlists'] as const,
  playlist: (id: string) => ['library', 'playlist', id] as const,
  sync: ['library', 'sync'] as const,
  syncStatus: (requestId?: string) => ['library', 'sync-status', requestId ?? 'latest'] as const,
  observedSync: ['library', 'observed-sync'] as const,
  pins: (userId: number) => ['library', 'pins', userId] as const,
  pinAttempt: (userId: number) => ['library', 'pin-attempt', userId] as const,
  workflow: (userId: number) => ['library', 'workflow', userId] as const,
  moves: (userId: number) => ['library', 'moves', userId] as const,
  moveAttempt: (userId: number) => ['library', 'move-attempt', userId] as const,
  observedMoves: (userId: number) => ['library', 'observed-moves', userId] as const,
};

export type LibraryWorkflow = {
  is_owner: boolean; can_move: boolean; reason: string | null; version: string | null;
  source: { id: string; title: string } | null; destination: { id: string; title: string } | null;
  membership_checked_at: string | null;
};
export type LibraryMove = {
  id: string; source_entry_id: string; source_playlist_id: string; destination_playlist_id: string;
  video_url_id: string; video_title: string; source_title: string; destination_title: string;
  status: 'running' | 'succeeded' | 'partial' | 'unknown' | 'failed'; stage: string;
  error: string | null; started_at: string; updated_at: string; can_retry_removal: boolean;
};
export type LibraryMoves = { moves: LibraryMove[]; busy: boolean };

export function moveMessage(move: LibraryMove): string {
  if (move.status === 'succeeded') return `Saved to “${move.destination_title}” and removed from “${move.source_title}”.`;
  if (move.status === 'running') return 'Moving on the server. You can keep browsing; we’ll check for confirmation.';
  return move.error ?? 'The move has not been confirmed. Check its status before taking further action.';
}

export function mergeMoveReceipts(report?: LibraryMoves, receipt?: LibraryMove): LibraryMove[] {
  const rows = new Map((report?.moves ?? []).map((move) => [move.id, move]));
  if (receipt && (!rows.has(receipt.id) || rows.get(receipt.id)!.updated_at <= receipt.updated_at)) rows.set(receipt.id, receipt);
  return [...rows.values()].sort((a, b) => b.started_at.localeCompare(a.started_at));
}

export function movePollInterval(moves: LibraryMove[], pending: boolean, now = Date.now()): number {
  return pending || moves.some((move) => ['running', 'unknown'].includes(move.status) && now - Date.parse(move.started_at) < 120_000) ? 3_000 : 30_000;
}

export type LibraryPin = { playlist_id: string; pinned_at: string };

export function playlistSections(playlists: Playlist[], pins: LibraryPin[], search: string, sort: LibrarySort) {
  const matches = browseLibrary(playlists, search);
  const byId = new Map(matches.map((playlist) => [playlist.id, playlist]));
  const pinned = [...pins].sort((a, b) => a.pinned_at.localeCompare(b.pinned_at) || a.playlist_id.localeCompare(b.playlist_id));
  const pinIds = new Set(pinned.map((pin) => pin.playlist_id));
  return [
    { title: 'Pinned for you', data: pinned.flatMap((pin) => byId.has(pin.playlist_id) ? [byId.get(pin.playlist_id)!] : []) },
    { title: 'All other playlists', data: sortLibrary(matches.filter((playlist) => !pinIds.has(playlist.id)), sort) },
  ].filter((section) => section.data.length > 0);
}

export const playlistSorts = [
  { value: 'updated', label: 'Recently updated' },
  { value: 'title', label: 'Title A–Z' },
  { value: 'title-desc', label: 'Title Z–A' },
  { value: 'newest', label: 'Newest created' },
  { value: 'oldest', label: 'Oldest created' },
] as const;
export const videoSorts = [
  { value: 'newest', label: 'Newest added' },
  { value: 'oldest', label: 'Oldest added' },
  { value: 'position', label: 'YouTube playlist order' },
  { value: 'title', label: 'Title A–Z' },
  { value: 'title-desc', label: 'Title Z–A' },
] as const;
export type LibrarySort = 'updated' | 'newest' | 'oldest' | 'position' | 'title' | 'title-desc';
const titles = new Intl.Collator(undefined, { numeric: true, sensitivity: 'base' });
const timestamp = (value?: string | null) => value && Number.isFinite(Date.parse(value)) ? Date.parse(value) : null;

/** Never mutate Query's shared arrays. Unknown values sort last; IDs break ties. */
export function sortLibrary<T extends { id: string; title: string; published_at?: string | null; updated_at?: string | null; position?: number | null }>(items: T[], sort: LibrarySort): T[] {
  const compareOptional = (a: number | null | undefined, b: number | null | undefined, descending = false) => {
    if (a == null) return b == null ? 0 : 1;
    if (b == null) return -1;
    return descending ? b - a : a - b;
  };
  return [...items].sort((a, b) => {
    let result: number;
    if (sort === 'title' || sort === 'title-desc') result = titles.compare(a.title, b.title) * (sort === 'title-desc' ? -1 : 1);
    else if (sort === 'position') result = compareOptional(a.position, b.position);
    else result = compareOptional(timestamp(sort === 'updated' ? a.updated_at : a.published_at), timestamp(sort === 'updated' ? b.updated_at : b.published_at), sort !== 'oldest');
    return result || titles.compare(a.title, b.title) || a.id.localeCompare(b.id);
  });
}

export type SyncCounts = { checked: number; added: number; updated: number; unchanged: number; skipped: number };
export type LibrarySyncRun = {
  id: string; status: 'running' | 'succeeded' | 'failed' | 'interrupted';
  started_at: string; finished_at: string | null;
  summary: { playlists: SyncCounts; videos: SyncCounts } | null; error: string | null;
};
export type LibrarySyncReport = { latest: LibrarySyncRun | null; last_success: LibrarySyncRun | null; requested: LibrarySyncRun | null; busy: boolean };

export function syncSummary(run: LibrarySyncRun): string {
  if (run.status === 'running') return 'Syncing on the server. You can keep browsing; completion will be checked automatically.';
  if (run.status !== 'succeeded') return run.error ?? 'The import did not complete. Your saved catalog is still available.';
  if (!run.summary) return 'The server confirmed that the import completed.';
  const { playlists, videos } = run.summary;
  const counts = (value: SyncCounts) => `${value.added} added, ${value.updated} changed, ${value.unchanged} unchanged, ${value.skipped} skipped`;
  return `${playlists.checked} playlists checked: ${counts(playlists)}.\n${videos.checked} video entries checked: ${counts(videos)}.`;
}

/** Retain authoritative API ordering; filtering never sorts or changes cached data. */
export function browseLibrary<T extends { title: string; description: string | null }>(items: T[], search: string): T[] {
  const term = search.trim().toLocaleLowerCase();
  return term ? items.filter((item) => `${item.title}\n${item.description ?? ''}`.toLocaleLowerCase().includes(term)) : items;
}

export function validPlaylistId(id: unknown): id is string {
  return typeof id === 'string' && /^[A-Za-z0-9_-]+$/.test(id);
}

export function videoWatchUrl(id: string): string | null {
  const value = id.trim();
  return value ? `https://www.youtube.com/watch?v=${encodeURIComponent(value)}` : null;
}

export async function openLibraryVideo(id: string, open: (url: string) => Promise<unknown>): Promise<boolean> {
  const url = videoWatchUrl(id);
  if (!url) return false;
  try { await open(url); return true; } catch { return false; }
}
