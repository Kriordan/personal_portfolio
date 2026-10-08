import { useRouter } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import { ActivityIndicator, FlatList, Pressable, RefreshControl, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LibraryEmpty, LibraryImage, LibrarySearch, libraryStyles } from '@/components/library-content';
import { InlineError, NativeAction, PageHeading, ScreenState, screenStyles } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useLibrary, useLibrarySync } from '@/hooks/use-library';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { confirmAction } from '@/lib/confirm-action';
import { browseLibrary, type Playlist } from '@/lib/library-model';

function PlaylistRow({ playlist }: { playlist: Playlist }) {
  const theme = useTheme();
  const router = useRouter();
  return <Pressable accessibilityRole="link" accessibilityLabel={playlist.title} accessibilityHint="Opens playlist videos" onPress={() => router.push({ pathname: '/library/[id]', params: { id: playlist.id } })}
    style={({ pressed }) => [libraryStyles.row, { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement }]}>
    <LibraryImage uri={playlist.thumbnail_url} />
    <View style={libraryStyles.rowBody}>
      <ThemedText style={libraryStyles.rowTitle}>{playlist.title}</ThemedText>
      {playlist.description ? <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>{playlist.description}</ThemedText> : null}
    </View>
    <ThemedText accessible={false} themeColor="textSecondary">›</ThemedText>
  </Pressable>;
}
const keyForPlaylist = (playlist: Playlist) => playlist.id;
const renderPlaylist = ({ item }: { item: Playlist }) => <PlaylistRow playlist={item} />;

export default function LibraryScreen() {
  const query = useLibrary();
  const sync = useLibrarySync();
  const theme = useTheme();
  const search = useNativeText();
  const confirming = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  const playlists = useMemo(() => browseLibrary(query.data?.playlists ?? [], search.text), [query.data?.playlists, search.text]);
  const refresh = () => { setRefreshing(true); void query.refetch().finally(() => setRefreshing(false)); };
  const confirmSync = () => {
    if (confirming.current || sync.status === 'pending') return;
    confirming.current = true;
    confirmAction('Sync shared Library?', 'Update the shared Library from the server’s connected YouTube account? Changes are visible to everyone.', 'Sync', () => {
      confirming.current = false;
      sync.start();
    }, () => { confirming.current = false; }, false);
  };
  if (!query.data && query.isPending) return <ScreenState loading={!query.isPaused} title={query.isPaused ? 'You’re offline' : 'Loading Library'} message={query.isPaused ? 'Reconnect to load the shared catalog.' : undefined} />;
  if (!query.data) return <ScreenState title="Couldn’t load Library" message="Check your connection and try again." onRetry={() => void query.refetch()} />;
  const total = query.data.playlists.length;
  return <SafeAreaView edges={['left', 'right', 'bottom']} style={[libraryStyles.screen, { backgroundColor: theme.background }]}>
    <FlatList data={playlists} keyExtractor={keyForPlaylist} renderItem={renderPlaylist} contentContainerStyle={screenStyles.collection} contentInsetAdjustmentBehavior="automatic" keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
      ListHeaderComponent={<View style={screenStyles.gap}>
        <PageHeading title="Library" subtitle="A shared collection of playlists, ready to explore." />
        <LibrarySearch search={search} label="Search playlists" />
        <NativeAction label={sync.status === 'pending' ? 'Syncing from YouTube…' : 'Sync from YouTube'} secondary disabled={sync.status === 'pending'} onPress={confirmSync} />
        {sync.status === 'pending' ? <View style={screenStyles.gap}><ActivityIndicator color={theme.accent} accessibilityLabel="Import in progress" /><ThemedText type="small" themeColor="textSecondary">Updating the shared catalog. You can keep browsing.</ThemedText></View> : null}
        {sync.status === 'error' ? <InlineError message={sync.message!} /> : null}
        {sync.status === 'success' ? <ThemedText accessibilityLiveRegion="polite">{sync.message}</ThemedText> : null}
        {sync.uncertain ? <NativeAction label="Refresh saved catalog" secondary onPress={refresh} disabled={refreshing} /> : null}
        <ThemedText type="small" themeColor="textSecondary">Pull to refresh saved playlists. Sync imports updates from YouTube for everyone.</ThemedText>
        {query.isPaused ? <ThemedText themeColor="textSecondary">You’re offline. Showing the last loaded playlists.</ThemedText> : null}
        {query.isError ? <InlineError message={sync.status === 'success' ? 'The import completed, but these playlists couldn’t refresh. Showing the last loaded catalog.' : 'Couldn’t refresh. Showing the last loaded playlists.'} onRetry={refresh} /> : null}
        <ThemedText type="smallBold" themeColor="textSecondary" style={libraryStyles.count}>{search.text.trim() ? `${playlists.length} of ${total} playlists` : `${total} ${total === 1 ? 'playlist' : 'playlists'}`} · Newest first</ThemedText>
      </View>}
      ListEmptyComponent={<LibraryEmpty title={total ? 'No matching playlists' : 'Your shared Library starts here.'} message={total ? 'Try another title or description, or clear your search.' : 'Sync from YouTube to import the connected account’s playlists. Everyone signed in sees the same catalog.'} />}
    />
  </SafeAreaView>;
}
