import { useRef, useState } from 'react';
import { Linking, View } from 'react-native';
import { InlineError, NativeAction, screenStyles } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useLibraryMoves } from '@/hooks/use-library-moves';
import { useTheme } from '@/hooks/use-theme';
import { confirmAction } from '@/lib/confirm-action';
import { API_BASE_URL } from '@/lib/config';
import { moveMessage, type LibraryMove, type Video } from '@/lib/library-model';

type Moves = ReturnType<typeof useLibraryMoves>;

export function LibraryMoveStatus({ activity }: { activity: Moves }) {
  const theme = useTheme();
  const [expanded, setExpanded] = useState(false);
  const [linkError, setLinkError] = useState(false);
  const confirming = useRef(false);
  if (!activity.workflow.data?.is_owner) return null;
  const retry = (move: LibraryMove) => {
    if (confirming.current || activity.pending) return;
    confirming.current = true;
    confirmAction('Finish moving this video?', `“${move.video_title}” is saved to “${move.destination_title}”. Check it is still there, then remove the exact entry from “${move.source_title}”?`, 'Remove from added', () => {
      confirming.current = false;
      activity.retryRemoval(move.id);
    }, () => { confirming.current = false; });
  };
  return <View style={screenStyles.gap}>
    {!activity.workflow.data.can_move ? <>
      <ThemedText type="small" themeColor="textSecondary">{activity.workflow.data.reason}</ThemedText>
      <NativeAction label="Manage YouTube connection" secondary onPress={() => { setLinkError(false); void Linking.openURL(`${API_BASE_URL}/oauth/`).catch(() => setLinkError(true)); }} />
      {linkError ? <InlineError message="Couldn’t open the connection page. Open the website’s YouTube connection page in your browser." /> : null}
    </> : null}
    {activity.error ? <InlineError message={activity.error} onRetry={activity.refresh} retryLabel="Check move status" /> : null}
    {activity.status.isError ? <InlineError message="Couldn’t refresh move status. Keeping the last confirmed result; no move has been sent again." onRetry={activity.refresh} retryLabel="Check move status" /> : null}
    {activity.pending && !activity.moves.some((move) => move.status === 'running') ? <ThemedText accessibilityLiveRegion="polite">Waiting for the server…</ThemedText> : null}
    {(expanded ? activity.moves : activity.moves.slice(0, 2)).map((move) => <View key={move.id} style={{ backgroundColor: theme.backgroundElement, borderRadius: 16, padding: 16, gap: 10 }}>
      <ThemedText type="smallBold">{move.status === 'succeeded' ? 'Move complete' : move.status === 'partial' ? 'Move needs one more step' : move.status === 'failed' ? 'Move failed' : move.status === 'unknown' ? 'Move awaiting confirmation' : 'Moving video'}</ThemedText>
      <ThemedText>{move.video_title}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary" accessibilityLiveRegion="polite">{moveMessage(move)}</ThemedText>
      {move.can_retry_removal ? <NativeAction label="Finish removal from added" secondary disabled={activity.pending} onPress={() => retry(move)} /> : null}
      {move.status === 'unknown' || move.status === 'running' ? <NativeAction label="Check move status" secondary onPress={activity.refresh} /> : null}
    </View>)}
    {activity.moves.length > 2 ? <NativeAction label={expanded ? 'Show less move activity' : `Show all move activity (${activity.moves.length})`} secondary onPress={() => setExpanded((value) => !value)} /> : null}
  </View>;
}

export function LibraryMoveAction({ video, activity }: { video: Video; activity: Moves }) {
  const confirming = useRef(false);
  const setup = activity.workflow.data;
  if (!setup?.can_move || setup.source?.id !== video.playlist_id || !setup.destination) return null;
  const receipt = activity.moves.find((move) => move.source_entry_id === video.id && move.status !== 'failed');
  if (receipt) return <ThemedText type="small" themeColor="textSecondary">{receipt.status === 'partial' ? 'Saved to watched. Finish removal in move activity above.' : receipt.status === 'succeeded' ? 'Moved to watched. Refreshing this playlist…' : 'Move awaiting confirmation. See move activity above.'}</ThemedText>;
  return <NativeAction label="Move to watched" secondary disabled={activity.pending || activity.status.isPending || activity.status.isError} onPress={() => {
    if (confirming.current) return;
    confirming.current = true;
    confirmAction('Move to watched?', `Save “${video.title}” to “${setup.destination!.title}”, then remove this entry from “${setup.source!.title}”? This changes your YouTube playlists and the shared Library.`, 'Move to watched', () => {
      confirming.current = false;
      activity.start(video.id);
    }, () => { confirming.current = false; });
  }} />;
}
