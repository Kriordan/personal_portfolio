import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import {
  LearningAccountState,
  LearningText,
  LearningUnavailable,
} from '@/components/learning-content';
import {
  InlineError,
  PageHeading,
  Screen,
  ScreenState,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useAuth } from '@/lib/auth-context';
import { practiceKeys, validSessionId } from '@/lib/practice-model';
import { practiceApi } from '@/lib/practice-runtime';

export default function SavedArtifact() {
  const { user } = useAuth();
  const { session, artifact, revision } = useLocalSearchParams<{
    session: string;
    artifact: string;
    revision: string;
  }>();
  if (
    !validSessionId(session) ||
    typeof artifact !== 'string' ||
    !/^[a-z0-9-]{1,128}$/.test(artifact) ||
    !/^\d{1,10}$/.test(revision ?? '') ||
    Number(revision) > 2147483647
  )
    return <LearningUnavailable title="Artifact unavailable" />;
  return user ? (
    <Artifact
      key={user.id + session + artifact + revision}
      userId={user.id}
      id={session}
      artifact={artifact}
      revision={Number(revision)}
    />
  ) : (
    <LearningAccountState />
  );
}
function Artifact({
  userId,
  id,
  artifact,
  revision,
}: {
  userId: number;
  id: string;
  artifact: string;
  revision: number;
}) {
  const query = useQuery({
    queryKey: practiceKeys.revision(userId, id, artifact, revision),
    queryFn: () => practiceApi.revision(id, artifact, revision),
    enabled: revision > 0,
  });
  if (revision === 0)
    return (
      <Screen>
        <PageHeading title="No saved revision" />
        <ThemedText>
          This artifact was empty when the conversation view was loaded.
        </ThemedText>
      </Screen>
    );
  if (query.isError)
    return (
      <Screen>
        <InlineError
          message="Couldn’t load this saved revision. It may no longer be available."
          onRetry={() => void query.refetch()}
        />
      </Screen>
    );
  if (!query.data)
    return (
      <ScreenState title="Loading saved revision" loading={!query.isPaused} />
    );
  const data = query.data;
  return (
    <Screen>
      <PageHeading
        title={data.artifact.title}
        subtitle={`Saved revision ${revision} · ${data.revision.language}`}
      />
      {data.current_revision !== revision ? (
        <ThemedText themeColor="textSecondary">
          A newer revision ({data.current_revision}) exists. This is the exact
          saved revision you selected.
        </ThemedText>
      ) : null}
      <LearningText
        text={data.revision.body || 'This saved revision is empty.'}
        code={data.artifact.format !== 'markdown'}
      />
    </Screen>
  );
}
