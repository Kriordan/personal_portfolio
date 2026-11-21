import * as Crypto from 'expo-crypto';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useState } from 'react';
import { Linking, View } from 'react-native';
import {
  LearningAccountState,
  LearningText,
  LearningUnavailable,
} from '@/components/learning-content';
import { ConceptHeader, StudyStatus } from '@/components/concept-workspace';
import { ConceptRetryLab } from '@/components/concept-retry-lab';
import { NativeChoice } from '@/components/native-choice';
import {
  Card,
  InlineError,
  NativeAction,
  Screen,
  ScreenState,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useConcept, useConceptStudy } from '@/hooks/use-concepts';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import { initialSection, type ConceptDetail } from '@/lib/concept-model';
import { validNoteId } from '@/lib/learning-model';

export default function ConceptScreen() {
  const { user } = useAuth();
  const { id, section } = useLocalSearchParams<{
    id: string;
    section?: string;
  }>();
  if (!validNoteId(id))
    return (
      <LearningUnavailable
        title="Concept unavailable"
        message="Choose a concept from Learning."
      />
    );
  return user ? (
    <Lesson
      key={user.id + ':' + id}
      userId={user.id}
      id={id}
      requested={typeof section === 'string' ? section : undefined}
    />
  ) : (
    <LearningAccountState />
  );
}
function Lesson({
  userId,
  id,
  requested,
}: {
  userId: number;
  id: string;
  requested?: string;
}) {
  const query = useConcept(userId, id);
  if (query.error instanceof ApiError && query.error.status === 404)
    return (
      <LearningUnavailable
        title="Concept unavailable"
        message="This concept isn’t available to this account."
      />
    );
  if (
    (!query.data && query.isPending) ||
    (!query.isFetchedAfterMount && query.isFetching)
  )
    return (
      <ScreenState
        loading={!query.isPaused}
        title={query.isPaused ? 'You’re offline' : 'Loading your lesson'}
        message="Connect to open your lesson and saved place."
      />
    );
  if (!query.data)
    return (
      <ScreenState
        title="Couldn’t load this lesson"
        onRetry={() => void query.refetch()}
      />
    );
  return (
    <LessonContent
      key={query.data.concept.version}
      detail={query.data}
      userId={userId}
      requested={requested}
      refreshFailed={
        query.isError || query.isPaused || !query.isFetchedAfterMount
      }
      reload={() => void query.refetch()}
    />
  );
}
function LessonContent({
  detail,
  userId,
  requested,
  reload,
  refreshFailed,
}: {
  detail: ConceptDetail;
  userId: number;
  requested?: string;
  reload: () => void;
  refreshFailed: boolean;
}) {
  const { concept, progress } = detail;
  const router = useRouter();
  const [sectionId, setSectionId] = useState(() =>
    initialSection(concept, progress, requested),
  );
  const [linkError, setLinkError] = useState(false);
  const study = useConceptStudy(userId);
  const sections = concept.content.sections;
  const index = Math.max(
    0,
    sections.findIndex((section) => section.id === sectionId),
  );
  const section = sections[index];
  const busy = !study.ready || !!study.pending;
  const savedHere =
    progress?.reading_section === section.id &&
    progress.reading_version === concept.version;
  return (
    <Screen key={section.id}>
      <ConceptHeader concept={concept} mode="learn" />
      <StudyStatus activity={study} onReload={reload} />
      {refreshFailed ? (
        <InlineError
          message="Couldn’t refresh your saved place. Reconnect before saving a change."
          onRetry={reload}
        />
      ) : null}
      {!progress ? (
        <Card>
          <ThemedText>{concept.content.summary}</ThemedText>
          <ThemedText themeColor="textSecondary">
            Start learning to save your place and include this concept in your
            reviews.
          </ThemedText>
          <NativeAction
            label="Start learning"
            disabled={busy || refreshFailed}
            onPress={() =>
              void study.study.begin({ kind: 'enroll', conceptId: concept.id })
            }
          />
        </Card>
      ) : null}
      <NativeChoice
        label="Lesson section"
        value={section.id}
        options={sections.map((item, i) => ({
          value: item.id,
          label: i + 1 + '. ' + item.title,
        }))}
        onChange={setSectionId}
      />
      <View style={{ gap: 12 }}>
        <ThemedText type="small" themeColor="textSecondary">
          Section {index + 1} of {sections.length}
        </ThemedText>
        <ThemedText type="subtitle" accessibilityRole="header">
          {section.title}
        </ThemedText>
        <LearningText text={section.markdown} />
      </View>
      {concept.id === 'idempotency' && section.id === 'retries' ? (
        <ConceptRetryLab />
      ) : null}
      {progress ? (
        <>
          <NativeAction
            label={savedHere ? 'Place saved' : 'Save my place'}
            secondary
            disabled={busy || savedHere || refreshFailed}
            onPress={() =>
              void study.study.begin({
                kind: 'position',
                conceptId: concept.id,
                content_version: concept.version,
                section_id: section.id,
                expected_revision: progress.revision,
                request_id: Crypto.randomUUID(),
              })
            }
          />
          <ThemedText
            type="small"
            themeColor="textSecondary"
            accessibilityLiveRegion="polite"
          >
            {progress.reading_section
              ? 'Saved place: ' +
                (sections.find((s) => s.id === progress.reading_section)
                  ?.title ?? 'Start of lesson')
              : 'Save a section to continue from the same place on web or phone.'}
          </ThemedText>
        </>
      ) : null}
      {index + 1 < sections.length ? (
        <NativeAction
          label="Next section"
          onPress={() => setSectionId(sections[index + 1].id)}
        />
      ) : null}
      {index === sections.length - 1 ? (
        <NativeAction
          label="Practice recall"
          onPress={() =>
            router.push({
              pathname: '/learning/concepts/[id]/review',
              params: { id: concept.id },
            })
          }
        />
      ) : null}
      {index > 0 ? (
        <NativeAction
          label="Previous section"
          secondary
          onPress={() => setSectionId(sections[index - 1].id)}
        />
      ) : null}
      {index === 0 ? (
        <Card>
          <ThemedText type="smallBold" accessibilityRole="header">
            What you’ll work on
          </ThemedText>
          {concept.content.learning_objectives.map((objective) => (
            <ThemedText key={objective}>• {objective}</ThemedText>
          ))}
          <ThemedText type="small" themeColor="textSecondary">
            Builds on: {concept.content.prerequisite_knowledge.join('; ')}.
          </ThemedText>
        </Card>
      ) : null}
      {index === sections.length - 1 ? (
        <View style={{ gap: 8 }}>
          <ThemedText type="subtitle" accessibilityRole="header">
            References
          </ThemedText>
          {concept.content.references
            .filter((ref) => /^https:\/\//.test(ref.url))
            .map((ref) => (
              <ThemedText
                key={ref.url}
                type="linkPrimary"
                accessibilityRole="link"
                onPress={() => {
                  void Linking.openURL(ref.url).catch(() => setLinkError(true));
                }}
              >
                {ref.title}
              </ThemedText>
            ))}
          {linkError ? (
            <InlineError message="Couldn’t open the reference. Check your connection and try again." />
          ) : null}
        </View>
      ) : null}
    </Screen>
  );
}
