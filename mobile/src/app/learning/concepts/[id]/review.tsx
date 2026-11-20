import { ReviewQuestion } from '@/components/review-question';
import { useQuery } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { ConceptHeader, StudyStatus } from '@/components/concept-workspace';
import {
  LearningAccountState,
  LearningUnavailable,
} from '@/components/learning-content';
import { LearningStatus } from '@/components/learning-status';
import {
  Card,
  InlineError,
  NativeAction,
  Screen,
  ScreenState,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useConcept, useConceptStudy } from '@/hooks/use-concepts';
import { useLearningActivity } from '@/hooks/use-learning';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { conceptApi } from '@/lib/concept-api';
import {
  conceptKeys,
  type Concept,
  type ConceptQueue,
} from '@/lib/concept-model';
import { learningQueueOptions } from '@/lib/learning-cache';
import { validNoteId } from '@/lib/learning-model';

type Activity = ReturnType<typeof useLearningActivity>;
export default function ConceptReviewScreen() {
  const { user } = useAuth();
  const { id } = useLocalSearchParams<{ id: string }>();
  if (!validNoteId(id))
    return (
      <LearningUnavailable
        title="Concept unavailable"
        message="Choose a concept from Learning."
      />
    );
  return user ? (
    <ReviewContent key={user.id + ':' + id} userId={user.id} id={id} />
  ) : (
    <LearningAccountState />
  );
}
function ReviewContent({ userId, id }: { userId: number; id: string }) {
  const detail = useConcept(userId, id);
  const activity = useLearningActivity(userId);
  const study = useConceptStudy(userId);
  const query = useQuery({
    ...learningQueueOptions,
    queryKey: conceptKeys.review(userId, id),
    queryFn: () => conceptApi.queue(id),
    enabled: !!detail.data && activity.ready && !activity.attempt,
  });
  const refresh = () => {
    void query.refetch();
    void detail.refetch();
  };
  if (
    [query.error, detail.error].some(
      (error) => error instanceof ApiError && error.status === 404,
    )
  )
    return (
      <LearningUnavailable
        title="Review unavailable"
        message="This concept isn’t available to this account."
      />
    );
  if (!detail.data)
    return (
      <ScreenState
        loading={detail.isPending && !detail.isPaused}
        title={detail.isPending ? 'Loading review' : 'Couldn’t load review'}
        message="Connect to load the current questions."
        onRetry={detail.isError ? refresh : undefined}
      />
    );
  const concept = detail.data.concept;
  if (!activity.ready || (!query.data && activity.attempt))
    return (
      <Screen>
        <ConceptHeader concept={concept} mode="review" />
        <LearningStatus activity={activity} onFreshQueue={refresh} />
      </Screen>
    );
  if (!query.data)
    return (
      <ScreenState
        loading={query.isPending && !query.isPaused}
        title={
          query.isPaused
            ? 'You’re offline'
            : query.isPending
              ? 'Preparing your review'
              : 'Couldn’t load the questions'
        }
        message="Your saved progress is unchanged."
        onRetry={query.isError ? refresh : undefined}
      />
    );
  if (!query.data.cards.length)
    return (
      <Screen>
        <ConceptHeader concept={concept} mode="review" />
        <StudyStatus activity={study} onReload={refresh} />
        <Card>
          <ThemedText type="subtitle" accessibilityRole="header">
            {query.data.progress
              ? 'Nothing due right now'
              : 'Choose when to begin'}
          </ThemedText>
          <ThemedText themeColor="textSecondary">
            {query.data.progress
              ? 'Your saved ratings determine when these questions return. You can continue reading in Learn.'
              : 'Start learning to add this concept’s questions to your review schedule.'}
          </ThemedText>
          {!query.data.progress ? (
            <NativeAction
              label="Start learning"
              disabled={!study.ready || !!study.pending}
              onPress={() =>
                void study.study.begin({ kind: 'enroll', conceptId: id })
              }
            />
          ) : (
            <NativeAction
              label="Check due questions"
              disabled={query.isFetching}
              onPress={refresh}
              secondary
            />
          )}
        </Card>
        {query.isError ? (
          <InlineError
            message="Couldn’t refresh the due questions."
            onRetry={refresh}
          />
        ) : null}
      </Screen>
    );
  return (
    <ReviewAttempt
      key={query.dataUpdatedAt}
      concept={concept}
      queue={query.data}
      activity={activity}
      userId={userId}
      refresh={refresh}
      refreshing={query.isFetching}
      refreshFailed={query.isError}
    />
  );
}
function ReviewAttempt({
  concept,
  queue,
  activity,
  userId,
  refresh,
  refreshing,
  refreshFailed,
}: {
  concept: Concept;
  queue: ConceptQueue;
  activity: Activity;
  userId: number;
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
  return (
    <Screen key={card?.card_id ?? 'done'}>
      <ConceptHeader concept={concept} mode="review" />
      {previous ? (
        <ThemedText
          type="small"
          themeColor="textSecondary"
          accessibilityLiveRegion="polite"
        >
          Rating saved · {previous.next_review_display}
        </ThemedText>
      ) : null}
      {card ? (
        <>
          <ThemedText type="small" themeColor="textSecondary">
            Question {results.length + 1} of {queue.cards.length}
          </ThemedText>
          <ReviewQuestion
            key={card.card_id}
            card={card}
            conceptId={concept.id}
            userId={userId}
            sessionId={sessionId}
            activity={activity}
            refresh={refresh}
          />
          <LearningStatus activity={activity} onFreshQueue={refresh} />
        </>
      ) : (
        <Card>
          <ThemedText type="subtitle" accessibilityRole="header">
            Review complete for now
          </ThemedText>
          <ThemedText>
            {results.length} ratings saved. The next review uses your existing
            schedule.
          </ThemedText>
          <NativeAction
            label="Check due questions"
            disabled={refreshing}
            onPress={refresh}
          />
          <NativeAction
            label="Return to Learn"
            secondary
            onPress={() =>
              router.replace({
                pathname: '/learning/concepts/[id]',
                params: { id: concept.id },
              })
            }
          />
        </Card>
      )}
      {refreshFailed ? (
        <InlineError
          message="Couldn’t load a fresh queue. Your confirmed ratings remain saved."
          onRetry={refresh}
        />
      ) : null}
      <ThemedText type="small" themeColor="textSecondary">
        Each confirmed rating is saved. You can leave and continue later.
      </ThemedText>
    </Screen>
  );
}
