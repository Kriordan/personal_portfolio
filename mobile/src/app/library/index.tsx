import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Redirect, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Image,
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
import { libraryApi, libraryKeys, type Playlist } from '@/lib/library-api';

function PlaylistRow({ playlist, onPress }: { playlist: Playlist; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}
    >
      {playlist.thumbnail_url ? (
        <Image
          source={{ uri: playlist.thumbnail_url }}
          style={styles.thumbnail}
          resizeMode="cover"
        />
      ) : null}
      <View style={styles.rowBody}>
        <ThemedText>{playlist.title}</ThemedText>
        {playlist.description ? (
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>
            {playlist.description}
          </ThemedText>
        ) : null}
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        ›
      </ThemedText>
    </Pressable>
  );
}

export default function LibraryScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isAuthenticated } = useAuth();

  const playlistsQuery = useQuery({
    queryKey: libraryKeys.playlists(),
    queryFn: libraryApi.getPlaylists,
    enabled: isAuthenticated === true,
  });

  const syncMutation = useMutation({
    mutationFn: libraryApi.sync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: libraryKeys.all });
    },
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (playlistsQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (playlistsQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Couldn’t load your library.</ThemedText>
        <Pressable style={styles.button} onPress={() => playlistsQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const { playlists } = playlistsQuery.data;

  return (
    <ThemedView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={playlistsQuery.isRefetching}
            onRefresh={() => playlistsQuery.refetch()}
          />
        }
      >
        <Pressable
          style={[styles.button, syncMutation.isPending && styles.buttonDisabled]}
          disabled={syncMutation.isPending}
          onPress={() => syncMutation.mutate()}
        >
          <ThemedText type="smallBold" style={styles.buttonText}>
            {syncMutation.isPending ? 'Syncing…' : 'Sync Library'}
          </ThemedText>
        </Pressable>
        {syncMutation.isError ? (
          <ThemedText type="small" style={styles.error}>
            {syncMutation.error instanceof Error
              ? syncMutation.error.message
              : 'Library sync failed.'}
          </ThemedText>
        ) : null}
        {syncMutation.isSuccess ? (
          <ThemedText type="small" style={styles.success}>
            {syncMutation.data.message}
          </ThemedText>
        ) : null}

        <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
          PLAYLISTS
        </ThemedText>
        {playlists.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            No playlists yet. Try syncing your library.
          </ThemedText>
        ) : (
          playlists.map((playlist) => (
            <PlaylistRow
              key={playlist.id}
              playlist={playlist}
              onPress={() => router.push(`/library/${playlist.id}`)}
            />
          ))
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
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#ffffff',
  },
  error: {
    color: '#d64545',
  },
  success: {
    color: '#2e9e5b',
  },
});
