import { useQuery } from '@tanstack/react-query';
import { Redirect, Stack, useLocalSearchParams } from 'expo-router';
import {
  ActivityIndicator,
  Image,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { libraryApi, libraryKeys, type Video } from '@/lib/library-api';

function videoWatchUrl(video: Video): string {
  return `https://www.youtube.com/watch?v=${video.video_url_id}`;
}

function VideoRow({ video }: { video: Video }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={() => Linking.openURL(videoWatchUrl(video))}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}
    >
      {video.thumbnail_url ? (
        <Image source={{ uri: video.thumbnail_url }} style={styles.thumbnail} resizeMode="cover" />
      ) : null}
      <View style={styles.rowBody}>
        <ThemedText numberOfLines={2}>{video.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {video.published_at ? new Date(video.published_at).toLocaleDateString() : ''}
          {video.watched ? ' · Watched' : ''}
        </ThemedText>
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        ›
      </ThemedText>
    </Pressable>
  );
}

export default function PlaylistDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { isAuthenticated } = useAuth();

  const playlistQuery = useQuery({
    queryKey: libraryKeys.playlist(id),
    queryFn: () => libraryApi.getPlaylist(id),
    enabled: Boolean(id) && isAuthenticated === true,
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (playlistQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (playlistQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">
          {playlistQuery.error instanceof Error
            ? playlistQuery.error.message
            : 'Couldn’t load playlist.'}
        </ThemedText>
        <Pressable style={styles.button} onPress={() => playlistQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const { playlist, videos } = playlistQuery.data;

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen options={{ title: playlist.title }} />
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={playlistQuery.isRefetching}
            onRefresh={() => playlistQuery.refetch()}
          />
        }
      >
        <ThemedText type="subtitle">{playlist.title}</ThemedText>
        {playlist.description ? (
          <ThemedText type="small" themeColor="textSecondary">
            {playlist.description}
          </ThemedText>
        ) : null}

        <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
          VIDEOS
        </ThemedText>
        {videos.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            No videos in this playlist.
          </ThemedText>
        ) : (
          videos.map((video) => <VideoRow key={video.id} video={video} />)
        )}
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.three,
  },
  scrollContent: {
    padding: Spacing.three,
    gap: Spacing.two,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  sectionHeader: {
    marginTop: Spacing.three,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
  },
  rowBody: {
    flex: 1,
    gap: Spacing.half,
  },
  thumbnail: {
    width: 64,
    height: 48,
    borderRadius: Spacing.one,
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    color: '#ffffff',
  },
});
