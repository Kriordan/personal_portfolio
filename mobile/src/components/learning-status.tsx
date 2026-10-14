import { useRouter } from 'expo-router';
import { View } from 'react-native';
import { Card, InlineError, NativeAction } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import type { useLearningActivity } from '@/hooks/use-learning';

export function LearningStatus({
  activity,
  onFreshQueue,
}: {
  activity: ReturnType<typeof useLearningActivity>;
  onFreshQueue?: () => void;
}) {
  const router = useRouter();
  const busy = activity.phase === 'saving' || activity.phase === 'checking';
  if (!activity.ready)
    return (
      <InlineError
        message={activity.error ?? 'Loading saved review state…'}
        onRetry={
          activity.error ? () => void activity.session.restore() : undefined
        }
      />
    );
  if (!activity.attempt && !activity.error) return null;
  if (!activity.attempt) return <InlineError message={activity.error!} />;
  return (
    <Card>
      <ThemedText
        type="smallBold"
        accessibilityRole="header"
        accessibilityLiveRegion="polite"
      >
        {activity.phase === 'saving'
          ? 'Saving rating…'
          : activity.phase === 'checking'
            ? 'Checking whether your rating saved…'
            : activity.phase === 'conflict'
              ? 'Review needs a fresh queue'
              : 'Save confirmation pending'}
      </ThemedText>
      {activity.error ? (
        <ThemedText themeColor="textSecondary">{activity.error}</ThemedText>
      ) : null}
      {activity.phase === 'conflict' ? (
        <NativeAction
          label="Load a fresh queue"
          onPress={() => {
            void activity.session.dismissConflict().then((cleared) => {
              if (cleared) {
                if (onFreshQueue) onFreshQueue();
                else router.push('/learning/review');
              }
            });
          }}
        />
      ) : (
        <View style={{ gap: 8 }}>
          <NativeAction
            label="Check saved rating"
            disabled={busy}
            secondary
            onPress={() => void activity.session.check()}
          />
          <NativeAction
            label="Retry the same rating"
            disabled={busy}
            secondary
            onPress={() => void activity.session.retry()}
          />
        </View>
      )}
    </Card>
  );
}
