import { useQuery } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View, useWindowDimensions } from 'react-native';
import { LearningText } from './learning-content';
import { Card, InlineError, NativeAction } from './screen';
import { ThemedText } from './themed-text';
import type { useLearningActivity } from '@/hooks/use-learning';
import { useTheme } from '@/hooks/use-theme';
import { ApiError } from '@/lib/api-client';
import { conceptApi } from '@/lib/concept-api';
import { conceptKeys, type ConceptQuestion } from '@/lib/concept-model';
import { learningQueueOptions } from '@/lib/learning-cache';
import { RATINGS } from '@/lib/learning-model';
import { practiceApi } from '@/lib/practice-runtime';
import {
  responseRoute,
  type FeedbackSource,
} from '@/lib/feedback-response-model';
type Activity = ReturnType<typeof useLearningActivity>;

export function ReviewQuestion({
  card,
  conceptId,
  userId,
  sessionId,
  activity,
  refresh,
  source,
}: {
  card: ConceptQuestion;
  conceptId: string;
  userId: number;
  sessionId: string;
  activity: Activity;
  refresh: () => void;
  source?: FeedbackSource;
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
      source?.sessionId,
      source?.submission_sequence,
      source?.findingId,
      card.card_id,
      card.content_version,
      card.progress_revision,
    ],
    queryFn: async () =>
      source
        ? { card: await practiceApi.revealFocused(source, card, sessionId) }
        : conceptApi.reveal(conceptId, card),
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
                    source,
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
            label={
              source ? 'Return to your response' : 'Revisit the explanation'
            }
            secondary
            onPress={() =>
              router.push(
                source
                  ? responseRoute(source)
                  : {
                      pathname: '/learning/concepts/[id]',
                      params: {
                        id: conceptId,
                        section: card.remediation_section_id,
                      },
                    },
              )
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
