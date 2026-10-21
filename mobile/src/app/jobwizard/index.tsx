import { Host } from '@expo/ui';
import { useRouter } from 'expo-router';
import { memo, useCallback, useMemo, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { NativeChoice } from '@/components/native-choice';
import { NativeField } from '@/components/native-form';
import { JobActivityStatus } from '@/components/jobwizard-content';
import {
  InlineError,
  NativeAction,
  PageHeading,
  ScreenState,
  screenStyles,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useJobActivity, useJobs } from '@/hooks/use-jobwizard';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import {
  browseJobs,
  jobDomain,
  jobSorts,
  jobViews,
  type Job,
  type JobSort,
  type JobView,
} from '@/lib/jobwizard-model';

const JobRow = memo(function JobRow({ job }: { job: Job }) {
  const theme = useTheme(),
    router = useRouter();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${job.title}. ${job.company_name}${job.archived_at ? '. Archived' : ''}`}
      onPress={() =>
        router.push({ pathname: '/jobwizard/[id]', params: { id: job.id } })
      }
      style={({ pressed }) => [
        styles.row,
        {
          backgroundColor: pressed
            ? theme.backgroundSelected
            : theme.backgroundElement,
        },
      ]}
    >
      <View style={styles.body}>
        <ThemedText style={styles.title}>{job.title}</ThemedText>
        <ThemedText>{job.company_name}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {jobDomain(job)}
        </ThemedText>
        {job.saved_at ? (
          <ThemedText type="small" themeColor="textSecondary">
            Saved {new Date(job.saved_at).toLocaleDateString()}
          </ThemedText>
        ) : null}
        {job.archived_at ? (
          <ThemedText type="smallBold" themeColor="textSecondary">
            Archived
          </ThemedText>
        ) : null}
      </View>
      <ThemedText accessible={false} themeColor="textSecondary">
        ›
      </ThemedText>
    </Pressable>
  );
});
const keyForJob = (job: Job) => String(job.id);
export default function JobwizardScreen() {
  const auth = useAuth();
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
  return <Organizer key={auth.user.id} />;
}
function Organizer() {
  const theme = useTheme(),
    router = useRouter(),
    query = useJobs(),
    activity = useJobActivity(),
    search = useNativeText();
  const [view, setView] = useState<JobView>('active'),
    [sort, setSort] = useState<JobSort>('newest'),
    [refreshing, setRefreshing] = useState(false);
  const jobs = useMemo(
    () => browseJobs(query.data?.jobs ?? [], search.text, view, sort),
    [query.data?.jobs, search.text, view, sort],
  );
  const renderJob = useCallback(
    ({ item }: { item: Job }) => <JobRow job={item} />,
    [],
  );
  const refresh = () => {
    setRefreshing(true);
    void Promise.all([query.refetch(), activity.session.check()]).finally(() =>
      setRefreshing(false),
    );
  };
  if (!query.data && query.isPending)
    return (
      <ScreenState
        loading={!query.isPaused}
        title={query.isPaused ? 'You’re offline' : 'Loading jobs'}
        message={
          query.isPaused ? 'Reconnect to load your saved jobs.' : undefined
        }
      />
    );
  if (!query.data)
    return (
      <ScreenState
        title="Couldn’t load jobs"
        message="Check your connection and try again."
        onRetry={refresh}
      />
    );
  return (
    <SafeAreaView
      edges={['left', 'right', 'bottom']}
      style={{ flex: 1, backgroundColor: theme.background }}
    >
      <FlatList
        data={jobs}
        keyExtractor={keyForJob}
        renderItem={renderJob}
        contentContainerStyle={screenStyles.collection}
        contentInsetAdjustmentBehavior="automatic"
        automaticallyAdjustKeyboardInsets
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={refresh} />
        }
        ListHeaderComponent={
          <View style={screenStyles.gap}>
            <PageHeading
              title="Jobwizard"
              subtitle="Your private collection of opportunities, ready when you are."
            />
            <NativeAction
              label="Add job"
              onPress={() => router.push('/jobwizard/new')}
              disabled={!activity.ready || !!activity.attempt}
            />
            <JobActivityStatus activity={activity} />
            {activity.confirmed && 'job' in activity.confirmed.result ? (
              <ThemedText type="small" accessibilityLiveRegion="polite">
                Job saved: {activity.confirmed.result.job.title}
              </ThemedText>
            ) : null}
            <Host matchContents={{ vertical: true }}>
              <NativeField
                label="Search jobs"
                placeholder="Title, company or website"
                {...search.input}
                autoCorrect={false}
              />
            </Host>
            {search.text ? (
              <NativeAction
                label="Clear search"
                secondary
                onPress={search.clear}
              />
            ) : null}
            <NativeChoice
              label="Show"
              value={view}
              options={jobViews}
              onChange={setView}
            />
            <NativeChoice
              label="Sort"
              value={sort}
              options={jobSorts}
              onChange={setSort}
            />
            <ThemedText
              type="smallBold"
              themeColor="textSecondary"
              style={styles.count}
            >
              {jobs.length} {jobs.length === 1 ? 'job' : 'jobs'}
            </ThemedText>
            {query.isError ? (
              <InlineError
                message="Couldn’t refresh. Showing the last loaded jobs."
                onRetry={refresh}
              />
            ) : null}
            {query.isPaused ? (
              <ThemedText themeColor="textSecondary">
                You’re offline. Showing the last loaded jobs.
              </ThemedText>
            ) : null}
          </View>
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <ThemedText type="subtitle">
              {search.text.trim()
                ? 'No matching jobs'
                : !query.data.jobs.length
                  ? 'Your next opportunity starts here.'
                  : `No ${view === 'all' ? 'saved' : view} jobs`}
            </ThemedText>
            <ThemedText themeColor="textSecondary">
              {search.text.trim()
                ? 'Try another title, company or website.'
                : view === 'archived'
                  ? 'Archived jobs will appear here. You can restore them anytime.'
                  : 'Save a job’s title, company and listing link to keep it close.'}
            </ThemedText>
          </View>
        }
      />
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  row: {
    borderRadius: 18,
    padding: 18,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 12,
  },
  body: { flex: 1, gap: 5 },
  title: { fontWeight: '600' },
  count: { marginVertical: 14 },
  empty: { paddingVertical: 30, gap: 12 },
});
