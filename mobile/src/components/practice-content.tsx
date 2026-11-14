import { memo } from 'react';
import { useRouter } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';
import { LearningText } from './learning-content';
import { Card, InlineError, NativeAction } from './screen';
import { ThemedText } from './themed-text';
import { useTheme } from '@/hooks/use-theme';
import type { usePracticeOperation } from '@/hooks/use-practice';
import type { PracticeMessage } from '@/lib/practice-model';

export function PracticeRecovery({
  activity,
  reload,
}: {
  activity: ReturnType<typeof usePracticeOperation>;
  reload: () => void;
}) {
  const router = useRouter();
  if (!activity.ready)
    return (
      <InlineError
        message={activity.error ?? 'Checking for interrupted changes…'}
        onRetry={
          activity.error ? () => void activity.operation.restore() : undefined
        }
      />
    );
  if (!activity.pending)
    return activity.error ? <InlineError message={activity.error} /> : null;
  const busy = activity.phase === 'saving' || activity.phase === 'checking';
  const change = activity.pending;
  return (
    <Card>
      <ThemedText type="smallBold" accessibilityLiveRegion="polite">
        {busy ? 'Confirming your change…' : 'A practice change needs attention'}
      </ThemedText>
      {activity.error ? <ThemedText>{activity.error}</ThemedText> : null}
      {'sessionId' in change ? (
        <NativeAction
          secondary
          label="Open the affected conversation"
          onPress={() =>
            router.replace({
              pathname: '/learning/concepts/[id]/discuss',
              params: {
                id: change.conceptId,
                practice_session: change.sessionId,
              },
            })
          }
        />
      ) : null}
      {activity.phase === 'rejected' ? (
        <NativeAction
          secondary
          label="Keep draft and refresh"
          onPress={() => {
            void activity.operation.dismissRejected().then((ok) => {
              if (ok) reload();
            });
          }}
        />
      ) : (
        <>
          <NativeAction
            secondary
            disabled={busy}
            label="Check saved result"
            onPress={() => void activity.operation.check()}
          />
          <NativeAction
            secondary
            disabled={busy}
            label="Retry the same request"
            onPress={() => void activity.operation.retry()}
          />
        </>
      )}
    </Card>
  );
}
export const ConversationMessage = memo(function ConversationMessage({
  message,
  sessionId,
}: {
  message: PracticeMessage;
  sessionId: string;
}) {
  const theme = useTheme();
  const router = useRouter();
  return (
    <View
      style={[
        styles.message,
        {
          backgroundColor:
            message.role === 'learner'
              ? theme.accentSoft
              : theme.backgroundElement,
        },
      ]}
    >
      <ThemedText type="smallBold" themeColor="textSecondary">
        {message.role === 'learner' ? 'You' : 'Interviewer'} · Message{' '}
        {message.sequence}
        {message.hint ? ' · Hint' : ''}
      </ThemedText>
      <LearningText text={message.body} />
      {message.artifact_revisions.length ? (
        <View style={styles.citations}>
          {message.artifact_revisions.map((cite) => (
            <Pressable
              key={cite.artifact_id}
              accessibilityRole="link"
              accessibilityLabel={`Read ${cite.artifact_id}, saved revision ${cite.revision}, cited by message ${message.sequence}`}
              style={styles.citation}
              onPress={() =>
                router.push({
                  pathname: '/learning/practice/[session]/artifact',
                  params: {
                    session: sessionId,
                    artifact: cite.artifact_id,
                    revision: cite.revision.toString(),
                  },
                })
              }
            >
              <ThemedText type="small" themeColor="accent">
                {cite.artifact_id} · v{cite.revision}
              </ThemedText>
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
});
const styles = StyleSheet.create({
  message: { padding: 16, borderRadius: 16, gap: 10, marginBottom: 12 },
  citations: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  citation: { minHeight: 44, paddingHorizontal: 8, justifyContent: 'center' },
});
