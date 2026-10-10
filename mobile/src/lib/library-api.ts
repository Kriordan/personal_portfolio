import { apiRequest } from '@/lib/api-client';
import type { Playlist, Video, LibrarySyncRun, LibrarySyncReport, LibraryPin, LibraryWorkflow, LibraryMove, LibraryMoves } from '@/lib/library-model';
export { libraryKeys, type Playlist, type Video } from '@/lib/library-model';

// Shapes mirror project/api/library.py and library_service.serialize_*().

export const libraryApi = {
  workflow(): Promise<LibraryWorkflow> { return apiRequest('/library/workflow'); },
  moves(): Promise<LibraryMoves> { return apiRequest('/library/moves', { timeoutMs: 30_000 }); },
  move(requestId: string, entryId: string, version: string): Promise<{ move: LibraryMove }> {
    return apiRequest('/library/moves', { method: 'POST', body: { request_id: requestId, source_entry_id: entryId, workflow_version: version }, timeoutMs: 30_000 });
  },
  retryRemoval(moveId: string, requestId: string): Promise<{ move: LibraryMove }> {
    return apiRequest(`/library/moves/${encodeURIComponent(moveId)}/retry-removal`, { method: 'POST', body: { request_id: requestId }, timeoutMs: 30_000 });
  },
  getPins(): Promise<{ pins: LibraryPin[] }> {
    return apiRequest('/library/pins');
  },
  setPin(id: string, pinned: boolean): Promise<{ pins: LibraryPin[] }> {
    return apiRequest(`/library/pins/${encodeURIComponent(id)}`, { method: 'PUT', body: { pinned } });
  },
  getPlaylists(): Promise<{ playlists: Playlist[] }> {
    return apiRequest<{ playlists: Playlist[] }>('/library/playlists');
  },

  getPlaylist(playlistId: string): Promise<{ playlist: Playlist; videos: Video[] }> {
    return apiRequest<{ playlist: Playlist; videos: Video[] }>(
      `/library/playlists/${encodeURIComponent(playlistId)}`,
    );
  },

  getVideo(videoId: string): Promise<{ video: Video }> {
    return apiRequest<{ video: Video }>(`/library/videos/${encodeURIComponent(videoId)}`);
  },

  sync(requestId: string): Promise<{ run: LibrarySyncRun }> {
    return apiRequest<{ run: LibrarySyncRun }>('/library/sync', { method: 'POST', body: { request_id: requestId }, timeoutMs: 30_000 });
  },

  syncStatus(requestId?: string): Promise<LibrarySyncReport> {
    return apiRequest<LibrarySyncReport>(`/library/sync-status${requestId ? `?request_id=${encodeURIComponent(requestId)}` : ''}`, { timeoutMs: 15_000 });
  },
};
