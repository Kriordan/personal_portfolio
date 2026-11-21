import * as Crypto from 'expo-crypto';
import { Stack, useLocalSearchParams, useRouter } from 'expo-router';
import { useCallback, useRef } from 'react';
import {
  Alert,
  FlatList,
  Pressable,
  StyleSheet,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { ConceptHeader } from '@/components/concept-workspace';
import { PracticeSessionPicker } from '@/components/practice-session-picker';
import {
  LearningAccountState,
  LearningUnavailable,
} from '@/components/learning-content';
import {
  ConversationMessage,
  PracticeRecovery,
} from '@/components/practice-content';
import { InlineError, NativeAction, ScreenState } from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useConcept } from '@/hooks/use-concepts';
import {
  usePracticeDetail,
  usePracticeDraft,
  usePracticeOperation,
  usePracticeWork,
} from '@/hooks/use-practice';
import { useTheme } from '@/hooks/use-theme';
import { ApiError } from '@/lib/api-client';
import { useAuth } from '@/lib/auth-context';
import type { Concept } from '@/lib/concept-model';
import { draftOutdated } from '@/lib/practice-drafts';
import { workBlocksSend } from '@/lib/practice-work-drafts';
import { validNoteId } from '@/lib/learning-model';
import {
  latestSequence,
  messageBytes,
  MESSAGE_LIMIT,
  replyLive,
  replyNotice,
  validSessionId,
  type PracticeMessage,
} from '@/lib/practice-model';

export default function DiscussScreen() {
  const { user } = useAuth();
  const { id, practice_session } = useLocalSearchParams<{
    id: string;
    practice_session?: string;
  }>();
  if (
    !validNoteId(id) ||
    (practice_session !== undefined && !validSessionId(practice_session))
  )
    return <LearningUnavailable title="Conversation unavailable" />;
  return user ? (
    <Discuss
      key={user.id + id}
      userId={user.id}
      id={id}
      sessionId={practice_session}
    />
  ) : (
    <LearningAccountState />
  );
}
function Discuss({
  userId,
  id,
  sessionId,
}: {
  userId: number;
  id: string;
  sessionId?: string;
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
        title="Loading Discuss"
        loading={query.isPending && !query.isPaused}
        onRetry={() => void query.refetch()}
      />
    );
  return sessionId ? (
    <Conversation
      key={userId + sessionId}
      userId={userId}
      id={sessionId}
      concept={query.data.concept}
    />
  ) : (
    <PracticeSessionPicker userId={userId} concept={query.data.concept} />
  );
}
const messageKey = (m: PracticeMessage) => String(m.sequence);
function Conversation({
  userId,
  id,
  concept,
}: {
  userId: number;
  id: string;
  concept: Concept;
}) {
  const query = usePracticeDetail(userId, id);
  const activity = usePracticeOperation(userId);
  const draft = usePracticeDraft(userId, id);
  const work = usePracticeWork(userId, id);
  const theme = useTheme();
  const router = useRouter();
  const list = useRef<FlatList<PracticeMessage>>(null);
  const follow = useRef(true);
  const hasScrolled = useRef(false);
  const jumpToLatest = useCallback(() => {
    follow.current = true;
    list.current?.scrollToEnd({ animated: true });
  }, []);
  const renderMessage = useCallback(
    ({ item }: { item: PracticeMessage }) => (
      <ConversationMessage message={item} sessionId={id} />
    ),
    [id],
  );
  const { pending } = activity;
  if (
    query.error instanceof ApiError &&
    [403, 404].includes(query.error.status)
  )
    return <LearningUnavailable title="Conversation unavailable" />;
  if (!query.data)
    return (
      <ScreenState
        title="Loading your conversation"
        loading={query.isPending && !query.isPaused}
        onRetry={() => void query.refetch()}
      />
    );
  const detail = query.data;
  if (detail.session.concept_id !== concept.id)
    return (
      <LearningUnavailable title="Choose this conversation from its concept" />
    );
  const blocked =
    !activity.ready ||
    !draft.ready ||
    !!pending ||
    query.isError ||
    query.isPaused ||
    !query.isFetchedAfterMount;
  const live = replyLive(detail.reply);
  const notice = replyNotice(detail.reply);
  const body =
    pending?.kind === 'send' && pending.sessionId === id
      ? pending.body
      : (draft.draft?.body ?? '');
  const outdated = draftOutdated(draft.draft, detail);
  const count = messageBytes(body);
  const paused = detail.session.status === 'paused';
  const requestReply = (recent = false) =>
    void activity.operation.begin({
      kind: 'reply',
      sessionId: id,
      conceptId: concept.id,
      expected_sequence: latestSequence(detail),
      request_id: Crypto.randomUUID(),
      ...(recent ? { context: 'recent' as const } : {}),
    });
  return (
    <SafeAreaView
      edges={['left', 'right', 'bottom']}
      style={[styles.fill, { backgroundColor: theme.background }]}
    >
      <Stack.Screen
        options={{
          headerRight: () => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel="Jump to latest message"
              onPress={jumpToLatest}
              style={styles.latest}
            >
              <ThemedText type="smallBold" themeColor="accent">
                Latest
              </ThemedText>
            </Pressable>
          ),
        }}
      />
      <FlatList
        ref={list}
        data={detail.messages}
        keyExtractor={messageKey}
        renderItem={renderMessage}
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="interactive"
        contentInsetAdjustmentBehavior="automatic"
        automaticallyAdjustKeyboardInsets
        onScrollBeginDrag={() => {
          hasScrolled.current = true;
        }}
        onScroll={(event) => {
          if (!hasScrolled.current) return;
          const { layoutMeasurement, contentOffset, contentSize } =
            event.nativeEvent;
          follow.current =
            contentSize.height - layoutMeasurement.height - contentOffset.y <
            100;
        }}
        scrollEventThrottle={100}
        onContentSizeChange={() => {
          if (follow.current)
            requestAnimationFrame(() => {
              if (follow.current)
                list.current?.scrollToEnd({ animated: false });
            });
        }}
        ListHeaderComponent={
          <View style={styles.header}>
            <ConceptHeader concept={concept} mode="discuss" />
            <View style={styles.toolbar}>
              <View style={styles.fill}>
                <NativeAction
                  secondary
                  label="Scenario & work"
                  onPress={() =>
                    router.push({
                      pathname: '/learning/practice/[session]/context',
                      params: { session: id },
                    })
                  }
                />
              </View>
              <View style={styles.fill}>
                <NativeAction
                  secondary
                  label="Conversations"
                  onPress={() =>
                    router.replace({
                      pathname: '/learning/concepts/[id]/discuss',
                      params: { id: concept.id },
                    })
                  }
                />
              </View>
            </View>
            <ThemedText type="small" themeColor="textSecondary">
              Session {id.slice(-8)} · {paused ? 'Paused' : 'Active'} · Saved on
              web and phone
            </ThemedText>
          </View>
        }
        ListFooterComponent={
          <View style={styles.footer}>
            <PracticeRecovery
              activity={activity}
              reload={() => void query.refetch()}
            />
            {query.isError || query.isPaused ? (
              <InlineError
                message="Couldn’t refresh. Reconnect before sending; the saved conversation is still shown."
                onRetry={() => void query.refetch()}
              />
            ) : null}
            {notice ? (
              <ThemedText
                accessibilityLiveRegion="polite"
                type="small"
                themeColor="textSecondary"
              >
                {notice}
              </ThemedText>
            ) : null}
            {detail.feedback_pending ? (
              <ThemedText type="small">
                Feedback is being prepared on the web. You can send again when
                it finishes.
              </ThemedText>
            ) : null}
            {detail.reply.can_request && !paused ? (
              <NativeAction
                secondary
                label="Request an interviewer reply"
                disabled={blocked}
                onPress={() => requestReply()}
              />
            ) : null}
            {detail.reply.can_continue_recent && !paused ? (
              <NativeAction
                secondary
                label="Continue with recent messages"
                disabled={blocked}
                onPress={() =>
                  Alert.alert(
                    'Continue with recent messages?',
                    'The interviewer will read the messages that fit, along with your saved work, brief, and clarified requirements. Older messages stay saved but won’t be read. Review important assumptions and decisions in the web brief before continuing.',
                    [
                      { text: 'Cancel', style: 'cancel' },
                      { text: 'Continue', onPress: () => requestReply(true) },
                    ],
                  )
                }
              />
            ) : null}
            {detail.check_in_due ? (
              <ThemedText type="small" themeColor="textSecondary">
                You’ve worked through {detail.learner_turns} turns. This is a
                good point to pause or review your decisions. You can keep
                going.
              </ThemedText>
            ) : null}
            <View
              style={[
                styles.composer,
                { borderColor: theme.backgroundSelected },
              ]}
            >
              <ThemedText type="smallBold">Your message</ThemedText>
              <TextInput
                accessibilityLabel="Your message to the interviewer"
                multiline
                value={body}
                maxLength={8192}
                onChangeText={(text) => draft.drafts.edit(id, text, detail)}
                editable={draft.ready && !pending}
                placeholder="Ask a question or explain your reasoning…"
                placeholderTextColor={theme.textSecondary}
                style={[
                  styles.input,
                  {
                    color: theme.text,
                    backgroundColor: theme.backgroundElement,
                  },
                ]}
              />
              {draft.error ? (
                <InlineError
                  message={draft.error}
                  onRetry={() =>
                    draft.ready
                      ? draft.drafts.retrySave(id)
                      : void draft.drafts.load(id)
                  }
                />
              ) : (
                <ThemedText type="small" themeColor="textSecondary">
                  {!draft.ready
                    ? 'Loading this device’s draft…'
                    : draft.saving
                      ? 'Saving draft on this device…'
                      : body
                        ? 'Draft saved on this device · Cleared on sign-out'
                        : 'Unsent drafts stay on this device until sent or cleared.'}
                </ThemedText>
              )}
              {outdated && !pending ? (
                <View style={styles.footer}>
                  <ThemedText>
                    Your conversation or saved work changed after you began this
                    draft. Read the updates before continuing.
                  </ThemedText>
                  <NativeAction
                    secondary
                    label="Review scenario & work"
                    onPress={() =>
                      router.push({
                        pathname: '/learning/practice/[session]/context',
                        params: { session: id },
                      })
                    }
                  />
                  <NativeAction
                    secondary
                    label="I’ve reviewed the updates"
                    disabled={blocked || live}
                    onPress={() => draft.drafts.rebase(id, detail)}
                  />
                </View>
              ) : null}
              {count > MESSAGE_LIMIT ? (
                <InlineError message="This message is too long. Shorten it to 8 KiB before sending." />
              ) : null}
              {!work.ready || work.error || work.edits.length ? (
                <View style={styles.footer}>
                  <ThemedText>
                    {work.error ??
                      (!work.ready
                        ? 'Checking for unfinished Build edits…'
                        : 'You have unfinished Build edits. Save or discard them before sending so the interviewer sees your intended work.')}
                  </ThemedText>
                  <NativeAction
                    secondary
                    label="Open Build"
                    onPress={() =>
                      router.replace({
                        pathname: '/learning/concepts/[id]/build',
                        params: { id: concept.id, practice_session: id },
                      })
                    }
                  />
                  {work.error ? (
                    <NativeAction
                      secondary
                      label="Check Build drafts"
                      onPress={() =>
                        work.ready
                          ? work.drafts.retrySave(id)
                          : void work.drafts.load(id)
                      }
                    />
                  ) : null}
                </View>
              ) : null}
              <NativeAction
                label={paused ? 'Resume to send a message' : 'Send message'}
                disabled={
                  blocked ||
                  workBlocksSend(work) ||
                  outdated ||
                  draft.saving ||
                  !!draft.error ||
                  live ||
                  !!detail.feedback_pending ||
                  paused ||
                  !body.trim() ||
                  count > MESSAGE_LIMIT
                }
                onPress={() => {
                  if (draft.draft) {
                    follow.current = true;
                    void activity.operation.begin({
                      ...draft.draft,
                      request_id: Crypto.randomUUID(),
                    });
                  }
                }}
              />
            </View>
            <NativeAction
              secondary
              label={paused ? 'Resume conversation' : 'Pause conversation'}
              disabled={blocked}
              onPress={() =>
                void activity.operation.begin({
                  kind: paused ? 'resume' : 'pause',
                  conceptId: concept.id,
                  sessionId: id,
                  request_id: Crypto.randomUUID(),
                })
              }
            />
            <ThemedText type="small" themeColor="textSecondary">
              Leaving this screen keeps the session available. Pausing stops the
              next AI step; a reply already in progress may finish.
            </ThemedText>
          </View>
        }
      />
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  latest: { minHeight: 44, paddingHorizontal: 8, justifyContent: 'center' },
  fill: { flex: 1 },
  content: {
    padding: 20,
    gap: 4,
    maxWidth: 860,
    width: '100%',
    alignSelf: 'center',
  },
  header: { gap: 12, marginBottom: 20 },
  toolbar: { flexDirection: 'row', gap: 8 },
  footer: { gap: 12, paddingBottom: 20 },
  composer: { gap: 10, paddingTop: 12, borderTopWidth: 1 },
  input: {
    minHeight: 100,
    maxHeight: 220,
    borderRadius: 14,
    padding: 14,
    fontSize: 17,
    lineHeight: 24,
    textAlignVertical: 'top',
  },
});
