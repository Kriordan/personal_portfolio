import { useRouter } from 'expo-router';
import { useCallback, useMemo, useRef, useState } from 'react';
import { SectionList, Pressable, RefreshControl, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LibraryEmpty, LibraryImage, LibrarySearch, libraryStyles } from '@/components/library-content';
import { LibrarySortControl } from '@/components/library-sort-control';
import { InlineError, NativeAction, PageHeading, ScreenState, screenStyles } from '@/components/screen';
import { LibrarySyncStatus } from '@/components/library-sync-status';
import { useLibrarySort } from '@/hooks/use-library-sort';
import { ThemedText } from '@/components/themed-text';
import { useLibrary, useLibraryPins, useLibrarySync } from '@/hooks/use-library';
import { LibraryPinButton } from '@/components/library-pin-button';
import { LibraryMoveStatus } from '@/components/library-move-status';
import { useLibraryMoves } from '@/hooks/use-library-moves';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { confirmAction } from '@/lib/confirm-action';
import { playlistSections, type Playlist } from '@/lib/library-model';

function PlaylistRow({ playlist, pinned, disabled, onPin }: { playlist: Playlist; pinned: boolean; disabled: boolean; onPin: () => void }) {
  const theme = useTheme();
  const router = useRouter();
  return <View style={{ backgroundColor: theme.backgroundElement, borderRadius: 16, marginBottom: 10 }}><Pressable accessibilityRole="link" accessibilityLabel={playlist.title} accessibilityHint="Opens playlist videos" onPress={() => router.push({ pathname: '/library/[id]', params: { id: playlist.id } })}
    style={({ pressed }) => [libraryStyles.row, { marginBottom: 0, backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement }]}>
    <LibraryImage uri={playlist.thumbnail_url} />
    <View style={libraryStyles.rowBody}>
      <ThemedText style={libraryStyles.rowTitle}>{playlist.title}</ThemedText>
      {playlist.description ? <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>{playlist.description}</ThemedText> : null}
    </View>
    <ThemedText accessible={false} themeColor="textSecondary">›</ThemedText>
  </Pressable><LibraryPinButton title={playlist.title} pinned={pinned} disabled={disabled} onPress={onPin} /></View>;
}
const keyForPlaylist = (playlist: Playlist) => playlist.id;

export default function LibraryScreen() {
  const query = useLibrary();
  const pins = useLibraryPins();
  const activity = useLibraryMoves();
  const sync = useLibrarySync();
  const theme = useTheme();
  const sort = useLibrarySort('playlists');
  const search = useNativeText();
  const confirming = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  const sections = useMemo(() => playlistSections(query.data?.playlists ?? [], pins.pins, search.text, sort.value), [query.data?.playlists, pins.pins, search.text, sort.value]);
  const pinIds = useMemo(() => new Set(pins.pins.map((pin) => pin.playlist_id)), [pins.pins]);
  const { set: setPin } = pins;
  const renderPlaylist = useCallback(({ item }: { item: Playlist }) => <PlaylistRow playlist={item} pinned={pinIds.has(item.id)} disabled={!pins.ready || pins.pending} onPin={() => setPin(item.id, !pinIds.has(item.id))} />, [pinIds, pins.ready, pins.pending, setPin]);
  const refresh = () => { setRefreshing(true); void Promise.all([query.refetch(), pins.query.refetch()]).finally(() => setRefreshing(false)); };
  const confirmSync = () => {
    if (confirming.current || sync.pending) return;
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
    <SectionList sections={sections} keyExtractor={keyForPlaylist} renderItem={renderPlaylist} stickySectionHeadersEnabled={false}
      renderSectionHeader={({ section }) => <ThemedText type="smallBold" accessibilityRole="header" style={libraryStyles.count}>{section.title === 'All other playlists' && !pinIds.size ? 'Playlists' : section.title}</ThemedText>}
      contentContainerStyle={screenStyles.collection} contentInsetAdjustmentBehavior="automatic" keyboardShouldPersistTaps="handled" automaticallyAdjustKeyboardInsets
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={refresh} />}
      ListHeaderComponent={<View style={screenStyles.gap}>
        <PageHeading title="Library" subtitle="A shared collection of playlists, ready to explore." />
        <LibrarySearch search={search} label="Search playlists" />
        <NativeAction label={sync.pending ? 'Syncing from YouTube…' : 'Sync from YouTube'} secondary disabled={sync.pending} onPress={confirmSync} />
        <LibrarySyncStatus sync={sync} />
        <LibraryMoveStatus activity={activity} />
        <ThemedText type="small" themeColor="textSecondary">Pull to refresh saved playlists. Sync imports updates from YouTube for everyone.</ThemedText>
        {query.isPaused ? <ThemedText themeColor="textSecondary">You’re offline. Showing the last loaded playlists.</ThemedText> : null}
        {query.isError ? <InlineError message={sync.run?.status === 'succeeded' ? 'The import completed, but these playlists couldn’t refresh. Showing the last loaded catalog.' : 'Couldn’t refresh. Showing the last loaded playlists.'} onRetry={refresh} /> : null}
        {pins.error || pins.query.isError ? <InlineError message={pins.error ?? 'Couldn’t load your pins. Showing the saved catalog.'} onRetry={() => void pins.query.refetch()} /> : null}
        {pins.query.isPending ? <ThemedText type="small" themeColor="textSecondary">Loading your pins…</ThemedText> : null}
        <ThemedText type="smallBold" themeColor="textSecondary" style={libraryStyles.count}>{search.text.trim() ? `${sections.reduce((count, section) => count + section.data.length, 0)} of ${total} playlists` : `${total} ${total === 1 ? 'playlist' : 'playlists'}`}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">Pin your favorites for quick access on your devices. Sorting applies to the remaining playlists.</ThemedText>
        <LibrarySortControl sort={sort} />
      </View>}
      ListEmptyComponent={<LibraryEmpty title={total ? 'No matching playlists' : 'Your shared Library starts here.'} message={total ? 'Try another title or description, or clear your search.' : 'Sync from YouTube to import the connected account’s playlists. Everyone signed in sees the same catalog.'} />}
    />
  </SafeAreaView>;
}
