import { useRouter } from 'expo-router';
import { Image } from 'expo-image';
import { useRef, useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { Card, InlineError, NativeAction } from './screen';
import { ThemedText } from './themed-text';
import { JobInfoButton } from './job-form-controls';
import { JobHelpContent } from './job-help-content';
import { useJobActivity, useJobCapture } from '@/hooks/use-jobwizard';
import { confirmAction } from '@/lib/confirm-action';
import {
  captureAttemptMessage,
  safeJobUrl,
  type Job,
} from '@/lib/jobwizard-model';

export function JobActivityStatus({
  activity,
}: {
  activity: ReturnType<typeof useJobActivity>;
}) {
  const router = useRouter();
  if (!activity.ready)
    return (
      <InlineError
        message={activity.error ?? 'Restoring saved operation state…'}
        onRetry={() => void activity.session.restore()}
      />
    );
  if (!activity.attempt && !activity.error) return null;
  const busy = ['saving', 'checking'].includes(activity.phase);
  return (
    <Card>
      <ThemedText type="smallBold" accessibilityLiveRegion="polite">
        {activity.phase === 'saving'
          ? activity.attempt?.kind === 'capture'
            ? 'Capturing screenshot…'
            : 'Saving job…'
          : activity.phase === 'checking'
            ? 'Checking completion…'
            : 'Jobwizard status'}
      </ThemedText>
      {activity.error ? <InlineError message={activity.error} /> : null}
      {activity.attempt?.jobId ? (
        <NativeAction
          label="Open affected job"
          secondary
          onPress={() =>
            router.push({
              pathname: '/jobwizard/[id]',
              params: { id: activity.attempt!.jobId! },
            })
          }
        />
      ) : null}
      {activity.phase === 'uncertain' ? (
        <>
          <NativeAction
            label="Check completion"
            secondary
            onPress={() => void activity.session.check()}
          />
          <NativeAction
            label="Retry same operation"
            secondary
            onPress={() => void activity.session.retry()}
          />
        </>
      ) : null}
      {activity.phase === 'rejected' ? (
        <NativeAction
          label="Clear rejected attempt"
          secondary
          disabled={busy}
          onPress={() => void activity.session.clearRejection()}
        />
      ) : null}
    </Card>
  );
}
export function JobLink({
  url,
  label = 'Open listing',
}: {
  url: string;
  label?: string;
}) {
  const [failed, setFailed] = useState(false),
    [pending, setPending] = useState(false),
    lock = useRef(false);
  const open = async () => {
    if (lock.current || !safeJobUrl(url)) return;
    lock.current = true;
    setPending(true);
    setFailed(false);
    try {
      await Linking.openURL(url);
    } catch {
      setFailed(true);
    } finally {
      lock.current = false;
      setPending(false);
    }
  };
  return (
    <View style={styles.gap}>
      <NativeAction
        label={pending ? 'Opening…' : label}
        onPress={() => void open()}
        disabled={pending || !safeJobUrl(url)}
      />
      {failed ? (
        <InlineError message="Couldn’t open the link. Check that a browser is available and try again." />
      ) : null}
    </View>
  );
}
export function JobScreenshot({
  job,
  activity,
}: {
  job: Job;
  activity: ReturnType<typeof useJobActivity>;
}) {
  const query = useJobCapture(job.id, true);
  const router = useRouter();
  const status = query.data?.capture;
  const [showHelp, setShowHelp] = useState(false);
  const [failedUri, setFailedUri] = useState<string | null>(null),
    attemptedRenewal = useRef<string | null>(null),
    confirming = useRef(false);
  const capture = () => {
    if (confirming.current || activity.attempt) return;
    confirming.current = true;
    confirmAction(
      'Capture this listing?',
      'Send this public listing URL to Browserless to capture a screenshot? Avoid private or tokenized links. Embedded videos are omitted. Your job is already saved.',
      'Capture',
      () => {
        confirming.current = false;
        void activity.session.begin({
          kind: 'capture',
          jobId: job.id,
          input: { expected_revision: job.revision },
        });
      },
      () => {
        confirming.current = false;
      },
      false,
    );
  };
  const image = status?.image;
  return (
    <Card>
      <View style={styles.heading}>
        <ThemedText type="subtitle" accessibilityRole="header">
          Screenshot
        </ThemedText>
        <JobInfoButton
          label="About screenshot capture"
          expanded={showHelp}
          onPress={() => setShowHelp(!showHelp)}
        />
      </View>
      {showHelp ? <JobHelpContent topic="capture" /> : null}
      {query.isPending ? (
        <ThemedText>Loading screenshot status…</ThemedText>
      ) : null}
      {query.isError ? (
        <InlineError
          message="Couldn’t refresh screenshot status."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {status?.latest ? (
        <ThemedText accessibilityLiveRegion="polite">
          {captureAttemptMessage(status.latest)}
        </ThemedText>
      ) : null}
      {image ? (
        <>
          {failedUri === image.url ? (
            <InlineError
              message="Screenshot access expired or is unavailable."
              onRetry={() => void query.refetch()}
              retryLabel="Refresh screenshot access"
            />
          ) : (
            <Image
              source={{ uri: image.url }}
              recyclingKey={image.url}
              cachePolicy="none"
              contentFit="contain"
              style={{
                width: '100%',
                aspectRatio: Math.max(0.12, image.width / image.height),
                maxHeight: 650,
                alignSelf: 'center',
              }}
              accessibilityLabel={`Listing screenshot for ${job.title}`}
              onError={() => {
                setFailedUri(image.url);
                // One automatic renewal per artifact, avoiding an endless failed-image loop.
                if (attemptedRenewal.current !== image.captured_at) {
                  attemptedRenewal.current = image.captured_at;
                  void query.refetch();
                }
              }}
            />
          )}
          <ThemedText type="small" themeColor="textSecondary">
            Captured {new Date(image.captured_at).toLocaleString()}
            {image.outdated ? ' · From an older listing URL' : ''}
          </ThemedText>
          <NativeAction
            label="Open full screenshot"
            onPress={() =>
              router.push({
                pathname: '/jobwizard/[id]/screenshot',
                params: { id: job.id },
              })
            }
          />
        </>
      ) : status ? (
        <ThemedText themeColor="textSecondary">
          {status.legacy_unavailable
            ? 'The old screenshot is unavailable. Its original reference is preserved.'
            : 'No screenshot available.'}
        </ThemedText>
      ) : null}
      {status?.configured && status.supported !== false ? (
        <NativeAction
          label={
            status.busy || status.latest?.status === 'running'
              ? 'Capturing…'
              : image
                ? 'Capture new screenshot'
                : 'Capture screenshot'
          }
          secondary
          disabled={
            !activity.ready ||
            !!activity.attempt ||
            status.busy ||
            status.latest?.status === 'running'
          }
          onPress={capture}
        />
      ) : status?.supported === false ? (
        <ThemedText type="small" themeColor="textSecondary">
          Capture isn’t supported for this link. You can still save and open it.
        </ThemedText>
      ) : status ? (
        <ThemedText type="small" themeColor="textSecondary">
          Screenshot capture is currently unavailable. Saving and editing jobs
          still works.
        </ThemedText>
      ) : null}
    </Card>
  );
}
const styles = StyleSheet.create({
  gap: { gap: 8 },
  heading: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
});
