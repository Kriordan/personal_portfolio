import * as Crypto from 'expo-crypto';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert, Keyboard, Pressable, View } from 'react-native';
import { ConceptHeader } from '@/components/concept-workspace';
import {
  LearningAccountState,
  LearningUnavailable,
} from '@/components/learning-content';
import { PracticeRecovery } from '@/components/practice-content';
import { PracticeFeedback } from '@/components/practice-feedback';
import { PracticeSessionPicker } from '@/components/practice-session-picker';
import {
  ArtifactEditor,
  BriefEditor,
  SavedWorkComparison,
} from '@/components/practice-work-editor';
import {
  InlineError,
  NativeAction,
  NavRow,
  Screen,
  ScreenState,
  SectionHeading,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useConcept } from '@/hooks/use-concepts';
import { useTheme } from '@/hooks/use-theme';
import {
  usePracticeDetail,
  usePracticeOperation,
  usePracticeWork,
} from '@/hooks/use-practice';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import type { Concept } from '@/lib/concept-model';
import { validNoteId } from '@/lib/learning-model';
import { validSessionId, type PracticeDetail } from '@/lib/practice-model';
import { savedWork } from '@/lib/practice-work-drafts';
import {
  copyWork,
  workKey,
  workProblem,
  type WorkEdit,
} from '@/lib/practice-work-model';

export default function BuildScreen() {
  const { user } = useAuth();
  const { id, practice_session, work, snapshot } = useLocalSearchParams<{
    id: string;
    practice_session?: string;
    work?: string;
    snapshot?: string;
  }>();
  if (
    !validNoteId(id) ||
    (practice_session !== undefined && !validSessionId(practice_session))
  )
    return <LearningUnavailable title="Work unavailable" />;
  return user ? (
    <Build
      key={user.id + id}
      userId={user.id}
      id={id}
      sessionId={practice_session}
      part={work}
      selectedSnapshot={snapshot}
    />
  ) : (
    <LearningAccountState />
  );
}
function Build({
  userId,
  id,
  sessionId,
  part,
  selectedSnapshot,
}: {
  userId: number;
  id: string;
  sessionId?: string;
  part?: string;
  selectedSnapshot?: string;
}) {
  const query = useConcept(userId, id);
  if (
    query.error instanceof ApiError &&
    [403, 404].includes(query.error.status)
  )
    return <LearningUnavailable title="Concept unavailable" />;
  if (!query.data)
    return (
      <ScreenState
        title="Loading Build"
        loading={query.isPending && !query.isPaused}
        onRetry={() => void query.refetch()}
      />
    );
  return sessionId ? (
    <Workspace
      key={userId + sessionId}
      userId={userId}
      id={sessionId}
      concept={query.data.concept}
      part={part}
      selectedSnapshot={selectedSnapshot}
    />
  ) : (
    <PracticeSessionPicker
      userId={userId}
      concept={query.data.concept}
      mode="build"
    />
  );
}
function Workspace({
  userId,
  id,
  concept,
  part,
  selectedSnapshot,
}: {
  userId: number;
  id: string;
  concept: Concept;
  part?: string;
  selectedSnapshot?: string;
}) {
  const query = usePracticeDetail(userId, id);
  const activity = usePracticeOperation(userId);
  const work = usePracticeWork(userId, id);
  const router = useRouter();
  if (
    query.error instanceof ApiError &&
    [403, 404].includes(query.error.status)
  )
    return <LearningUnavailable title="Work unavailable" />;
  if (!query.data)
    return (
      <ScreenState
        title="Loading your work"
        loading={query.isPending && !query.isPaused}
        onRetry={() => void query.refetch()}
      />
    );
  const detail = query.data;
  if (detail.session.concept_id !== concept.id)
    return <LearningUnavailable title="Choose this work from its concept" />;
  const current = part ? savedWork(detail, part) : null;
  return (
    <Screen key={part || 'proposal'} keyboardDismissMode="interactive">
      <ConceptHeader concept={concept} mode="build" compact />
      <ThemedText type="small" themeColor="textSecondary">
        Shared session · {id.slice(-8)} ·{' '}
        {detail.session.status === 'paused' ? 'Paused' : 'Active'}
      </ThemedText>
      {!current && part !== 'feedback' ? (
        <NavRow
          title="Scenario & work"
          subtitle="Requirements, saved decisions, and spending status"
          href={{
            pathname: '/learning/practice/[session]/context',
            params: { session: id },
          }}
        />
      ) : null}
      {query.isError || query.isPaused ? (
        <InlineError
          message="Connect to refresh the saved work. Your local edits are kept."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {!work.ready || work.error ? (
        <InlineError
          message={work.error ?? 'Loading this device’s Build drafts…'}
          onRetry={
            work.error
              ? () =>
                  work.ready
                    ? work.drafts.retrySave(id)
                    : void work.drafts.load(id)
              : undefined
          }
        />
      ) : null}
      {part === 'feedback' ? (
        <PracticeFeedback
          userId={userId}
          detail={detail}
          work={work}
          activity={activity}
          selected={selectedSnapshot}
          blocked={
            query.isError || query.isPaused || !query.isFetchedAfterMount
          }
          reload={() => void query.refetch()}
        />
      ) : current ? (
        <WorkPanel
          key={part}
          detail={detail}
          current={current}
          work={work}
          activity={activity}
          blocked={
            query.isError || query.isPaused || !query.isFetchedAfterMount
          }
          reload={() => void query.refetch()}
          close={() => {
            Keyboard.dismiss();
            router.setParams({ work: '' });
          }}
        />
      ) : (
        <>
          {part ? (
            <InlineError message="That work item is unavailable. Choose one below." />
          ) : null}
          <PracticeRecovery
            activity={activity}
            reload={() => void query.refetch()}
          />
          <SectionHeading>Your proposal</SectionHeading>
          <ThemedText>
            Work on one part at a time. Explicit saves share your changes with
            the web and interviewer.
          </ThemedText>
          {detail.artifacts.map((artifact) => {
            const draft = work.edits.some(
              (e) =>
                e.kind === 'artifact' &&
                e.artifactId === artifact.artifact_id,
            );
            return (
              <WorkChoice
                key={artifact.artifact_id}
                title={artifact.title}
                status={
                  draft
                    ? 'Unsaved edits on this device'
                    : `Saved revision ${artifact.revision}`
                }
                onPress={() =>
                  router.setParams({
                    work: `artifact:${artifact.artifact_id}`,
                  })
                }
              />
            );
          })}
          <WorkChoice
            title="Assumptions & decisions"
            status={
              work.edits.some((e) => e.kind === 'brief')
                ? 'Unsaved edits on this device'
                : `${detail.session_brief.entries.length} saved notes`
            }
            onPress={() => router.setParams({ work: 'brief' })}
          />
          <ThemedText type="small" themeColor="textSecondary">
            Build drafts stay on this device until saved or discarded and are
            cleared on sign-out. Saving work does not request AI feedback.
          </ThemedText>
          <WorkChoice
            title="Feedback & snapshots"
            status={
              detail.feedback_pending
                ? 'Feedback is being prepared'
                : detail.submissions?.length
                  ? `${detail.submissions.length} saved ${detail.submissions.length === 1 ? 'snapshot' : 'snapshots'}`
                  : 'Save a snapshot, then request design feedback'
            }
            onPress={() =>
              router.setParams({
                work: 'feedback',
                snapshot: detail.feedback_pending
                  ? String(detail.feedback_pending.sequence)
                  : '',
              })
            }
          />
        </>
      )}
      {current ? (
        <NavRow
          title="Scenario & work"
          subtitle="Requirements, saved decisions, and spending status"
          href={{
            pathname: '/learning/practice/[session]/context',
            params: { session: id },
          }}
        />
      ) : null}
    </Screen>
  );
}
function WorkChoice({
  title,
  status,
  onPress,
}: {
  title: string;
  status: string;
  onPress: () => void;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${title}. ${status}`}
      onPress={onPress}
      style={({ pressed }) => ({
        padding: 16,
        borderRadius: 16,
        minHeight: 64,
        gap: 4,
        backgroundColor: pressed
          ? theme.backgroundSelected
          : theme.backgroundElement,
      })}
    >
      <ThemedText style={{ fontWeight: '600' }}>{title}</ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        {status}
      </ThemedText>
    </Pressable>
  );
}
function WorkPanel({
  detail,
  current,
  work,
  activity,
  blocked,
  reload,
  close,
}: {
  detail: PracticeDetail;
  current: WorkEdit;
  work: ReturnType<typeof usePracticeWork>;
  activity: ReturnType<typeof usePracticeOperation>;
  blocked: boolean;
  reload: () => void;
  close: () => void;
}) {
  const id = detail.session.id;
  const [comparedRevision, setComparedRevision] = useState<number | null>(
    null,
  );
  const [discardError, setDiscardError] = useState(false);
  const local = work.edits.find((e) => workKey(e) === workKey(current));
  const pending = activity.pending;
  const pendingEdit =
    pending &&
    (pending.kind === 'artifact' || pending.kind === 'brief') &&
    pending.sessionId === id &&
    workKey(pending) === workKey(current)
      ? pending
      : null;
  const edit = pendingEdit ?? local ?? current;
  const artifact =
    current.kind === 'artifact'
      ? detail.artifacts.find((a) => a.artifact_id === current.artifactId)!
      : null;
  const conflict = !!local && local.base_revision !== current.base_revision;
  const disabled = !work.ready || !!pending;
  const cannotSave =
    disabled ||
    blocked ||
    !activity.ready ||
    work.saving ||
    !!work.error ||
    !local ||
    conflict ||
    !!workProblem(edit);
  const discard = () => {
    if (!local) return;
    Alert.alert(
      'Discard this device’s unsaved edits?',
      'The saved work on the web stays unchanged.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Use saved version',
          style: 'destructive',
          onPress: () => {
            void work.drafts.clearIfMatches(id, local).then(
              () => setDiscardError(false),
              () => setDiscardError(true),
            );
          },
        },
      ],
    );
  };
  return (
    <View style={{ gap: 14 }}>
      <NativeAction secondary label="All work" onPress={close} />
      <SectionHeading>
        {artifact?.title ?? 'Assumptions & decisions'}
      </SectionHeading>
      {artifact ? (
        <ThemedText themeColor="textSecondary">
          {artifact.instructions}
        </ThemedText>
      ) : null}
      <ThemedText type="small" themeColor="textSecondary">
        Saved revision {current.base_revision}
        {local
          ? ` · Your draft began at revision ${local.base_revision}`
          : ''}
      </ThemedText>
      {edit.kind === 'artifact' ? (
        <ArtifactEditor
          edit={edit}
          languages={artifact!.languages}
          disabled={disabled}
          onChange={(value) => work.drafts.edit(id, value)}
        />
      ) : (
        <BriefEditor
          edit={edit}
          disabled={disabled}
          onChange={(value) => work.drafts.edit(id, value)}
        />
      )}
      <ThemedText
        type="small"
        accessibilityLiveRegion="polite"
        themeColor="textSecondary"
      >
        {!work.ready
          ? 'Loading drafts…'
          : work.saving
            ? 'Protecting edits on this device…'
            : work.error
              ? 'Local save needs attention.'
              : local
                ? 'Draft saved on this device · Not yet shared with the interviewer'
                : 'Showing saved work shared with the web and interviewer.'}
      </ThemedText>
      {local && workProblem(local) ? (
        <InlineError message={workProblem(local)!} />
      ) : null}
      {discardError ? (
        <InlineError message="Couldn’t discard the local draft. It is still available; try again." />
      ) : null}
      {conflict ? (
        <View style={{ gap: 12 }}>
          <ThemedText type="smallBold">
            Saved work changed elsewhere
          </ThemedText>
          <ThemedText>
            Your draft is intact. Compare the current saved version before
            deciding what to keep.
          </ThemedText>
          <NativeAction
            secondary
            label="Compare saved version"
            disabled={!!pending || blocked}
            onPress={() => {
              Keyboard.dismiss();
              setComparedRevision(current.base_revision);
            }}
          />
          {comparedRevision === current.base_revision ? (
            <>
              <SavedWorkComparison edit={current} />
              <ThemedText>
                {current.kind === 'brief'
                  ? 'Keeping your draft will replace the whole notes list when you save. Copy any saved notes you want to keep into your draft first.'
                  : 'Keeping your draft will replace this artifact when you save. Copy any saved changes you want to keep into your draft first.'}
              </ThemedText>
              <NativeAction
                secondary
                label="Keep my draft after comparison"
                disabled={disabled || blocked || work.saving || !!work.error}
                onPress={() =>
                  Alert.alert(
                    'Use your draft for the next save?',
                    'This keeps your draft and updates its starting revision. Nothing changes on the server until you tap Save.',
                    [
                      { text: 'Cancel', style: 'cancel' },
                      {
                        text: 'Keep my draft',
                        onPress: () => work.drafts.rebase(id, current),
                      },
                    ],
                  )
                }
              />
            </>
          ) : null}
          <NativeAction
            secondary
            label="Use saved version"
            disabled={disabled || work.saving}
            onPress={discard}
          />
        </View>
      ) : null}
      <PracticeRecovery activity={activity} reload={reload} />
      {detail.session.status === 'paused' ? (
        <ThemedText type="small" themeColor="textSecondary">
          Saving resumes this paused session. It does not start an AI reply.
        </ThemedText>
      ) : null}
      <NativeAction
        label={
          detail.session.status === 'paused'
            ? 'Save and resume session'
            : current.kind === 'brief'
              ? 'Save notes'
              : 'Save artifact'
        }
        disabled={cannotSave}
        onPress={() => {
          if (local) {
            Keyboard.dismiss();
            void activity.operation.begin({
              ...copyWork(local),
              sessionId: id,
              conceptId: detail.session.concept_id,
              request_id: Crypto.randomUUID(),
            });
          }
        }}
      />
      {local && !conflict ? (
        <NativeAction
          secondary
          label="Discard unsaved edits"
          disabled={disabled || work.saving}
          onPress={discard}
        />
      ) : null}
    </View>
  );
}
