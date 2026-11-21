import { useLocalSearchParams } from 'expo-router';
import {
  LearningAccountState,
  LearningUnavailable,
} from '@/components/learning-content';
import { FeedbackResponse } from '@/components/feedback-response';
import { useAuth } from '@/lib/auth-context';
import { validFeedbackSource } from '@/lib/feedback-response-model';

export default function FeedbackResponseScreen() {
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
        title="Feedback unavailable"
        message="Open a saved finding from Build."
      />
    );
  return user ? (
    <FeedbackResponse
      key={`${user.id}:${session}:${snapshot}:${finding}`}
      userId={user.id}
      source={source}
    />
  ) : (
    <LearningAccountState />
  );
}
