import { apiRequest } from '@/lib/api-client';
import type { Playlist, Video } from '@/lib/library-model';
export { libraryKeys, type Playlist, type Video } from '@/lib/library-model';

// Shapes mirror project/api/library.py and library_service.serialize_*().

export const libraryApi = {
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

  sync(): Promise<{ message: string }> {
    return apiRequest<{ message: string }>('/library/sync', { method: 'POST', timeoutMs: 30_000 });
  },
};
