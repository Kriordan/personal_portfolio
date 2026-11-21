import * as Crypto from 'expo-crypto';
import { useFocusEffect, useRouter } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, View } from 'react-native';
import { LearningText } from './learning-content';
import { NativeChoice } from './native-choice';
import { PracticeRecovery } from './practice-content';
import { FeedbackFindingCard } from './practice-feedback-findings';
import {
  Card,
  InlineError,
  NativeAction,
  NavRow,
  SectionHeading,
} from './screen';
import { ThemedText } from './themed-text';
import {
  usePracticeDraft,
  type usePracticeOperation,
  type usePracticeWork,
} from '@/hooks/use-practice';
import { usePracticeFeedback } from '@/hooks/use-practice-feedback';
import { ApiError } from '@/lib/api-client';
import {
  feedbackNotice,
  snapshotBlock,
  snapshotChange,
  snapshotIsOlder,
  wholeRevision,
  type SnapshotDetail,
} from '@/lib/practice-feedback-model';
import type { PracticeDetail } from '@/lib/practice-model';

type Activity = ReturnType<typeof usePracticeOperation>;
export function PracticeFeedback({
  userId,
  detail,
  work,
  activity,
  blocked,
  selected,
  reload,
}: {
  userId: number;
  detail: PracticeDetail;
  work: ReturnType<typeof usePracticeWork>;
  activity: Activity;
  blocked: boolean;
  selected?: string;
  reload: () => void;
}) {
  const router = useRouter();
  const draft = usePracticeDraft(userId, detail.session.id);
  const snapshots = detail.submissions ?? [];
  const sequence = selected
    ? Number(selected)
    : (snapshots[0]?.sequence ?? 0);
  const chosen = snapshots.find((s) => s.sequence === sequence);
  const { operation, saved } = activity;
  useFocusEffect(
    useCallback(() => {
      if (
        saved?.change.kind === 'submit' &&
        saved.change.sessionId === detail.session.id &&
        saved.result.submission
      ) {
        router.setParams({
          snapshot: String(saved.result.submission.sequence),
        });
        operation.consumeSaved();
      }
    }, [saved, operation, router, detail.session.id]),
  );
  const obstacle = snapshotBlock(detail, {
    ready: work.ready && draft.ready,
    error: !!work.error || !!draft.error,
    saving: work.saving || draft.saving,
    edits: work.edits.length,
    message: draft.draft?.body ?? '',
  });
  return (
    <>
      <NativeAction
        secondary
        label="Back to your proposal"
        onPress={() => router.setParams({ work: '' })}
      />
      <SectionHeading>Feedback & revision</SectionHeading>
      {!snapshots.length ? (
        <ThemedText>
          Save a snapshot of your sent conversation, saved artifacts, and
          notes. You can keep editing the session afterward.
        </ThemedText>
      ) : null}
      <PracticeRecovery activity={activity} reload={reload} />
      {obstacle ? (
        <ThemedText accessibilityLiveRegion="polite">{obstacle}</ThemedText>
      ) : null}
      {draft.error ? (
        <InlineError
          message={draft.error}
          onRetry={() =>
            draft.ready
              ? draft.drafts.retrySave(detail.session.id)
              : void draft.drafts.load(detail.session.id)
          }
        />
      ) : null}
      <NativeAction
        label={snapshots.length ? 'Save a new snapshot' : 'Save snapshot'}
        disabled={
          blocked || !activity.ready || !!activity.pending || !!obstacle
        }
        onPress={() =>
          void operation.begin(snapshotChange(detail, Crypto.randomUUID()))
        }
      />
      <ThemedText type="small" themeColor="textSecondary">
        {snapshots.length
          ? 'No AI charge. Your session stays editable.'
          : 'Saving runs syntax checks without an AI charge. Request feedback separately below.'}
        {detail.session.status === 'paused'
          ? ' Saving resumes this paused session.'
          : ''}
      </ThemedText>
      {snapshots.length ? (
        <NativeChoice
          label="Saved snapshots"
          value={String(sequence)}
          options={snapshots.map((s) => ({
            value: String(s.sequence),
            label: `Snapshot ${s.sequence} · ${new Date(s.created_at).toLocaleDateString()}`,
          }))}
          onChange={(value) => router.setParams({ snapshot: value })}
        />
      ) : null}
      {selected &&
      (!/^\d{1,10}$/.test(selected) ||
        !wholeRevision(sequence, 1) ||
        !chosen) ? (
        <InlineError
          message="That snapshot is unavailable. Refresh or choose a saved snapshot."
          onRetry={reload}
        />
      ) : chosen ? (
        <SnapshotPanel
          key={sequence}
          userId={userId}
          detail={detail}
          sequence={sequence}
          activity={activity}
          blocked={blocked}
          reload={reload}
        />
      ) : null}
    </>
  );
}
function SnapshotPanel({
  userId,
  detail,
  sequence,
  activity,
  blocked,
  reload,
}: {
  userId: number;
  detail: PracticeDetail;
  sequence: number;
  activity: Activity;
  blocked: boolean;
  reload: () => void;
}) {
  const { snapshot, evaluation, refresh } = usePracticeFeedback(
    userId,
    detail.session.id,
    sequence,
  );
  const [showIncluded, setShowIncluded] = useState(false);
  const missing = [snapshot.error, evaluation.error].some(
    (e) => e instanceof ApiError && [403, 404].includes(e.status),
  );
  const loading = !snapshot.data || !evaluation.data;
  const stale =
    blocked ||
    snapshot.isError ||
    evaluation.isError ||
    snapshot.isPaused ||
    evaluation.isPaused ||
    !snapshot.isFetchedAfterMount ||
    !evaluation.isFetchedAfterMount;
  if (missing)
    return (
      <InlineError
        message="This snapshot is no longer available to this account."
        onRetry={refresh}
      />
    );
  if (loading)
    return snapshot.isError ||
      evaluation.isError ||
      snapshot.isPaused ||
      evaluation.isPaused ? (
      <InlineError
        message="Connect to load this saved assessment."
        onRetry={refresh}
      />
    ) : (
      <ThemedText accessibilityLiveRegion="polite">
        Loading this snapshot…
      </ThemedText>
    );
  const stored = snapshot.data;
  const assessment = evaluation.data;
  if (
    stored.session.id !== detail.session.id ||
    stored.submission.sequence !== sequence ||
    assessment.submission_sequence !== sequence
  )
    return (
      <InlineError
        message="The saved assessment could not be matched to this snapshot."
        onRetry={refresh}
      />
    );
  const feedback = assessment.feedback;
  const live = ['pending', 'running'].includes(assessment.request.status);
  const recent = activity.saved?.change;
  const savedReason =
    recent?.kind === 'feedback' &&
    recent.sessionId === detail.session.id &&
    recent.submission_sequence === sequence
      ? activity.saved?.result.request?.reason
      : null;
  const notice = feedbackNotice(
    assessment.unavailable || savedReason || assessment.request.reason,
  );
  const budget = detail.ai_budget?.total ?? detail.ai_budget;
  const request = () =>
    void activity.operation.begin({
      kind: 'feedback',
      request_id: Crypto.randomUUID(),
      conceptId: detail.session.concept_id,
      sessionId: detail.session.id,
      submission_sequence: sequence,
    });
  return (
    <>
      {stale ? (
        <InlineError
          message="Couldn’t refresh this snapshot. The saved result is shown; reconnect before requesting feedback."
          onRetry={() => {
            refresh();
            reload();
          }}
        />
      ) : null}
      {snapshotIsOlder(detail, stored.submission) ? (
        <ThemedText themeColor="textSecondary">
          Your session has newer work. This assessment covers the earlier
          snapshot; later changes are not included.
        </ThemedText>
      ) : null}
      <NativeAction
        secondary
        label={
          showIncluded ? 'Hide snapshot details' : 'What was saved & checked'
        }
        onPress={() => setShowIncluded(!showIncluded)}
      />
      {showIncluded ? <SnapshotContents snapshot={stored} /> : null}
      {feedback ? (
        <>
          <SectionHeading>Design feedback</SectionHeading>
          <LearningText text={feedback.summary} />
          <ThemedText type="small" themeColor="textSecondary">
            Assessed {feedback.coverage.turn_count} conversation{' '}
            {feedback.coverage.turn_count === 1 ? 'turn' : 'turns'}, selected
            artifact revisions, earlier revisions cited by the conversation,
            and saved notes. AI feedback is a judgment to review. “Not
            observed” means evidence is missing, not that your design is
            wrong.
          </ThemedText>
          {feedback.coverage.hints_given ? (
            <ThemedText type="small" themeColor="textSecondary">
              {feedback.coverage.hints_given} recorded hints. Assisted work
              does not establish unaided mastery.
            </ThemedText>
          ) : null}
          {feedback.findings.map((finding) => (
            <FeedbackFindingCard
              key={finding.id}
              finding={finding}
              detail={detail}
              snapshot={stored}
            />
          ))}
          <ThemedText>
            Revise your proposal, then save a new snapshot for another
            assessment. Your previous feedback stays available.
          </ThemedText>
        </>
      ) : live ? (
        <Card>
          <ThemedText accessibilityLiveRegion="polite">
            Feedback is being prepared. You can keep editing or leave the app;
            the result will be saved here.
          </ThemedText>
          <NativeAction
            secondary
            label="Refresh feedback status"
            onPress={refresh}
          />
        </Card>
      ) : (
        <>
          <ThemedText>
            Request an assessment of this complete snapshot. This uses your
            existing AI allowance and leaves the session editable.
          </ThemedText>
          {budget ? (
            <ThemedText type="small" themeColor="textSecondary">
              ${(budget.spent_microusd / 1e6).toFixed(3)} of $
              {(budget.cap_microusd / 1e6).toFixed(2)} committed
              {detail.ai_budget?.total ? ' across the pilot' : ' this month'}.
              Existing call and context limits apply.
            </ThemedText>
          ) : null}
          {assessment.busy ? (
            <ThemedText accessibilityLiveRegion="polite">
              Wait for the current AI request to finish. Your snapshot is
              saved.
            </ThemedText>
          ) : null}
          {notice ? (
            <ThemedText accessibilityLiveRegion="polite">{notice}</ThemedText>
          ) : null}
          <NativeAction
            label={
              assessment.request.id
                ? 'Request feedback again'
                : 'Request feedback'
            }
            disabled={
              stale ||
              !activity.ready ||
              !!activity.pending ||
              !assessment.can_request
            }
            onPress={() =>
              assessment.request.id
                ? Alert.alert(
                    'Request feedback again?',
                    'The earlier attempt may count toward your allowance. This starts a new attempt on the same saved snapshot.',
                    [
                      { text: 'Cancel', style: 'cancel' },
                      { text: 'Request again', onPress: request },
                    ],
                  )
                : request()
            }
          />
        </>
      )}
    </>
  );
}
function SnapshotContents({ snapshot }: { snapshot: SnapshotDetail }) {
  const saved = snapshot.submission;
  return (
    <Card>
      <ThemedText type="small">
        Exercise version {saved.exercise_version} · Conversation through turn{' '}
        {saved.turn_sequence} · Notes revision {saved.brief_revision}
      </ThemedText>
      <ThemedText>
        Syntax checks cover JSON and YAML. They do not assess design
        correctness or change your review schedule.
      </ThemedText>
      {saved.checks.map((check) => (
        <View key={check.artifact_id} style={{ gap: 8 }}>
          <ThemedText type="smallBold">
            {snapshot.artifacts.find(
              (a) => a.artifact_id === check.artifact_id,
            )?.title ?? check.artifact_id}{' '}
            · revision {check.revision}
          </ThemedText>
          <ThemedText>
            {check.message}
            {check.line
              ? ` Line ${check.line}${check.column ? `, column ${check.column}` : ''}.`
              : ''}
          </ThemedText>
          {check.revision > 0 ? (
            <NavRow
              title="Read saved artifact"
              subtitle={`${check.language} · revision ${check.revision}`}
              href={{
                pathname: '/learning/practice/[session]/artifact',
                params: {
                  session: snapshot.session.id,
                  artifact: check.artifact_id,
                  revision: String(check.revision),
                },
              }}
            />
          ) : null}
        </View>
      ))}
      {snapshot.session_brief.entries.length ? (
        <ThemedText type="smallBold">Saved notes</ThemedText>
      ) : (
        <ThemedText>No notes were saved in this snapshot.</ThemedText>
      )}
      {snapshot.session_brief.entries.map((entry) => (
        <View key={entry.id} style={{ gap: 6 }}>
          <ThemedText type="smallBold">
            {entry.type.replaceAll('_', ' ')}
          </ThemedText>
          <LearningText text={entry.text} />
        </View>
      ))}
    </Card>
  );
}
