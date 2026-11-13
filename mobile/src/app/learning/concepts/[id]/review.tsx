import { useQuery } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View, useWindowDimensions } from 'react-native';
import { ConceptHeader, StudyStatus } from '@/components/concept-workspace';
import {
  LearningAccountState,
  LearningText,
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
import { useTheme } from '@/hooks/use-theme';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { conceptApi } from '@/lib/concept-api';
import {
  conceptKeys,
  type Concept,
  type ConceptQuestion,
  type ConceptQueue,
} from '@/lib/concept-model';
import { learningQueueOptions } from '@/lib/learning-cache';
import { RATINGS, validNoteId } from '@/lib/learning-model';

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
          <Question
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
function Question({
  card,
  conceptId,
  userId,
  sessionId,
  activity,
  refresh,
}: {
  card: ConceptQuestion;
  conceptId: string;
  userId: number;
  sessionId: string;
  activity: Activity;
  refresh: () => void;
}) {
  const theme = useTheme();
  const router = useRouter();
  const { width, fontScale } = useWindowDimensions();
  const [show, setShow] = useState(false);
  const [startedAt] = useState(Date.now);
  const answer = useQuery({
    ...learningQueueOptions,
    queryKey: [
      ...conceptKeys.review(userId, conceptId),
      'answer',
      sessionId,
      card.card_id,
      card.content_version,
      card.progress_revision,
    ],
    queryFn: () => conceptApi.reveal(conceptId, card),
    enabled: show,
  });
  const invalid =
    answer.error instanceof ApiError &&
    [404, 409].includes(answer.error.status);
  const revealed =
    !invalid &&
    !!answer.data &&
    answer.data.card.card_id === card.card_id &&
    answer.data.card.content_version === card.content_version;
  const disabled =
    !revealed ||
    !!activity.attempt ||
    !activity.ready ||
    activity.phase === 'conflict';
  return (
    <>
      <Card>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {card.note_title}
        </ThemedText>
        <LearningText text={card.prompt} />
        {!show ? (
          <ThemedText type="small" themeColor="textSecondary">
            Try explaining your answer before revealing it.
          </ThemedText>
        ) : null}
      </Card>
      {!show ? (
        <NativeAction label="Show answer" onPress={() => setShow(true)} />
      ) : null}
      {show && !revealed && !answer.isError ? (
        <ThemedText accessibilityLiveRegion="polite">
          {answer.isPaused
            ? 'Reconnect to reveal the answer.'
            : 'Loading the answer…'}
        </ThemedText>
      ) : null}
      {answer.isError ? (
        <InlineError
          message={
            invalid
              ? 'This review changed elsewhere. Load the current questions before rating.'
              : 'Couldn’t load the answer. Your progress is unchanged.'
          }
          retryLabel={invalid ? 'Load current questions' : 'Try again'}
          onRetry={invalid ? refresh : () => void answer.refetch()}
        />
      ) : null}
      {revealed ? (
        <>
          <Card>
            <ThemedText type="smallBold" accessibilityRole="header">
              Compare your answer
            </ThemedText>
            <LearningText text={answer.data!.card.answer} />
            <LearningText text={answer.data!.card.explanation} />
          </Card>
          <View style={styles.ratings}>
            {RATINGS.map((rating) => (
              <Pressable
                key={rating.value}
                accessibilityRole="button"
                accessibilityLabel={rating.label + '. ' + rating.description}
                accessibilityState={{
                  disabled,
                  busy: activity.phase === 'saving',
                }}
                disabled={disabled}
                onPress={() =>
                  void activity.session.begin(
                    card,
                    rating.value,
                    Date.now() - startedAt,
                    sessionId,
                  )
                }
                style={({ pressed }) => [
                  styles.rating,
                  {
                    width: fontScale > 1.3 || width < 360 ? '100%' : '48%',
                    backgroundColor: pressed
                      ? theme.backgroundSelected
                      : theme.backgroundElement,
                    opacity: disabled ? 0.6 : 1,
                  },
                ]}
              >
                <ThemedText
                  type="smallBold"
                  themeColor={rating.value === 0 ? 'danger' : 'accent'}
                >
                  {rating.label}
                </ThemedText>
                <ThemedText type="small" themeColor="textSecondary">
                  {rating.description}
                </ThemedText>
              </Pressable>
            ))}
          </View>
          <NativeAction
            label="Revisit the explanation"
            secondary
            onPress={() =>
              router.push({
                pathname: '/learning/concepts/[id]',
                params: { id: conceptId, section: card.remediation_section_id },
              })
            }
          />
        </>
      ) : null}
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
