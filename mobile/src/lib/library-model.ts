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
};

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
