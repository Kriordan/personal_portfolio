import { memo, useState } from 'react';
import { useRouter } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import {
  Card,
  NativeAction,
  Screen,
  PageHeading,
  ScreenState,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { Fonts } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { useAuth } from '@/lib/auth-context';
import type { NoteSummary, ReviewCard } from '@/lib/learning-model';

const typeLabels: Record<string, string> = {
  qa: 'Question and answer',
  cloze: 'Fill in the blank',
  command: 'Command',
  code_diff: 'Code change',
  incident: 'Incident',
};
export const cardTypeLabel = (type: string) =>
  typeLabels[type] ?? 'Question and answer';
const noteKey = (note: NoteSummary) => note.id;
export { noteKey };

export function LearningAccountState() {
  const { userError, retryUser } = useAuth();
  return (
    <ScreenState
      loading={!userError}
      title={userError ? 'Couldn’t load your account' : 'Loading your account'}
      message="Connect to load your personal review progress."
      onRetry={userError ? retryUser : undefined}
    />
  );
}

export const LearningNoteRow = memo(function LearningNoteRow({
  note,
}: {
  note: NoteSummary;
}) {
  const theme = useTheme();
  const router = useRouter();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${note.title}. ${note.flashcard_count} cards, ${note.due_count} due.`}
      onPress={() =>
        router.push({ pathname: '/learning/[id]', params: { id: note.id } })
      }
      style={({ pressed }) => [
        styles.note,
        {
          backgroundColor: pressed
            ? theme.backgroundSelected
            : theme.backgroundElement,
        },
      ]}
    >
      <View style={styles.body}>
        <ThemedText style={styles.noteTitle}>{note.title}</ThemedText>
        {note.summary ? (
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>
            {note.summary
              .replace(/^#{1,6}\s+.*\n+/gm, '')
              .replace(/[*`]/g, '')
              .trim()}
          </ThemedText>
        ) : null}
        <ThemedText
          type="smallBold"
          themeColor={note.due_count ? 'accent' : 'textSecondary'}
        >
          {note.flashcard_count} cards · {note.due_count} due
        </ThemedText>
        {note.tags?.length ? (
          <ThemedText type="small" themeColor="textSecondary" numberOfLines={2}>
            {note.tags.join(' · ')}
          </ThemedText>
        ) : null}
      </View>
      <ThemedText accessible={false} themeColor="textSecondary">
        ›
      </ThemedText>
    </Pressable>
  );
});

/** Text-only formatting. Never interprets HTML or fetches embedded media. */
export function LearningText({
  text,
  code = false,
}: {
  text: string;
  code?: boolean;
}) {
  const theme = useTheme();
  if (code)
    return (
      <ScrollView
        horizontal
        nestedScrollEnabled
        style={[styles.code, { backgroundColor: theme.backgroundSelected }]}
      >
        <ThemedText selectable style={styles.codeText}>
          {text}
        </ThemedText>
      </ScrollView>
    );
  return (
    <View style={styles.textBlocks}>
      {text
        .split(/(```[\s\S]*?```)/g)
        .filter(Boolean)
        .map((block, i) => {
          if (block.startsWith('```') && block.endsWith('```'))
            return (
              <LearningText
                key={i}
                code
                text={block
                  .slice(3, -3)
                  .replace(/^[^\n]*\n/, '')
                  .trimEnd()}
              />
            );
          return (
            <ThemedText key={i} selectable>
              {block
                .replace(/^#{1,6}\s+(.+)$/gm, '**$1**')
                .split(/(`[^`\n]+`|\*\*[^*\n]+\*\*)/g)
                .map((part, index) =>
                  part.startsWith('`') && part.endsWith('`') ? (
                    <Text key={index} style={styles.inlineCode}>
                      {part.slice(1, -1)}
                    </Text>
                  ) : part.startsWith('**') && part.endsWith('**') ? (
                    <Text key={index} style={styles.noteTitle}>
                      {part.slice(2, -2)}
                    </Text>
                  ) : (
                    part
                  ),
                )}
            </ThemedText>
          );
        })}
    </View>
  );
}

export function LearningAnswer({ card }: { card: ReviewCard }) {
  return card.response_sections?.length ? (
    <View style={styles.textBlocks}>
      {card.response_sections.map((section, i) => (
        <View key={i} style={styles.textBlocks}>
          <ThemedText type="smallBold">{section.label}</ThemedText>
          <LearningText text={section.text} code={section.code} />
        </View>
      ))}
    </View>
  ) : (
    <LearningText text={card.response} />
  );
}

export const StudyCard = memo(function StudyCard({
  card,
}: {
  card: ReviewCard;
}) {
  const [revealed, setRevealed] = useState(false);
  const theme = useTheme();
  return (
    <View style={styles.cardGap}>
      <Card>
        <ThemedText type="smallBold" themeColor="textSecondary">
          {cardTypeLabel(card.type)}
        </ThemedText>
        <LearningText text={card.prompt} />
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ expanded: revealed }}
          accessibilityLabel={revealed ? 'Hide answer' : 'Show answer'}
          onPress={() => setRevealed((value) => !value)}
          style={[styles.reveal, { backgroundColor: theme.accentSoft }]}
        >
          <ThemedText themeColor="accent">
            {revealed ? 'Hide answer' : 'Show answer'}
          </ThemedText>
        </Pressable>
        {revealed ? <LearningAnswer card={card} /> : null}
      </Card>
    </View>
  );
});
export function LearningUnavailable({
  title = 'Note unavailable',
  message = 'This note may have moved or been removed.',
}: {
  title?: string;
  message?: string;
}) {
  const router = useRouter();
  return (
    <Screen>
      <PageHeading title={title} subtitle={message} />
      <NativeAction
        label="Back to Learning"
        onPress={() => router.replace('/learning')}
      />
    </Screen>
  );
}
export const learningStyles = StyleSheet.create({
  fill: { flex: 1 },
  empty: { gap: 12, paddingVertical: 24 },
  count: { paddingVertical: 12 },
});
const styles = StyleSheet.create({
  note: {
    padding: 18,
    borderRadius: 20,
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
    marginBottom: 12,
  },
  body: { flex: 1, gap: 6 },
  noteTitle: { fontWeight: '600' },
  cardGap: { marginBottom: 16 },
  reveal: {
    minHeight: 44,
    borderRadius: 12,
    padding: 12,
    alignItems: 'flex-start',
  },
  code: { borderRadius: 10 },
  codeText: {
    fontFamily: Fonts.mono,
    fontSize: 15,
    lineHeight: 23,
    padding: 12,
  },
  inlineCode: { fontFamily: Fonts.mono },
  textBlocks: { gap: 12 },
});
