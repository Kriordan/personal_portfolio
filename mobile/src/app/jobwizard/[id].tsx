import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { AccessibilityInfo, Linking, RefreshControl, View } from 'react-native';
import * as Clipboard from 'expo-clipboard';
import { JobActionsMenu } from '@/components/job-actions-menu';
import type { JobAction } from '@/components/job-actions-menu.types';
import { JobImportantDetails } from '@/components/job-important-details';
import { JobForm } from '@/components/job-form';
import {
  JobActivityStatus,
  JobScreenshot,
} from '@/components/jobwizard-content';
import {
  InlineError,
  NativeAction,
  PageHeading,
  Screen,
  ScreenState,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useJob, useJobActivity } from '@/hooks/use-jobwizard';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { jobDomain, routeJobId, safeJobUrl, type Job } from '@/lib/jobwizard-model';
export default function JobDetailScreen() {
  const auth = useAuth(),
    { id } = useLocalSearchParams<{ id: string }>();
  if (!auth.user)
    return (
      <ScreenState
        loading={!auth.userError}
        title={
          auth.userError
            ? 'Couldn’t load your account'
            : 'Loading your account'
        }
        onRetry={auth.userError ? auth.retryUser : undefined}
      />
    );
  return (
    <JobDetail key={`${auth.user.id}:${String(id)}`} id={routeJobId(id)} />
  );
}
function JobDetail({ id }: { id: number }) {
  const query = useJob(id),
    activity = useJobActivity(),
    router = useRouter();
  const [editing, setEditing] = useState<Job | null>(null),
    [refreshing, setRefreshing] = useState(false),
    [linkError, setLinkError] = useState<string | null>(null),
    [linkNotice, setLinkNotice] = useState<string | null>(null),
    [linkBusy, setLinkBusy] = useState(false);
  const linkLock = useRef(false);
  const unavailable =
    !id ||
    (query.error instanceof ApiError &&
      [403, 404].includes(query.error.status));
  if (unavailable && !editing)
    return (
      <Screen>
        <PageHeading
          title="Job unavailable"
          subtitle="It may have been removed or belong to another account."
        />
        <NativeAction
          label="Back to Jobwizard"
          onPress={() => router.replace('/jobwizard')}
        />
      </Screen>
    );
  if (!query.data && !editing && query.isPending)
    return (
      <ScreenState
        loading={!query.isPaused}
        title={query.isPaused ? 'You’re offline' : 'Loading job'}
      />
    );
  if (!query.data && !editing)
    return (
      <ScreenState
        title="Couldn’t load job"
        onRetry={() => void query.refetch()}
      />
    );
  const job = query.data?.job ?? editing!;
  const onAction = async (action: JobAction) => {
    if (action === 'edit') {
      if (!activity.attempt) setEditing(job);
      return;
    }
    if (action === 'archive') {
      if (!activity.ready || activity.attempt) return;
      await activity.session.begin({
        kind: 'save', jobId: job.id,
        input: { expected_revision: job.revision, archived: !job.archived_at },
      });
      return;
    }
    if (linkLock.current || (action === 'open' && !safeJobUrl(job.listing_url))) return;
    linkLock.current = true;
    setLinkBusy(true);
    setLinkError(null);
    setLinkNotice(null);
    try {
      if (action === 'open') await Linking.openURL(job.listing_url);
      else {
        const copied = await Clipboard.setStringAsync(job.listing_url);
        if (!copied) throw new Error('Clipboard unavailable');
        setLinkNotice('Link copied');
        AccessibilityInfo.announceForAccessibility('Link copied');
      }
    } catch {
      setLinkError(action === 'open'
        ? 'Couldn’t open the listing. Try Copy link to open it in your browser.'
        : 'Couldn’t copy the link. You can find it in Edit job.');
    } finally {
      linkLock.current = false;
      setLinkBusy(false);
    }
  };
  return (
    <>
      <Stack.Screen options={{ title: 'Job' }} />
      <Screen
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={() => {
              setRefreshing(true);
              void Promise.all([
                query.refetch(),
                activity.session.check(),
              ]).finally(() => setRefreshing(false));
            }}
          />
        }
      >
        <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 12 }}>
          <View style={{ flex: 1 }}>
            <PageHeading
              title={job.title}
              subtitle={job.company_name}
              eyebrow={job.archived_at ? 'Archived job' : 'Saved job'}
            />
          </View>
          <JobActionsMenu
            archived={!!job.archived_at}
            canOpen={!linkBusy && safeJobUrl(job.listing_url)}
            canCopy={!linkBusy && !!job.listing_url}
            canEdit={!activity.attempt}
            canArchive={activity.ready && !activity.attempt}
            onAction={(action) => void onAction(action)}
          />
        </View>
        <ThemedText type="small" themeColor="textSecondary" accessibilityLiveRegion="polite">
          {linkNotice ?? jobDomain(job)}
          {job.saved_at || job.posted_date ? (
            ` · ${job.saved_at ? 'Saved' : 'Date recorded'} ${new Date(
              (job.saved_at ?? job.posted_date)!,
            ).toLocaleDateString()}`
          ) : ''}
        </ThemedText>
        {!safeJobUrl(job.listing_url) ? (
          <InlineError message="This listing link is unsafe or invalid. Edit the job to replace it." />
        ) : null}
        {linkError ? <InlineError message={linkError} /> : null}
        <JobActivityStatus activity={activity} />
        {query.isError ? (
          <InlineError
            message="Couldn’t refresh. This is the last loaded job."
            onRetry={() => void query.refetch()}
          />
        ) : null}
        <JobImportantDetails details={job.accepted_details} />
        <NativeAction
          label="Suggest details"
          secondary
          disabled={!!activity.attempt}
          onPress={() => setEditing(job)}
        />
        <JobScreenshot job={job} activity={activity} />
      </Screen>
      {editing ? (
        <JobForm
          job={editing}
          onSaved={() => setEditing(null)}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}
