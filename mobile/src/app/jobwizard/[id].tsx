import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { RefreshControl } from 'react-native';
import { JobForm } from '@/components/job-form';
import {
  JobActivityStatus,
  JobLink,
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
import { routeJobId, safeJobUrl, type Job } from '@/lib/jobwizard-model';
export default function JobDetailScreen() {
  const auth = useAuth(),
    { id } = useLocalSearchParams<{ id: string }>();
  if (!auth.user)
    return (
      <ScreenState
        loading={!auth.userError}
        title={
          auth.userError ? 'Couldn’t load your account' : 'Loading your account'
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
    [refreshing, setRefreshing] = useState(false);
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
        <PageHeading
          title={job.title}
          subtitle={job.company_name}
          eyebrow={job.archived_at ? 'Archived job' : 'Saved job'}
        />
        <ThemedText selectable>{job.listing_url}</ThemedText>
        {safeJobUrl(job.listing_url) ? (
          <JobLink url={job.listing_url} />
        ) : (
          <InlineError message="This listing link is unsafe or invalid. Edit the job to replace it." />
        )}
        {job.saved_at || job.posted_date ? (
          <ThemedText type="small" themeColor="textSecondary">
            {job.saved_at ? 'Saved' : 'Date recorded'}{' '}
            {new Date((job.saved_at ?? job.posted_date)!).toLocaleDateString()}
          </ThemedText>
        ) : null}
        <NativeAction
          label="Edit job"
          secondary
          onPress={() => setEditing(job)}
          disabled={!!activity.attempt}
        />
        <NativeAction
          label={job.archived_at ? 'Restore job' : 'Archive job'}
          secondary
          disabled={!activity.ready || !!activity.attempt}
          onPress={() =>
            void activity.session.begin({
              kind: 'save',
              jobId: job.id,
              input: {
                expected_revision: job.revision,
                archived: !job.archived_at,
              },
            })
          }
        />
        <ThemedText type="small" themeColor="textSecondary">
          {job.archived_at
            ? 'Restore to return this job to Active.'
            : 'Archiving keeps this job and its screenshot. Restore it anytime.'}
        </ThemedText>
        <JobActivityStatus activity={activity} />
        {query.isError ? (
          <InlineError
            message="Couldn’t refresh. This is the last loaded job."
            onRetry={() => void query.refetch()}
          />
        ) : null}
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
