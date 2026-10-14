import { useQuery } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import {
  AccessibilityInfo,
  Pressable,
  StyleSheet,
  View,
  useWindowDimensions,
} from 'react-native';
import {
  LearningAccountState,
  LearningAnswer,
  LearningText,
  LearningUnavailable,
  cardTypeLabel,
} from '@/components/learning-content';
import { LearningStatus } from '@/components/learning-status';
import {
  Card,
  InlineError,
  NativeAction,
  PageHeading,
  Screen,
  ScreenState,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useLearningActivity } from '@/hooks/use-learning';
import { useTheme } from '@/hooks/use-theme';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import {
  learningApi,
  learningKeys,
  RATINGS,
  validNoteId,
  type ReviewQueue,
  type ReviewCard,
} from '@/lib/learning-api';
import { learningQueueOptions } from '@/lib/learning-cache';

type Activity = ReturnType<typeof useLearningActivity>;
export default function ReviewScreen() {
  const { user } = useAuth();
  const { note_id: noteId } = useLocalSearchParams<{ note_id?: string }>();
  if (noteId !== undefined && !validNoteId(noteId))
    return <LearningUnavailable />;
  return user ? (
    <ReviewContent userId={user.id} noteId={noteId} />
  ) : (
    <LearningAccountState />
  );
}
function ReviewContent({
  userId,
  noteId,
}: {
  userId: number;
  noteId?: string;
}) {
  const activity = useLearningActivity(userId);
  const router = useRouter();
  const query = useQuery({
    ...learningQueueOptions,
    queryKey: learningKeys.review(userId, noteId),
    queryFn: () => learningApi.getReviewQueue(noteId),
    enabled: activity.ready && !activity.attempt,
  });
  const refresh = () => {
    void query.refetch();
  };
  if (!activity.ready || (!query.data && activity.attempt))
    return (
      <Screen>
        <PageHeading title="Review" />
        <LearningStatus activity={activity} onFreshQueue={refresh} />
        <NativeAction
          label="Back to Learning"
          secondary
          onPress={() => router.replace('/learning')}
        />
      </Screen>
    );
  if (!query.data && query.isPending)
    return (
      <ScreenState
        loading={!query.isPaused}
        title={query.isPaused ? 'You’re offline' : 'Preparing your review'}
        message={
          query.isPaused
            ? 'Reconnect to get a current review queue.'
            : undefined
        }
      />
    );
  if (query.error instanceof ApiError && query.error.status === 404)
    return <LearningUnavailable />;
  if (!query.data)
    return (
      <ScreenState
        title="Couldn’t prepare your review"
        message="Your saved progress is unchanged. Try again when connected."
        onRetry={refresh}
      />
    );
  if (!query.data.cards.length)
    return (
      <Screen>
        <PageHeading
          title="No cards due"
          subtitle={
            noteId
              ? 'You’re caught up in this note. You can still browse and study.'
              : 'You’re caught up for now. Come back when more cards are due.'
          }
        />
        <NativeAction
          label="Back to Learning"
          onPress={() => router.replace('/learning')}
        />
        <NativeAction
          label="Check again"
          secondary
          disabled={query.isFetching}
          onPress={refresh}
        />
        {query.isError ? (
          <InlineError
            message="Couldn’t refresh the due queue."
            onRetry={refresh}
          />
        ) : null}
      </Screen>
    );
  return (
    <ReviewSession
      key={query.dataUpdatedAt}
      queue={query.data}
      activity={activity}
      refresh={refresh}
      refreshing={query.isFetching}
      refreshFailed={query.isError}
    />
  );
}
function ReviewSession({
  queue,
  activity,
  refresh,
  refreshing,
  refreshFailed,
}: {
  queue: ReviewQueue;
  activity: Activity;
  refresh: () => void;
  refreshing: boolean;
  refreshFailed: boolean;
}) {
  const router = useRouter();
  const [sessionId] = useState(() => Crypto.randomUUID());
  const results = activity.confirmed.filter(
    (entry) => entry.input.session_id === sessionId,
  );
  const card = queue.cards[results.length];
  const previous = results.at(-1)?.result;
  if (!card)
    return (
      <Screen>
        <PageHeading
          title="Session complete"
          subtitle={`${results.length} ratings saved. Your progress is up to date for this session.`}
        />
        <Card>
          {RATINGS.map((rating) => (
            <ThemedText key={rating.value}>
              {rating.label}:{' '}
              {
                results.filter((entry) => entry.result.rating === rating.value)
                  .length
              }
            </ThemedText>
          ))}
        </Card>
        <ThemedText themeColor="textSecondary">
          Review more to check the current due queue.
        </ThemedText>
        <NativeAction
          label={refreshing ? 'Checking due cards…' : 'Review more'}
          disabled={refreshing}
          onPress={refresh}
        />
        <NativeAction
          label="Back to Learning"
          secondary
          onPress={() => router.replace('/learning')}
        />
        {refreshFailed ? (
          <InlineError
            message="Your ratings are saved, but the next queue couldn’t load."
            onRetry={refresh}
          />
        ) : null}
      </Screen>
    );
  return (
    <Screen>
      <PageHeading
        title="Review"
        subtitle={`Card ${results.length + 1} of ${queue.cards.length} · ${queue.total_due} due when started`}
      />
      {previous ? (
        <ThemedText
          type="small"
          themeColor="textSecondary"
          accessibilityLiveRegion="polite"
        >
          Previous answer saved · {previous.next_review_display}
        </ThemedText>
      ) : null}
      <ReviewQuestion
        key={card.card_id}
        card={card}
        activity={activity}
        sessionId={sessionId}
      />
      <LearningStatus activity={activity} onFreshQueue={refresh} />
      <NativeAction
        label="Back to Learning"
        secondary
        onPress={() => router.replace('/learning')}
      />
      <ThemedText type="small" themeColor="textSecondary">
        Each confirmed rating is saved. You can finish this session at any time.
      </ThemedText>
    </Screen>
  );
}
function ReviewQuestion({
  card,
  activity,
  sessionId,
}: {
  card: ReviewCard;
  activity: Activity;
  sessionId: string;
}) {
  const [revealed, setRevealed] = useState(false);
  const [shownAt] = useState(Date.now);
  const { fontScale, width } = useWindowDimensions();
  const theme = useTheme();
  const disabled =
    !!activity.attempt || !activity.ready || activity.phase === 'conflict';
  const stacked = fontScale > 1.3 || width < 360;
  return (
    <>
      <Card>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {card.note_title} · {cardTypeLabel(card.type)}
        </ThemedText>
        <LearningText text={card.prompt} />
        {revealed ? (
          <>
            <ThemedText type="smallBold" accessibilityRole="header">
              Answer
            </ThemedText>
            <LearningAnswer card={card} />
          </>
        ) : null}
      </Card>
      {!revealed ? (
        <NativeAction
          label="Show answer"
          onPress={() => {
            setRevealed(true);
            AccessibilityInfo.announceForAccessibility(
              'Answer shown. Rate your recall when ready.',
            );
          }}
        />
      ) : (
        <View style={styles.ratings}>
          {RATINGS.map((rating) => (
            <Pressable
              key={rating.value}
              disabled={disabled}
              accessibilityRole="button"
              accessibilityLabel={`${rating.label}. ${rating.description}`}
              accessibilityState={{
                disabled,
                busy: activity.phase === 'saving',
              }}
              style={({ pressed }) => [
                styles.rating,
                {
                  width: stacked ? '100%' : '48%',
                  backgroundColor: pressed
                    ? theme.backgroundSelected
                    : theme.backgroundElement,
                  opacity: disabled ? 0.6 : 1,
                },
              ]}
              onPress={() =>
                void activity.session.begin(
                  card,
                  rating.value,
                  Date.now() - shownAt,
                  sessionId,
                )
              }
            >
              <ThemedText
                themeColor={rating.value === 0 ? 'danger' : 'accent'}
                type="smallBold"
              >
                {rating.label}
              </ThemedText>
              <ThemedText type="small" themeColor="textSecondary">
                {rating.description}
              </ThemedText>
            </Pressable>
          ))}
        </View>
      )}
    </>
  );
}
const styles = StyleSheet.create({
  ratings: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    gap: 12,
  },
  rating: { minHeight: 72, padding: 16, borderRadius: 16, gap: 4 },
});
