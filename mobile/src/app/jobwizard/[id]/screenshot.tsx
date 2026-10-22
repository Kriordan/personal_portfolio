import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import ScreenshotCanvas from '@/components/screenshot-canvas';
import { InlineError, NativeAction, ScreenState } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useJob, useJobCapture } from '@/hooks/use-jobwizard';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { routeJobId } from '@/lib/jobwizard-model';
import { validScreenshotSize } from '@/lib/screenshot-viewer';

export default function ScreenshotScreen() {
  const { id } = useLocalSearchParams<{ id: string }>(),
    { user } = useAuth();
  if (!user) return <ScreenState loading title="Loading your account" />;
  return <Screenshot key={`${user.id}:${String(id)}`} id={routeJobId(id)} />;
}
function Screenshot({ id }: { id: number }) {
  const router = useRouter(),
    job = useJob(id),
    query = useJobCapture(id, !!job.data);
  const image = query.data?.capture.image;
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const [expiredUrl, setExpiredUrl] = useState<string | null>(null);
  const renewedArtifact = useRef<string | null>(null),
    renewedExpiry = useRef<string | null>(null);
  const { refetch } = query;
  useEffect(() => {
    if (!image) return;
    const delay = Date.parse(image.expires_at) - Date.now();
    const timer = setTimeout(
      () => {
        setExpiredUrl(image.url);
        if (renewedExpiry.current !== image.url) {
          renewedExpiry.current = image.url;
          void refetch();
        }
      },
      Number.isFinite(delay) ? Math.max(0, delay) : 0,
    );
    return () => clearTimeout(timer);
  }, [image, refetch]);
  const close = () => {
    if (router.canGoBack()) router.back();
    else if (id)
      router.replace({ pathname: '/jobwizard/[id]', params: { id } });
    else router.replace('/jobwizard');
  };
  const unavailable =
    !id ||
    [job.error, query.error].some(
      (error) =>
        error instanceof ApiError && [401, 403, 404].includes(error.status),
    );
  let body;
  if (unavailable) body = <ScreenState title="Screenshot unavailable" />;
  else if (
    (!job.data && job.isPending) ||
    (!query.data && query.isPending && !!job.data)
  )
    body = (
      <ScreenState
        loading={!job.isPaused && !query.isPaused}
        title={
          job.isPaused || query.isPaused
            ? 'You’re offline'
            : 'Loading screenshot'
        }
      />
    );
  else if (!job.data || (!query.data && query.isError))
    body = (
      <ScreenState
        title="Couldn’t load screenshot"
        onRetry={() => {
          void job.refetch();
          void refetch();
        }}
      />
    );
  else if (!image) body = <ScreenState title="No screenshot available" />;
  else if (!validScreenshotSize(image.width, image.height))
    body = <ScreenState title="Screenshot unavailable" />;
  else if (expiredUrl === image.url || failedUrl === image.url)
    body = (
      <View style={styles.message}>
        <ThemedText>Screenshot access expired or is unavailable.</ThemedText>
        <NativeAction
          label={
            query.isFetching
              ? 'Refreshing access…'
              : 'Refresh screenshot access'
          }
          disabled={query.isFetching}
          onPress={() => void refetch()}
        />
      </View>
    );
  else
    body = (
      <>
        {query.isError ? (
          <InlineError
            message="Couldn’t refresh screenshot access. Showing the last loaded image."
            onRetry={() => void refetch()}
          />
        ) : null}
        <View style={styles.caption}>
          <ThemedText type="small" numberOfLines={2}>
            {job.data.job.title}
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Captured {new Date(image.captured_at).toLocaleString()}
            {image.outdated ? ' · Older listing URL' : ''}
          </ThemedText>
        </View>
        <ScreenshotCanvas
          key={image.captured_at}
          uri={image.url}
          width={image.width}
          height={image.height}
          label={`Listing screenshot for ${job.data.job.title}`}
          onError={() => {
            setFailedUrl(image.url);
            // A bad object must not produce an endless loop of freshly signed URLs.
            if (renewedArtifact.current !== image.captured_at) {
              renewedArtifact.current = image.captured_at;
              void refetch();
            }
          }}
        />
      </>
    );
  return (
    <SafeAreaView style={styles.fill} edges={['left', 'right', 'bottom']}>
      <Stack.Screen
        options={{
          title: 'Screenshot',
          headerLeft: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Close screenshot"
              onPress={close}
              style={styles.close}
            >
              <ThemedText themeColor="accent">Close</ThemedText>
            </Pressable>
          ),
        }}
      />
      {body}
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  fill: { flex: 1 },
  close: { minWidth: 44, minHeight: 44, justifyContent: 'center' },
  caption: { paddingHorizontal: 16, paddingTop: 8, gap: 4 },
  message: { padding: 24, gap: 16 },
});
