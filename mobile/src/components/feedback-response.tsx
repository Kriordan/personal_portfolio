import * as Crypto from 'expo-crypto';
import { Keyboard, Pressable, StyleSheet, TextInput, View } from 'react-native';
import { LearningText, LearningUnavailable } from './learning-content';
import { PracticeRecovery } from './practice-content';
import {
  Card,
  InlineError,
  NativeAction,
  NavRow,
  Screen,
  ScreenState,
} from './screen';
import { ThemedText } from './themed-text';
import {
  useFeedbackResponseDrafts,
  usePracticeOperation,
} from '@/hooks/use-practice';
import { usePracticeFeedback } from '@/hooks/use-practice-feedback';
import { useTheme } from '@/hooks/use-theme';
import { ApiError } from '@/lib/api-client';
import {
  copyResponse,
  feedbackReturnRoute,
  responseChoices,
  responseKey,
  responseNoteLength,
  responseRoute,
  validResponseEdit,
  type FeedbackSource,
  type ResponseEdit,
} from '@/lib/feedback-response-model';

export function FeedbackResponse({
  userId,
  source,
}: {
  userId: number;
  source: FeedbackSource;
}) {
  const theme = useTheme();
  const { snapshot, evaluation, refresh } = usePracticeFeedback(
    userId,
    source.sessionId,
    source.submission_sequence,
  );
  const activity = usePracticeOperation(userId);
  const local = useFeedbackResponseDrafts(userId, source.sessionId);
  const finding = evaluation.data?.feedback?.findings.find(
    (f) => f.id === source.findingId,
  );
  if (
    [snapshot.error, evaluation.error].some(
      (e) => e instanceof ApiError && [403, 404].includes(e.status),
    ) ||
    (evaluation.data?.feedback && !finding)
  )
    return (
      <LearningUnavailable
        title="Feedback unavailable"
        message="This finding is no longer available to this account."
      />
    );
  if (!finding || !snapshot.data)
    return (
      <ScreenState
        loading={snapshot.isFetching || evaluation.isFetching}
        title="Loading your response"
        message="Reconnect to read this saved finding."
        onRetry={refresh}
      />
    );
  const conceptId = snapshot.data.session.concept_id;
  const saved: ResponseEdit = {
    kind: 'annotate',
    findingId: source.findingId,
    submission_sequence: source.submission_sequence,
    base_revision: finding.annotation.revision,
    decision: finding.annotation.decision,
    note: finding.annotation.note,
  };
  const draft = local.edits.find((e) => responseKey(e) === responseKey(saved));
  const edit = draft ?? saved;
  const stale = !!draft && draft.base_revision !== saved.base_revision;
  const blocked = !local.ready || !activity.ready || !!activity.pending;
  const update = (patch: Partial<ResponseEdit>) =>
    local.drafts.edit(source.sessionId, { ...edit, ...patch });
  const changed = edit.decision !== saved.decision || edit.note !== saved.note;
  const valid = validResponseEdit(edit);
  const readFailed = evaluation.isError || snapshot.isError;
  const full = !draft && local.edits.length >= 50;
  const canPractice =
    finding.practice_available &&
    !changed &&
    !stale &&
    !blocked &&
    !local.error &&
    !local.saving &&
    !readFailed;
  return (
    <Screen>
      <ThemedText type="title" accessibilityRole="header">
        Your response
      </ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        Snapshot {source.submission_sequence} · Optional reflection
      </ThemedText>
      <NavRow
        title="Back to saved feedback"
        href={feedbackReturnRoute(conceptId, source)}
      />
      <Card>
        <ThemedText type="subtitle" accessibilityRole="header">
          {finding.title}
        </ThemedText>
        <LearningText text={finding.explanation} />
        <ThemedText type="smallBold">Suggested next step</ThemedText>
        <LearningText text={finding.next_step} />
      </Card>
      <PracticeRecovery activity={activity} reload={refresh} />
      {readFailed ? (
        <InlineError
          message="Couldn’t refresh the saved response. Reconnect before saving or starting review."
          onRetry={refresh}
        />
      ) : null}
      {!local.ready || local.error ? (
        <InlineError
          message={local.error ?? 'Loading this device’s response drafts…'}
          onRetry={() =>
            local.ready
              ? local.drafts.retrySave(source.sessionId)
              : void local.drafts.load(source.sessionId)
          }
        />
      ) : null}
      {full ? (
        <InlineError message="This session has 50 local response drafts. Save or discard one before starting another." />
      ) : null}
      <Card>
        <ThemedText type="subtitle" accessibilityRole="header">
          What do you think?
        </ThemedText>
        <ThemedText themeColor="textSecondary">
          Feedback is a suggestion to examine. Your response won’t change the
          assessment or your review schedule.
        </ThemedText>
        <View
          accessibilityRole="radiogroup"
          accessibilityLabel="Your response to this finding"
          style={styles.choices}
        >
          {responseChoices.map((choice) => (
            <Pressable
              key={choice.value}
              accessibilityRole="radio"
              accessibilityLabel={choice.label}
              accessibilityState={{
                checked: edit.decision === choice.value,
                disabled: blocked || full,
              }}
              disabled={blocked || full}
              onPress={() => update({ decision: choice.value })}
              style={[
                styles.choice,
                {
                  backgroundColor:
                    edit.decision === choice.value
                      ? theme.accentSoft
                      : theme.backgroundElement,
                },
              ]}
            >
              <ThemedText
                type="smallBold"
                themeColor={
                  edit.decision === choice.value ? 'accent' : 'textSecondary'
                }
              >
                {choice.label}
              </ThemedText>
            </Pressable>
          ))}
        </View>
        <ThemedText type="smallBold">Note (optional)</ThemedText>
        <TextInput
          accessibilityLabel="Your feedback response note"
          multiline
          maxLength={4000}
          editable={!blocked && !full}
          value={edit.note}
          onChangeText={(note) => update({ note })}
          placeholder="What would you keep, question, or change?"
          placeholderTextColor={theme.textSecondary}
          style={[
            styles.note,
            { color: theme.text, backgroundColor: theme.backgroundElement },
          ]}
        />
        <ThemedText type="small" themeColor="textSecondary">
          {responseNoteLength(edit.note)} / 2,000 characters
        </ThemedText>
        <NativeAction
          secondary
          label="Done typing"
          onPress={Keyboard.dismiss}
        />
        {!valid ? (
          <InlineError message="Use valid text without null characters, within 2,000 characters. Your draft stays on this device." />
        ) : null}
        <ThemedText
          type="small"
          themeColor="textSecondary"
          accessibilityLiveRegion="polite"
        >
          {local.saving
            ? 'Protecting your draft on this device…'
            : local.error
              ? 'Draft not yet protected.'
              : draft
                ? 'Draft saved on this device. Save your response to share it with the web.'
                : 'Showing your saved response.'}
        </ThemedText>
        <NativeAction
          label="Save response"
          disabled={
            blocked ||
            local.saving ||
            !!local.error ||
            readFailed ||
            stale ||
            !changed ||
            !valid
          }
          onPress={() => {
            Keyboard.dismiss();
            void activity.operation.begin({
              ...copyResponse(edit),
              conceptId,
              sessionId: source.sessionId,
              request_id: Crypto.randomUUID(),
            });
          }}
        />
      </Card>
      {stale ? (
        <Card>
          <ThemedText type="subtitle" accessibilityRole="header">
            Your response changed elsewhere
          </ThemedText>
          <ThemedText>
            Your draft is above. Compare it with the current saved response
            before choosing what to keep.
          </ThemedText>
          <ThemedText type="smallBold">
            Saved:{' '}
            {responseChoices.find((c) => c.value === saved.decision)?.label} ·
            Revision {saved.base_revision}
          </ThemedText>
          <LearningText text={saved.note || '(No saved note)'} />
          <NativeAction
            label="Keep my draft with this version"
            secondary
            disabled={blocked || readFailed || local.saving}
            onPress={() => local.drafts.rebase(source.sessionId, saved)}
          />
        </Card>
      ) : null}
      {draft ? (
        <NativeAction
          label="Use saved response"
          secondary
          disabled={blocked || readFailed || local.saving}
          onPress={() =>
            void local.drafts
              .clearIfMatches(source.sessionId, draft)
              .catch(() => {})
          }
        />
      ) : null}
      {finding.kind === 'concern' ? (
        <Card>
          <ThemedText type="subtitle" accessibilityRole="header">
            Practice this idea
          </ThemedText>
          <ThemedText themeColor="textSecondary">
            {finding.practice_available
              ? 'A short pass through linked questions. Only your explicit ratings update your existing schedule. No AI request is needed.'
              : saved.decision === 'agree'
                ? 'There are no linked review questions for this finding. You can revisit the explanation or revise your proposal.'
                : 'Save Agree to make any linked review questions available. You can also disagree or leave this unreviewed.'}
          </ThemedText>
          {changed || stale ? (
            <ThemedText type="small">
              Save or discard your response changes before starting review.
            </ThemedText>
          ) : null}
          {canPractice ? (
            <NavRow
              title="Start focused review"
              href={responseRoute(source, true)}
            />
          ) : null}
        </Card>
      ) : null}
    </Screen>
  );
}
const styles = StyleSheet.create({
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  choice: {
    padding: 14,
    minHeight: 48,
    borderRadius: 12,
    justifyContent: 'center',
  },
  note: {
    minHeight: 150,
    maxHeight: 340,
    padding: 14,
    borderRadius: 12,
    fontSize: 17,
    textAlignVertical: 'top',
  },
});
