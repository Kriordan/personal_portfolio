import { Host, type TextInputRef } from '@expo/ui';
import { useRouter } from 'expo-router';
import { memo, useCallback, useMemo, useRef, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { JobBrowseChoice } from '@/components/job-browse-choice';
import { JobToolbarIcon } from '@/components/job-toolbar-icon';
import { NativeField } from '@/components/native-form';
import { JobActivityStatus } from '@/components/jobwizard-content';
import {
  InlineError,
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
    [searchOpen, setSearchOpen] = useState(false),
    [refreshing, setRefreshing] = useState(false);
  const searchRef = useRef<TextInputRef>(null);
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
          <View style={styles.header}>
            <View style={styles.headingRow}>
              <View style={styles.headingTitle}>
                <PageHeading title="Jobwizard" />
              </View>
              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Search jobs"
                  accessibilityState={{ expanded: searchOpen }}
                  onPress={() => {
                    setSearchOpen(true);
                    searchRef.current?.focus();
                  }}
                  style={styles.iconButton}
                >
                  <JobToolbarIcon name="search" />
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Add job"
                  disabled={!activity.ready || !!activity.attempt}
                  accessibilityState={{ disabled: !activity.ready || !!activity.attempt }}
                  onPress={() => router.push('/jobwizard/new')}
                  style={[
                    styles.iconButton,
                    { backgroundColor: theme.accentSoft },
                    (!activity.ready || !!activity.attempt) && { opacity: 0.4 },
                  ]}
                >
                  <JobToolbarIcon name="add" />
                </Pressable>
              </View>
            </View>
            <ThemedText type="small" themeColor="textSecondary">
              {jobs.length} {view === 'all' ? '' : `${view} `}
              {jobs.length === 1 ? 'job' : 'jobs'} · Private
            </ThemedText>
            {searchOpen ? (
              <View style={styles.searchRow}>
                <Host matchContents={{ vertical: true }} style={styles.searchField}>
                  <NativeField
                    ref={searchRef}
                    label="Search jobs"
                    placeholder="Title, company or website"
                    {...search.input}
                    autoCorrect={false}
                    autoCapitalize="none"
                    autoFocus
                    returnKeyType="search"
                    onSubmitEditing={() => searchRef.current?.blur()}
                  />
                </Host>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Cancel search"
                  onPress={() => {
                    searchRef.current?.blur();
                    search.clear();
                    setSearchOpen(false);
                  }}
                  style={styles.cancelSearch}
                >
                  <ThemedText themeColor="accent">Cancel</ThemedText>
                </Pressable>
              </View>
            ) : null}
            <View style={styles.browseRow}>
              <JobBrowseChoice
                label="Filter jobs"
                icon="filter"
                value={view}
                options={jobViews}
                onChange={setView}
              />
              <JobBrowseChoice
                label="Sort jobs"
                icon="sort"
                value={sort}
                options={jobSorts}
                onChange={setSort}
              />
            </View>
            <JobActivityStatus activity={activity} />
            {activity.confirmed && 'job' in activity.confirmed.result ? (
              <ThemedText type="small" accessibilityLiveRegion="polite">
                Job saved: {activity.confirmed.result.job.title}
              </ThemedText>
            ) : null}
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
  header: { gap: 8, paddingBottom: 12 },
  headingRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', columnGap: 8 },
  headingTitle: { flexGrow: 1, flexShrink: 1, minWidth: 180 },
  actions: { flexDirection: 'row', gap: 4 },
  iconButton: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
  browseRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: 24 },
  searchRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  searchField: { flex: 1 },
  cancelSearch: { minHeight: 48, justifyContent: 'center', paddingHorizontal: 4 },
  empty: { paddingVertical: 30, gap: 12 },
});
