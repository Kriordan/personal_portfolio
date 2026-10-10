import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useMemo, useState } from 'react';
import { FlatList, RefreshControl, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LibraryEmpty, LibraryImage, LibrarySearch, VideoRow, libraryStyles } from '@/components/library-content';
import { LibrarySortControl } from '@/components/library-sort-control';
import { InlineError, NativeAction, PageHeading, Screen, ScreenState, screenStyles } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useLibraryPins, usePlaylist } from '@/hooks/use-library';
import { LibraryPinButton } from '@/components/library-pin-button';
import { useLibrarySort } from '@/hooks/use-library-sort';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { ApiError } from '@/lib/api-client';
import { browseLibrary, sortLibrary, validPlaylistId, type Video } from '@/lib/library-model';

const keyForVideo = (video: Video) => video.id;
const renderVideo = ({ item }: { item: Video }) => <VideoRow video={item} />;

export default function PlaylistDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const query = usePlaylist(id);
  const pins = useLibraryPins();
  const router = useRouter();
  const theme = useTheme();
  const search = useNativeText();
  const sort = useLibrarySort('videos');
  const [expanded, setExpanded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const videos = useMemo(() => sortLibrary(browseLibrary(query.data?.videos ?? [], search.text), sort.value), [query.data?.videos, search.text, sort.value]);
  const refresh = () => { setRefreshing(true); void query.refetch().finally(() => setRefreshing(false)); };
  const unavailable = !validPlaylistId(id) || query.error instanceof ApiError && [403, 404].includes(query.error.status);
  if (unavailable) return <Screen><PageHeading title="Playlist unavailable" subtitle="This playlist may have been removed or the link may be invalid." /><NativeAction label="Back to Library" onPress={() => router.replace('/library')} /></Screen>;
  if (!query.data && query.isPending) return <ScreenState loading={!query.isPaused} title={query.isPaused ? 'You’re offline' : 'Loading playlist'} message={query.isPaused ? 'Reconnect to load this playlist.' : undefined} />;
  if (!query.data) return <ScreenState title="Couldn’t load playlist" message="Check your connection and try again." onRetry={() => void query.refetch()} />;
  const { playlist, videos: allVideos } = query.data;
  return <>
    <Stack.Screen options={{ title: 'Playlist' }} />
    <SafeAreaView edges={['left', 'right', 'bottom']} style={[libraryStyles.screen, { backgroundColor: theme.background }]}>
      <FlatList data={videos} keyExtractor={keyForVideo} renderItem={renderVideo} contentContainerStyle={screenStyles.collection} contentInsetAdjustmentBehavior="automatic" keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
        ListHeaderComponent={<View style={screenStyles.gap}>
          <PageHeading title={playlist.title} eyebrow="SHARED LIBRARY" />
          <LibraryPinButton title={playlist.title} pinned={pins.pins.some((pin) => pin.playlist_id === id)} disabled={!pins.ready || pins.pending} onPress={() => pins.set(id, !pins.pins.some((pin) => pin.playlist_id === id))} />
          {pins.error || pins.query.isError ? <InlineError message={pins.error ?? 'Couldn’t load your pins.'} onRetry={() => void pins.query.refetch()} /> : null}
          <LibraryImage uri={playlist.thumbnail_url} hero />
          {playlist.description ? <View style={screenStyles.gap}>
            <ThemedText themeColor="textSecondary" numberOfLines={expanded ? undefined : 3}>{playlist.description}</ThemedText>
            <NativeAction label={expanded ? 'Show less description' : 'Show full description'} secondary onPress={() => setExpanded((value) => !value)} />
          </View> : null}
          <LibrarySearch search={search} label="Search videos in this playlist" />
          <ThemedText type="small" themeColor="textSecondary">Videos open in YouTube or your browser. Opening a video doesn’t change shared watched status.</ThemedText>
          {query.isPaused ? <ThemedText themeColor="textSecondary">You’re offline. Showing the last loaded videos.</ThemedText> : null}
          {query.isError ? <InlineError message="Couldn’t refresh. Showing the last loaded videos." onRetry={refresh} /> : null}
          <ThemedText type="smallBold" themeColor="textSecondary" style={libraryStyles.count}>{search.text.trim() ? `${videos.length} of ${allVideos.length} videos` : `${allVideos.length} ${allVideos.length === 1 ? 'video' : 'videos'}`}</ThemedText>
          <LibrarySortControl sort={sort} />
          {sort.value === 'position' && allVideos.some((video) => video.position == null) ? <ThemedText type="small" themeColor="textSecondary">Items without a saved YouTube position appear last. Sync to update playlist order.</ThemedText> : null}
        </View>}
        ListEmptyComponent={<LibraryEmpty title={allVideos.length ? 'No matching videos' : 'No videos saved yet'} message={allVideos.length ? 'Try another title or description, or clear your search.' : 'Return to Library to sync from YouTube. Unavailable videos may not be imported.'} />}
      />
    </SafeAreaView>
  </>;
}
