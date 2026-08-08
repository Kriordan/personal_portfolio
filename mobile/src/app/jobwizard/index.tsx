import { useQuery } from '@tanstack/react-query';
import { Redirect, useRouter } from 'expo-router';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  View,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { jobwizardApi, jobwizardKeys, type Job } from '@/lib/jobwizard-api';

function JobRow({ job, onPress }: { job: Job; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.row,
        { backgroundColor: pressed ? theme.backgroundSelected : theme.backgroundElement },
      ]}
    >
      <View style={styles.rowBody}>
        <ThemedText>{job.title}</ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          {job.company_name}
          {job.posted_date ? ` · ${new Date(job.posted_date).toLocaleDateString()}` : ''}
        </ThemedText>
      </View>
      <ThemedText type="small" themeColor="textSecondary">
        ›
      </ThemedText>
    </Pressable>
  );
}

export default function JobwizardScreen() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const jobsQuery = useQuery({
    queryKey: jobwizardKeys.jobs(),
    queryFn: jobwizardApi.getJobs,
    enabled: isAuthenticated === true,
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (jobsQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (jobsQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Couldn’t load your jobs.</ThemedText>
        <Pressable style={styles.button} onPress={() => jobsQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const { jobs } = jobsQuery.data;

  return (
    <ThemedView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl
            refreshing={jobsQuery.isRefetching}
            onRefresh={() => jobsQuery.refetch()}
          />
        }
      >
        <Pressable style={styles.button} onPress={() => router.push('/jobwizard/new')}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            New Job
          </ThemedText>
        </Pressable>

        <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
          JOBS
        </ThemedText>
        {jobs.length === 0 ? (
          <ThemedText type="small" themeColor="textSecondary">
            No jobs yet. Add one to get started.
          </ThemedText>
        ) : (
          jobs.map((job) => (
            <JobRow key={job.id} job={job} onPress={() => router.push(`/jobwizard/${job.id}`)} />
          ))
        )}
      </ScrollView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    gap: Spacing.three,
  },
  scrollContent: {
    padding: Spacing.three,
    gap: Spacing.two,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  sectionHeader: {
    marginTop: Spacing.three,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
  },
  rowBody: {
    flex: 1,
    gap: Spacing.half,
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    color: '#ffffff',
  },
});
