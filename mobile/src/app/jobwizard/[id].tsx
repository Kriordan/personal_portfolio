import { useQuery } from '@tanstack/react-query';
import { Redirect, Stack, useLocalSearchParams } from 'expo-router';
import {
  ActivityIndicator,
  Image,
  Linking,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
} from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useAuth } from '@/lib/auth-context';
import { jobScreenshotUrl, jobwizardApi, jobwizardKeys } from '@/lib/jobwizard-api';

export default function JobDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { isAuthenticated } = useAuth();
  const jobId = Number(id);

  const jobQuery = useQuery({
    queryKey: jobwizardKeys.job(jobId),
    queryFn: () => jobwizardApi.getJob(jobId),
    enabled: Number.isFinite(jobId) && isAuthenticated === true,
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (jobQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (jobQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">
          {jobQuery.error instanceof Error ? jobQuery.error.message : 'Couldn’t load job.'}
        </ThemedText>
        <Pressable style={styles.button} onPress={() => jobQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  const { job } = jobQuery.data;
  const screenshotUrl = jobScreenshotUrl(job);

  return (
    <ThemedView style={styles.container}>
      <Stack.Screen options={{ title: job.title }} />
      <ScrollView
        contentContainerStyle={styles.scrollContent}
        refreshControl={
          <RefreshControl refreshing={jobQuery.isRefetching} onRefresh={() => jobQuery.refetch()} />
        }
      >
        <ThemedText type="subtitle">{job.title}</ThemedText>
        <ThemedText themeColor="textSecondary">{job.company_name}</ThemedText>
        {job.posted_date ? (
          <ThemedText type="small" themeColor="textSecondary">
            Posted {new Date(job.posted_date).toLocaleDateString()}
          </ThemedText>
        ) : null}

        <Pressable style={styles.button} onPress={() => Linking.openURL(job.listing_url)}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Open Original Listing
          </ThemedText>
        </Pressable>

        {screenshotUrl ? (
          <>
            <ThemedText type="smallBold" themeColor="textSecondary" style={styles.sectionHeader}>
              LISTING SCREENSHOT
            </ThemedText>
            <Pressable onPress={() => Linking.openURL(screenshotUrl)}>
              <Image
                source={{ uri: screenshotUrl }}
                style={styles.screenshot}
                resizeMode="cover"
              />
            </Pressable>
          </>
        ) : (
          <ThemedText type="small" themeColor="textSecondary" style={styles.sectionHeader}>
            No screenshot available for this listing.
          </ThemedText>
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
  screenshot: {
    width: '100%',
    height: 480,
    borderRadius: Spacing.two,
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
