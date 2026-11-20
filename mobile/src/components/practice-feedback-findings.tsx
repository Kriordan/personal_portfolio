import { useState } from 'react';
import { useRouter } from 'expo-router';
import { View } from 'react-native';
import { LearningText } from './learning-content';
import { Card, InlineError, NativeAction, NavRow } from './screen';
import { ThemedText } from './themed-text';
import {
  evidenceText,
  feedbackKinds,
  type FeedbackEvidence,
  type FeedbackFinding,
  type SnapshotDetail,
} from '@/lib/practice-feedback-model';
import type { PracticeDetail } from '@/lib/practice-model';
import { responseChoices, responseRoute } from '@/lib/feedback-response-model';

export function FeedbackFindingCard({
  finding,
  detail,
  snapshot,
}: {
  finding: FeedbackFinding;
  detail: PracticeDetail;
  snapshot: SnapshotDetail;
}) {
  const router = useRouter();
  const conceptId = detail.session.concept_id;
  const source = finding.evidence.find(
    (e) => e.kind === 'artifact' || e.kind === 'note',
  );
  const part =
    source?.kind === 'artifact'
      ? `artifact:${source.artifact_id}`
      : source?.kind === 'note'
        ? 'brief'
        : '';
  return (
    <Card>
      <ThemedText type="smallBold" themeColor="accent">
        {feedbackKinds[finding.kind]}
      </ThemedText>
      <ThemedText type="small" themeColor="textSecondary">
        {finding.dimension_label}
      </ThemedText>
      <ThemedText type="subtitle" accessibilityRole="header">
        {finding.title}
      </ThemedText>
      <LearningText text={finding.explanation} />
      {finding.evidence.map((evidence, index) => (
        <Evidence
          key={`${evidence.source_id}:${index}`}
          evidence={evidence}
          detail={detail}
          snapshot={snapshot}
        />
      ))}
      <ThemedText type="smallBold">Next step</ThemedText>
      <LearningText text={finding.next_step} />
      <NavRow
        title="Your response"
        subtitle={
          responseChoices.find((c) => c.value === finding.annotation.decision)
            ?.label ?? 'Not reviewed'
        }
        href={responseRoute({
          sessionId: detail.session.id,
          submission_sequence: snapshot.submission.sequence,
          findingId: finding.id,
        })}
      />
      {finding.kind !== 'strength'
        ? finding.remediation.map((link) => (
            <NavRow
              key={`${link.concept_id}:${link.section_id}`}
              title="Revisit the explanation"
              subtitle={link.section_id.replaceAll('-', ' ')}
              href={{
                pathname: '/learning/concepts/[id]',
                params: {
                  id: link.concept_id,
                  section: link.section_id,
                  ...(link.concept_id === conceptId
                    ? {
                        practice_session: detail.session.id,
                        work: 'feedback',
                        snapshot: String(snapshot.submission.sequence),
                      }
                    : {}),
                },
              }}
            />
          ))
        : null}
      <NativeAction
        secondary
        label={part ? 'Revise this work' : 'Revise your proposal'}
        onPress={() => router.setParams({ work: part })}
      />
    </Card>
  );
}
function Evidence({
  evidence,
  detail,
  snapshot,
}: {
  evidence: FeedbackEvidence;
  detail: PracticeDetail;
  snapshot: SnapshotDetail;
}) {
  const [open, setOpen] = useState(false);
  const label =
    evidence.kind === 'artifact'
      ? `${evidence.artifact_id} · revision ${evidence.revision}, line ${evidence.line}`
      : evidence.kind === 'turn'
        ? `Your message · turn ${evidence.sequence}`
        : `Saved note · revision ${evidence.revision}`;
  const body = evidenceText(evidence, detail, snapshot);
  return (
    <View style={{ gap: 8 }}>
      <ThemedText selectable>“{evidence.quote}”</ThemedText>
      {evidence.kind === 'artifact' ? (
        <NavRow
          title="Read the cited revision"
          subtitle={label}
          href={{
            pathname: '/learning/practice/[session]/artifact',
            params: {
              session: detail.session.id,
              artifact: evidence.artifact_id,
              revision: String(evidence.revision),
            },
          }}
        />
      ) : (
        <>
          <ThemedText type="small" themeColor="textSecondary">
            {label}
          </ThemedText>
          <NativeAction
            secondary
            label={open ? 'Hide original source' : 'Read original source'}
            onPress={() => setOpen(!open)}
          />
          {open ? (
            body !== null ? (
              <LearningText text={body} />
            ) : (
              <InlineError message="This exact source could not be confirmed. Refresh the snapshot before relying on the citation." />
            )
          ) : null}
        </>
      )}
    </View>
  );
}
