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
  created_at: string | null;
  updated_at: string | null;
}

export const libraryKeys = {
  all: ['library'] as const,
  playlists: () => ['library', 'playlists'] as const,
  playlist: (id: string) => ['library', 'playlist', id] as const,
  sync: ['library', 'sync'] as const,
};

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
