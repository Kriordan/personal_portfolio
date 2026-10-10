import { useState } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';

import { InlineError, NativeAction } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import type { useLibrarySync } from '@/hooks/use-library';
import { useTheme } from '@/hooks/use-theme';
import { syncSummary } from '@/lib/library-model';

const when = (value: string | null) => value ? new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }) : '';

export function LibrarySyncStatus({ sync }: { sync: ReturnType<typeof useLibrarySync> }) {
  const theme = useTheme();
  const [details, setDetails] = useState(false);
  const { run, lastSuccess, statusQuery } = sync;
  const complete = run?.status === 'succeeded';
  const failed = run?.status === 'failed' || run?.status === 'interrupted';
  return <View style={[styles.card, { backgroundColor: theme.backgroundElement }]}>
    {run && sync.status === 'error' && !sync.uncertain && run.id !== sync.requestId ? <InlineError message={sync.message!} /> : null}
    {sync.pending ? <View style={styles.row}><ActivityIndicator color={theme.accent} /><ThemedText type="smallBold">Syncing from YouTube…</ThemedText></View> : null}
    {run ? <>
      {!sync.pending ? <ThemedText type="smallBold" accessibilityLiveRegion="polite">{complete ? `Sync complete · ${when(run.finished_at)}` : run.status === 'interrupted' ? 'Sync interrupted' : 'Sync did not complete'}</ThemedText> : null}
      {complete && run.summary ? <>
        <ThemedText type="small">{run.summary.playlists.checked} playlists · {run.summary.videos.checked} video entries checked</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">{run.summary.videos.added} new videos · {run.summary.videos.updated} changed</ThemedText>
        <NativeAction label={details ? 'Hide sync details' : 'Show sync details'} secondary onPress={() => setDetails((value) => !value)} />
        {details ? <><ThemedText type="small">{syncSummary(run)}</ThemedText><ThemedText type="small" themeColor="textSecondary">Unavailable entries are skipped. Previously saved items are retained when they disappear from YouTube. Video counts include entries in each playlist.</ThemedText></> : null}
      </> : <ThemedText type="small" themeColor="textSecondary">{syncSummary(run)}</ThemedText>}
    </> : sync.status === 'error' && !sync.uncertain ? <InlineError message={sync.message!} /> : <ThemedText type="small" themeColor="textSecondary">{sync.pending ? 'Starting the shared import. You can keep browsing.' : sync.uncertain ? sync.message : statusQuery.isPending ? 'Checking the latest sync…' : statusQuery.isError ? 'No confirmed sync result available.' : 'No completed sync recorded yet.'}</ThemedText>}
    {(!complete || failed) && lastSuccess ? <ThemedText type="small" themeColor="textSecondary">Last successful sync: {when(lastSuccess.finished_at)}</ThemedText> : null}
    {statusQuery.isPaused ? <ThemedText type="small" themeColor="textSecondary">You’re offline. Status will be checked when you reconnect.</ThemedText> : null}
    {statusQuery.isError ? <InlineError message="Couldn’t check the current sync status. Any result above is the last confirmed result." /> : null}
    {(!complete && sync.uncertain) || statusQuery.isError || failed ? <NativeAction label="Check sync status" secondary disabled={statusQuery.isFetching} onPress={() => void statusQuery.refetch()} /> : null}
  </View>;
}

const styles = StyleSheet.create({ card: { padding: 16, borderRadius: 16, gap: 8 }, row: { flexDirection: 'row', alignItems: 'center', gap: 10 } });
