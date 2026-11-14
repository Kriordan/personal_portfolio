import * as Crypto from 'expo-crypto';
import { useRouter } from 'expo-router';
import { useEffect } from 'react';
import { ConceptHeader } from './concept-workspace';
import { PracticeRecovery } from './practice-content';
import { InlineError, NativeAction, NavRow, Screen } from './screen';
import { ThemedText } from './themed-text';
import { usePracticeList, usePracticeOperation } from '@/hooks/use-practice';
import type { Concept } from '@/lib/concept-model';

export function PracticeSessionPicker({
  userId,
  concept,
  mode = 'discuss',
}: {
  userId: number;
  concept: Concept;
  mode?: 'discuss' | 'build';
}) {
  const router = useRouter();
  const path =
    mode === 'build'
      ? '/learning/concepts/[id]/build'
      : '/learning/concepts/[id]/discuss';
  const query = usePracticeList(userId);
  const activity = usePracticeOperation(userId);
  const { saved, operation } = activity;
  useEffect(() => {
    if (saved?.change.kind !== 'start' || saved.change.conceptId !== concept.id)
      return;
    router.replace({
      pathname: path,
      params: { id: concept.id, practice_session: saved.result.session_id },
    });
    operation.consumeSaved();
  }, [saved, operation, router, concept.id, path]);
  const sessions =
    query.data?.sessions.filter((s) => s.concept_id === concept.id) ?? [];
  return (
    <Screen>
      <ConceptHeader concept={concept} mode={mode} />
      <ThemedText>
        {mode === 'build'
          ? 'Write your proposal in the same session as your interviewer conversation.'
          : 'Clarify the problem, propose a design, and defend your decisions with an AI interviewer.'}
      </ThemedText>
      <PracticeRecovery
        activity={activity}
        reload={() => void query.refetch()}
      />
      {query.isError || query.isPaused ? (
        <InlineError
          message="Connect to refresh your saved conversations."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {sessions.length ? (
        <ThemedText type="subtitle">Pick up where you left off</ThemedText>
      ) : null}
      {sessions.map((s, i) => (
        <NavRow
          key={s.id}
          title={
            i === 0 ? 'Continue latest conversation' : 'Open saved conversation'
          }
          subtitle={`${s.status === 'paused' ? 'Paused' : 'Active'} · ${new Date(s.updated_at).toLocaleString()} · ${s.id.slice(-8)}`}
          href={{
            pathname: path,
            params: { id: concept.id, practice_session: s.id },
          }}
        />
      ))}
      {query.isPending ? (
        <ThemedText>Loading saved conversations…</ThemedText>
      ) : !sessions.length && !query.isError ? (
        <ThemedText themeColor="textSecondary">
          Your web and phone share the same saved conversations.
        </ThemedText>
      ) : null}
      <NativeAction
        secondary={sessions.length > 0}
        label="Start a new conversation"
        disabled={
          !activity.ready ||
          !!activity.pending ||
          !query.isSuccess ||
          !concept.content.exercise_ids?.length
        }
        onPress={() =>
          void operation.begin({
            kind: 'start',
            conceptId: concept.id,
            exerciseId: concept.content.exercise_ids[0],
            request_id: Crypto.randomUUID(),
          })
        }
      />
      <ThemedText type="small" themeColor="textSecondary">
        Up to 20 recent open conversations. Saved work and spending limits are
        shared with the web.
      </ThemedText>
    </Screen>
  );
}
