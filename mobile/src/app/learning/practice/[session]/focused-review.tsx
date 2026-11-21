import { useLocalSearchParams } from 'expo-router';
import { FocusedFeedbackReview } from '@/components/focused-feedback-review';
import {
  LearningAccountState,
  LearningUnavailable,
} from '@/components/learning-content';
import { useAuth } from '@/lib/auth-context';
import { validFeedbackSource } from '@/lib/feedback-response-model';

export default function FocusedReviewScreen() {
  const { user } = useAuth();
  const { session, snapshot, finding } = useLocalSearchParams<{
    session: string;
    snapshot: string;
    finding: string;
  }>();
  const source = {
    sessionId: session,
    submission_sequence: Number(snapshot),
    findingId: finding,
  };
  if (!validFeedbackSource(source))
    return (
      <LearningUnavailable
        title="Review unavailable"
        message="Open a saved finding from Build."
      />
    );
  return user ? (
    <FocusedFeedbackReview
      key={`${user.id}:${session}:${snapshot}:${finding}`}
      userId={user.id}
      source={source}
    />
  ) : (
    <LearningAccountState />
  );
}
