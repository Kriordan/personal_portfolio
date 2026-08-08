import { apiRequest } from '@/lib/api-client';

// Shapes mirror project/api/library.py and library_service.serialize_*().

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
    return apiRequest<{ message: string }>('/library/sync', { method: 'POST' });
  },
};

export const libraryKeys = {
  all: ['library'] as const,
  playlists: () => ['library', 'playlists'] as const,
  playlist: (playlistId: string) => ['library', 'playlist', playlistId] as const,
};
