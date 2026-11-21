import { useQuery } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import { useState } from 'react';
import { LearningUnavailable } from './learning-content';
import { LearningStatus } from './learning-status';
import { ReviewQuestion } from './review-question';
import {
  Card,
  InlineError,
  NativeAction,
  NavRow,
  Screen,
  ScreenState,
} from './screen';
import { ThemedText } from './themed-text';
import { useLearningActivity } from '@/hooks/use-learning';
import { ApiError } from '@/lib/api-client';
import {
  responseRoute,
  type FeedbackSource,
  type FocusedReview,
} from '@/lib/feedback-response-model';
import { learningQueueOptions } from '@/lib/learning-cache';
import { practiceKeys } from '@/lib/practice-model';
import { practiceApi } from '@/lib/practice-runtime';

export function FocusedFeedbackReview({
  userId,
  source,
}: {
  userId: number;
  source: FeedbackSource;
}) {
  const activity = useLearningActivity(userId);
  const query = useQuery({
    ...learningQueueOptions,
    queryKey: practiceKeys.focused(userId, source),
    queryFn: () => practiceApi.focusedReview(source),
    enabled: activity.ready && !activity.attempt,
  });
  const refresh = () => {
    void query.refetch();
  };
  if (
    query.error instanceof ApiError &&
    [403, 404].includes(query.error.status)
  )
    return (
      <LearningUnavailable
        title="Review unavailable"
        message="This finding is no longer available to this account."
      />
    );
  if (!activity.ready || (!query.data && activity.attempt))
    return (
      <Screen>
        <Header source={source} />
        <LearningStatus activity={activity} onFreshQueue={refresh} />
      </Screen>
    );
  if (!query.data)
    return (
      <ScreenState
        loading={query.isFetching}
        title="Loading focused review"
        message="Reconnect to load the remaining linked questions. Your saved ratings are unchanged."
        onRetry={refresh}
      />
    );
  return (
    <ReviewPass
      key={query.dataUpdatedAt}
      userId={userId}
      source={source}
      queue={query.data}
      activity={activity}
      refresh={refresh}
      refreshing={query.isFetching}
      failed={query.isError}
    />
  );
}
function Header({ source }: { source: FeedbackSource }) {
  return (
    <>
      <ThemedText type="title" accessibilityRole="header">
        Focused review
      </ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        Snapshot {source.submission_sequence} · Linked questions
      </ThemedText>
      <NavRow title="Return to your response" href={responseRoute(source)} />
    </>
  );
}
function ReviewPass({
  userId,
  source,
  queue,
  activity,
  refresh,
  refreshing,
  failed,
}: {
  userId: number;
  source: FeedbackSource;
  queue: FocusedReview;
  activity: ReturnType<typeof useLearningActivity>;
  refresh: () => void;
  refreshing: boolean;
  failed: boolean;
}) {
  const [passId] = useState(() => Crypto.randomUUID());
  const confirmed = activity.confirmed.filter(
    (r) => r.input.session_id === passId,
  );
  const card = queue.questions[confirmed.length];
  const previous = confirmed.at(-1)?.result;
  return (
    <Screen key={card?.card_id ?? 'done'}>
      <Header source={source} />
      <ThemedText type="subtitle" accessibilityRole="header">
        {queue.finding.title}
      </ThemedText>
      <LearningStatus activity={activity} onFreshQueue={refresh} />
      {previous ? (
        <ThemedText type="small" accessibilityLiveRegion="polite">
          Rating saved · {previous.next_review_display}
        </ThemedText>
      ) : null}
      {!queue.accepted ? (
        <Card>
          <ThemedText type="subtitle">Review your response first</ThemedText>
          <ThemedText>
            Linked practice needs a saved Agree response. Any earlier ratings
            remain saved.
          </ThemedText>
        </Card>
      ) : card ? (
        <>
          <ThemedText type="small" themeColor="textSecondary">
            Question {confirmed.length + 1} of {queue.questions.length}{' '}
            remaining in this pass
          </ThemedText>
          <ReviewQuestion
            key={card.card_id}
            card={card}
            conceptId={card.note_id}
            userId={userId}
            sessionId={passId}
            source={source}
            activity={activity}
            refresh={refresh}
          />
        </>
      ) : (
        <Card>
          <ThemedText type="subtitle" accessibilityRole="header">
            {queue.total && queue.completed + confirmed.length >= queue.total
              ? 'Focused review complete'
              : 'No questions available right now'}
          </ThemedText>
          <ThemedText>
            {queue.completed + confirmed.length} of {queue.total} linked
            questions completed. Each rated question completes this pass once;
            future reviews use your existing schedule.
          </ThemedText>
          {queue.unavailable ? (
            <ThemedText themeColor="textSecondary">
              {queue.unavailable} questions are suspended or unavailable.
            </ThemedText>
          ) : null}
        </Card>
      )}
      {failed ? (
        <InlineError
          message="Couldn’t refresh this practice. Saved ratings remain safe."
          onRetry={refresh}
        />
      ) : null}
      <NativeAction
        label="Load remaining questions"
        secondary
        disabled={refreshing || !!activity.attempt}
        onPress={refresh}
      />
      <ThemedText type="small" themeColor="textSecondary">
        Only Again, Hard, Good, or Easy changes your schedule. Leaving or
        revealing an answer doesn’t record a rating.
      </ThemedText>
    </Screen>
  );
}
