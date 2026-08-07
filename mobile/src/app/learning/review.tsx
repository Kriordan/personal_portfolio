import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as Crypto from 'expo-crypto';
import { Redirect, useRouter } from 'expo-router';
import { useState } from 'react';
import { ActivityIndicator, Pressable, ScrollView, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import { RATINGS, learningApi, learningKeys, type ReviewCard } from '@/lib/learning-api';

const RATING_COLORS: Record<number, string> = {
  0: '#d64545',
  3: '#b58a2e',
  4: '#3c87f7',
  5: '#2e9e5b',
};

function newSessionId(): string {
  return `mobile-${Date.now().toString(36)}-${Crypto.randomUUID()}`;
}

function ReviewSession({
  cards,
  onReviewMore,
  onExit,
}: {
  cards: ReviewCard[];
  onReviewMore: () => void;
  onExit: () => void;
}) {
  const theme = useTheme();
  const queryClient = useQueryClient();

  const [sessionId] = useState(newSessionId);
  const [index, setIndex] = useState(0);
  const [revealed, setRevealed] = useState(false);
  const [shownAt, setShownAt] = useState(() => Date.now());
  const [lastFeedback, setLastFeedback] = useState<string | null>(null);

  const currentCard = index < cards.length ? cards[index] : null;

  const rateMutation = useMutation({
    mutationFn: (rating: number) => {
      if (!currentCard) throw new Error('No card to rate.');
      return learningApi.rateCard({
        card_id: currentCard.card_id,
        rating,
        response_ms: Date.now() - shownAt,
        session_id: sessionId,
      });
    },
    onSuccess: (result) => {
      setLastFeedback(result.next_review_display);
      setRevealed(false);
      setShownAt(Date.now());
      setIndex((current) => current + 1);
      if (index + 1 >= cards.length) {
        // Session finished; refresh due counts on the notes overview.
        queryClient.invalidateQueries({ queryKey: learningKeys.notes() });
      }
    },
  });

  if (!currentCard) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText type="subtitle">Session complete</ThemedText>
        <ThemedText themeColor="textSecondary">
          You reviewed {cards.length} card{cards.length === 1 ? '' : 's'}.
        </ThemedText>
        {lastFeedback && (
          <ThemedText type="small" themeColor="textSecondary">
            {lastFeedback}
          </ThemedText>
        )}
        <Pressable style={styles.button} onPress={onReviewMore}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Review more
          </ThemedText>
        </Pressable>
        <Pressable style={styles.buttonSecondary} onPress={onExit}>
          <ThemedText type="smallBold">Back to Learning</ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  return (
    <ThemedView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.progressRow}>
          <ThemedText type="small" themeColor="textSecondary">
            Card {index + 1} of {cards.length}
          </ThemedText>
          {lastFeedback && (
            <ThemedText type="small" themeColor="textSecondary">
              {lastFeedback}
            </ThemedText>
          )}
        </View>

        <View style={[styles.card, { backgroundColor: theme.backgroundElement }]}>
          <View style={styles.cardHeader}>
            <ThemedText type="smallBold" themeColor="textSecondary">
              {currentCard.note_title.toUpperCase()}
            </ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {currentCard.type}
            </ThemedText>
          </View>
          <ThemedText>{currentCard.prompt}</ThemedText>
          {revealed && (
            <>
              <View style={[styles.divider, { backgroundColor: theme.backgroundSelected }]} />
              <ThemedText>{currentCard.response}</ThemedText>
            </>
          )}
        </View>

        {!revealed ? (
          <Pressable style={styles.button} onPress={() => setRevealed(true)}>
            <ThemedText type="smallBold" style={styles.buttonText}>
              Show Answer
            </ThemedText>
          </Pressable>
        ) : (
          <View style={styles.ratingRow}>
            {RATINGS.map((rating) => (
              <Pressable
                key={rating.value}
                style={[
                  styles.ratingButton,
                  { backgroundColor: RATING_COLORS[rating.value] },
                  rateMutation.isPending && styles.buttonDisabled,
                ]}
                disabled={rateMutation.isPending}
                onPress={() => rateMutation.mutate(rating.value)}
              >
                <ThemedText type="smallBold" style={styles.buttonText}>
                  {rating.label}
                </ThemedText>
              </Pressable>
            ))}
          </View>
        )}

        {rateMutation.isError && (
          <ThemedText type="small" style={styles.error}>
            {rateMutation.error instanceof Error
              ? rateMutation.error.message
              : 'Failed to save rating.'}
          </ThemedText>
        )}
      </ScrollView>
    </ThemedView>
  );
}

export default function ReviewScreen() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();

  const queueQuery = useQuery({
    queryKey: learningKeys.review(),
    queryFn: learningApi.getReviewQueue,
    enabled: isAuthenticated === true,
    // The queue is a per-session snapshot: it only changes on explicit refetch
    // (retry / "Review more") or when the screen mounts, never in the background,
    // so ratings can't reorder cards mid-session.
    staleTime: Infinity,
    refetchOnMount: 'always',
  });

  if (isAuthenticated === false) {
    return <Redirect href="/login" />;
  }

  if (queueQuery.isPending) {
    return (
      <ThemedView style={styles.centered}>
        <ActivityIndicator />
      </ThemedView>
    );
  }

  if (queueQuery.isError) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText themeColor="textSecondary">Couldn’t load the review queue.</ThemedText>
        <Pressable style={styles.button} onPress={() => queueQuery.refetch()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Retry
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  if (queueQuery.data.cards.length === 0) {
    return (
      <ThemedView style={styles.centered}>
        <ThemedText type="subtitle">All caught up</ThemedText>
        <ThemedText themeColor="textSecondary">No cards are due for review.</ThemedText>
        <Pressable style={styles.button} onPress={() => router.back()}>
          <ThemedText type="smallBold" style={styles.buttonText}>
            Back to Learning
          </ThemedText>
        </Pressable>
      </ThemedView>
    );
  }

  return (
    <ReviewSession
      // Remount to reset session state whenever a fresh queue arrives.
      key={queueQuery.dataUpdatedAt}
      cards={queueQuery.data.cards}
      onReviewMore={() => queueQuery.refetch()}
      onExit={() => router.back()}
    />
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
    paddingHorizontal: Spacing.four,
  },
  scrollContent: {
    padding: Spacing.three,
    gap: Spacing.three,
    maxWidth: MaxContentWidth,
    width: '100%',
    alignSelf: 'center',
  },
  progressRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  card: {
    borderRadius: Spacing.two,
    paddingHorizontal: Spacing.three,
    paddingVertical: Spacing.three,
    gap: Spacing.two,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.two,
  },
  divider: {
    height: 1,
    alignSelf: 'stretch',
  },
  ratingRow: {
    flexDirection: 'row',
    gap: Spacing.two,
  },
  ratingButton: {
    flex: 1,
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  button: {
    backgroundColor: '#3c87f7',
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonSecondary: {
    borderRadius: Spacing.two,
    paddingVertical: Spacing.three,
    paddingHorizontal: Spacing.three,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  buttonText: {
    color: '#ffffff',
  },
  error: {
    color: '#d64545',
  },
});
