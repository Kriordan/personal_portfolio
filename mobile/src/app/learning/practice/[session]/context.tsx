import { useLocalSearchParams } from 'expo-router';
import { View } from 'react-native';
import {
  LearningAccountState,
  LearningText,
  LearningUnavailable,
} from '@/components/learning-content';
import {
  Card,
  InlineError,
  NavRow,
  PageHeading,
  Screen,
  ScreenState,
  SectionHeading,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { usePracticeDetail } from '@/hooks/use-practice';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { validSessionId } from '@/lib/practice-model';

export default function PracticeContext() {
  const { user } = useAuth();
  const { session } = useLocalSearchParams<{ session: string }>();
  if (!validSessionId(session))
    return <LearningUnavailable title="Conversation unavailable" />;
  return user ? (
    <Context key={user.id + session} userId={user.id} id={session} />
  ) : (
    <LearningAccountState />
  );
}
function Context({ userId, id }: { userId: number; id: string }) {
  const query = usePracticeDetail(userId, id);
  if (
    query.error instanceof ApiError &&
    [403, 404].includes(query.error.status)
  )
    return <LearningUnavailable title="Conversation unavailable" />;
  if (!query.data)
    return (
      <ScreenState
        title="Loading scenario and work"
        loading={query.isPending && !query.isPaused}
        onRetry={() => void query.refetch()}
      />
    );
  const detail = query.data;
  const budget = detail.ai_budget?.total ?? detail.ai_budget;
  return (
    <Screen>
      <PageHeading
        title={detail.session.exercise_title}
        subtitle={`Saved session · ${id.slice(-8)} · Exercise v${detail.session.exercise_version}`}
      />
      {query.isError || query.isPaused ? (
        <InlineError
          message="Couldn’t refresh. Showing the last loaded work."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      <SectionHeading>Scenario</SectionHeading>
      <LearningText text={detail.brief.scenario} />
      {(
        [
          ['Learning objectives', detail.brief.learning_objectives],
          ['Functional requirements', detail.brief.functional_requirements],
          [
            'Nonfunctional requirements',
            detail.brief.nonfunctional_requirements,
          ],
        ] as const
      ).map(([title, items]) => (
        <View key={title} style={{ gap: 10 }}>
          <SectionHeading>{title}</SectionHeading>
          {items.map((item) => (
            <LearningText key={item} text={`• ${item}`} />
          ))}
        </View>
      ))}
      <SectionHeading>Clarified requirements</SectionHeading>
      {detail.revealed_requirements.length ? (
        detail.revealed_requirements.map((item) => (
          <Card key={item.id}>
            <LearningText text={item.fact} />
            <ThemedText type="small" themeColor="textSecondary">
              Revealed in message {item.sequence}
            </ThemedText>
          </Card>
        ))
      ) : (
        <ThemedText themeColor="textSecondary">
          Ask the interviewer to clarify the requirements as you work.
        </ThemedText>
      )}
      <SectionHeading>Your assumptions and decisions</SectionHeading>
      <ThemedText type="small" themeColor="textSecondary">
        Learner notes · Saved brief v{detail.session_brief.revision}. These are
        distinct from the exercise’s requirements.
      </ThemedText>
      {detail.session_brief.entries.length ? (
        detail.session_brief.entries.map((entry) => (
          <Card key={entry.id}>
            <ThemedText type="smallBold">
              {entry.type}
              {entry.pinned ? ' · Pinned' : ''}
            </ThemedText>
            <LearningText text={entry.text} />
          </Card>
        ))
      ) : (
        <ThemedText themeColor="textSecondary">
          No saved notes yet. You can edit this brief in the web workspace.
        </ThemedText>
      )}
      <SectionHeading>Saved artifacts</SectionHeading>
      <ThemedText type="small" themeColor="textSecondary">
        Read your work here. Editing remains available in the web workspace.
      </ThemedText>
      {detail.artifacts.map((artifact) => (
        <NavRow
          key={artifact.artifact_id}
          title={artifact.title}
          subtitle={
            artifact.revision
              ? `Saved revision ${artifact.revision} · ${artifact.language}`
              : 'No saved work yet'
          }
          href={{
            pathname: '/learning/practice/[session]/artifact',
            params: {
              session: id,
              artifact: artifact.artifact_id,
              revision: String(artifact.revision),
            },
          }}
        />
      ))}
      <SectionHeading>Conversation continuity</SectionHeading>
      <ThemedText>
        {detail.context_choices.length
          ? `The interviewer reads from message ${detail.context_choices.at(-1)!.from_sequence}, together with the saved work and brief. The full transcript is preserved.`
          : 'The interviewer reads this conversation together with the work and brief cited by your message.'}
      </ThemedText>
      {budget ? (
        <ThemedText type="small" themeColor="textSecondary">
          {detail.ai_budget?.total
            ? 'Shared lifetime allowance'
            : 'Monthly allowance'}
          : ${(budget.spent_microusd / 1e6).toFixed(3)} of $
          {(budget.cap_microusd / 1e6).toFixed(2)} committed. Existing per-call
          and monthly limits also apply.
        </ThemedText>
      ) : null}
    </Screen>
  );
}
