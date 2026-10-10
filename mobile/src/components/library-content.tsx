import { Host } from '@expo/ui';
import { Image } from 'expo-image';
import { useRef, useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import { NativeField } from '@/components/native-form';
import { InlineError, NativeAction } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { openLibraryVideo, videoWatchUrl, type Video } from '@/lib/library-model';

export function LibraryImage({ uri, hero = false }: { uri: string | null; hero?: boolean }) {
  const theme = useTheme();
  const [failedUri, setFailedUri] = useState<string | null>(null);
  return (
    <View style={[hero ? styles.hero : styles.thumbnail, { backgroundColor: theme.backgroundSelected }]} accessible={hero} accessibilityLabel="Playlist artwork">
      {uri && failedUri !== uri ? (
        <Image source={{ uri }} recyclingKey={uri} style={styles.image} contentFit={hero ? 'contain' : 'cover'} onError={() => setFailedUri(uri)} accessible={false} />
      ) : <ThemedText themeColor="textSecondary" accessible={false}>{hero ? 'Playlist artwork unavailable' : '▷'}</ThemedText>}
    </View>
  );
}

export function LibrarySearch({ search, label }: { search: ReturnType<typeof useNativeText>; label: string }) {
  return <>
    <Host matchContents={{ vertical: true }}><NativeField label={label} {...search.input} placeholder="Title or description" autoCorrect={false} /></Host>
    {search.text ? <NativeAction label="Clear search" secondary onPress={search.clear} /> : null}
  </>;
}

export function LibraryEmpty({ title, message }: { title: string; message: string }) {
  return <View style={styles.empty}><ThemedText type="subtitle">{title}</ThemedText><ThemedText themeColor="textSecondary">{message}</ThemedText></View>;
}

export function VideoRow({ video }: { video: Video }) {
  const theme = useTheme();
  const lock = useRef(false);
  const [opening, setOpening] = useState(false);
  const [failed, setFailed] = useState(false);
  const available = !!videoWatchUrl(video.video_url_id);
  const open = async () => {
    if (lock.current || !available) return;
    lock.current = true;
    setOpening(true);
    setFailed(false);
    const opened = await openLibraryVideo(video.video_url_id, (url) => Linking.openURL(url));
    setFailed(!opened);
    setOpening(false);
    lock.current = false;
  };
  return <View style={styles.video}>
    <Pressable accessibilityRole="link" accessibilityLabel={`${video.title}${video.watched ? '. Watched, shared' : ''}`} accessibilityHint={available ? 'Opens YouTube or your browser' : 'Video link unavailable'} accessibilityState={{ disabled: !available || opening, busy: opening }} disabled={!available || opening} onPress={() => void open()}
      style={({ pressed }) => [libraryStyles.row, { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement }]}>
      <LibraryImage uri={video.thumbnail_url} />
      <View style={libraryStyles.rowBody}>
        <ThemedText style={libraryStyles.rowTitle}>{video.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{!available ? 'Video link unavailable' : opening ? 'Opening YouTube…' : 'Watch on YouTube ↗'}</ThemedText>
        {video.watched ? <ThemedText type="small" themeColor="textSecondary">Watched · shared</ThemedText> : null}
      </View>
    </Pressable>
    {failed ? <InlineError message="Couldn’t open YouTube. Try again when a browser or the YouTube app is available." onRetry={() => void open()} retryLabel="Try opening YouTube again" /> : null}
  </View>;
}

export const libraryStyles = StyleSheet.create({
  screen: { flex: 1 },
  row: { minHeight: 96, padding: 16, gap: 14, borderRadius: 16, marginBottom: 10, flexDirection: 'row', alignItems: 'center' },
  rowBody: { flex: 1, gap: 4 },
  rowTitle: { fontWeight: '600' },
  count: { paddingVertical: 12 },
});
const styles = StyleSheet.create({
  thumbnail: { width: 72, height: 54, borderRadius: 10, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  hero: { width: '100%', height: 180, borderRadius: 16, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
  image: { width: '100%', height: '100%' },
  empty: { paddingVertical: 24, gap: 12 },
  video: { gap: 4 },
});
