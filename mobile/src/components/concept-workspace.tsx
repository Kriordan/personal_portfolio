import { useLocalSearchParams, useRouter } from 'expo-router';
import { Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';
import { InlineError, NativeAction, PageHeading } from './screen';
import { ThemedText } from './themed-text';
import { useTheme } from '@/hooks/use-theme';
import type { useConceptStudy } from '@/hooks/use-concepts';
import type { Concept } from '@/lib/concept-model';

export function ConceptHeader({
  concept,
  mode,
  compact = false,
}: {
  concept: Concept;
  mode: 'learn' | 'review' | 'discuss' | 'build';
  compact?: boolean;
}) {
  const router = useRouter();
  const { practice_session, work } = useLocalSearchParams<{
    practice_session?: string;
    work?: string;
  }>();
  const theme = useTheme();
  const { fontScale } = useWindowDimensions();
  return (
    <>
      {compact ? (
        <ThemedText type="smallBold" accessibilityRole="header">
          {concept.title}
        </ThemedText>
      ) : (
        <PageHeading title={concept.title} eyebrow="ENGINEERING PRACTICE" />
      )}
      {concept.private_pilot_draft || concept.local_draft ? (
        <ThemedText type="small" themeColor="textSecondary">
          Private Learning pilot · Draft content
        </ThemedText>
      ) : null}
      <View key={fontScale} accessibilityRole="tablist" style={styles.tabs}>
        {(['learn', 'review', 'discuss', 'build'] as const).map((view) => (
          <Pressable
            key={view}
            accessibilityRole="tab"
            accessibilityState={{ selected: mode === view }}
            accessibilityLabel={
              view === 'learn'
                ? 'Learn'
                : view === 'review'
                  ? 'Review'
                  : view === 'discuss'
                    ? 'Discuss'
                    : 'Build'
            }
            onPress={() => {
              if (view !== mode)
                router.replace({
                  pathname:
                    view === 'learn'
                      ? '/learning/concepts/[id]'
                      : view === 'review'
                        ? '/learning/concepts/[id]/review'
                        : view === 'discuss'
                          ? '/learning/concepts/[id]/discuss'
                          : '/learning/concepts/[id]/build',
                  params: {
                    id: concept.id,
                    ...(practice_session ? { practice_session } : {}),
                    ...(work ? { work } : {}),
                  },
                });
            }}
            style={[
              styles.tab,
              {
                backgroundColor:
                  mode === view ? theme.accentSoft : theme.backgroundElement,
              },
            ]}
          >
            <ThemedText
              type="smallBold"
              themeColor={mode === view ? 'accent' : 'textSecondary'}
            >
              {view === 'learn'
                ? 'Learn'
                : view === 'review'
                  ? 'Review'
                  : view === 'discuss'
                    ? 'Discuss'
                    : 'Build'}
            </ThemedText>
          </Pressable>
        ))}
      </View>
    </>
  );
}
export function StudyStatus({
  activity,
  onReload,
}: {
  activity: ReturnType<typeof useConceptStudy>;
  onReload: () => void;
}) {
  if (!activity.ready)
    return (
      <InlineError
        message={activity.error ?? 'Loading your saved place…'}
        onRetry={
          activity.error ? () => void activity.study.restore() : undefined
        }
      />
    );
  if (!activity.pending)
    return activity.error ? <InlineError message={activity.error} /> : null;
  const busy = activity.phase === 'saving' || activity.phase === 'checking';
  return (
    <View style={styles.status}>
      <ThemedText accessibilityLiveRegion="polite" type="smallBold">
        {busy ? 'Confirming your save…' : 'Saved place needs attention'}
      </ThemedText>
      {activity.error ? (
        <ThemedText themeColor="textSecondary">{activity.error}</ThemedText>
      ) : null}
      {activity.phase === 'conflict' ? (
        <NativeAction
          label="Reload saved place"
          secondary
          onPress={() => {
            void activity.study.dismissConflict().then((cleared) => {
              if (cleared) onReload();
            });
          }}
        />
      ) : (
        <>
          <NativeAction
            label="Check save"
            secondary
            disabled={busy}
            onPress={() => void activity.study.check()}
          />
          <NativeAction
            label="Retry the same save"
            secondary
            disabled={busy}
            onPress={() => void activity.study.retry()}
          />
        </>
      )}
    </View>
  );
}
const styles = StyleSheet.create({
  tabs: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tab: {
    // Let native text measurement choose each tab's width before wrapping.
    // A numeric basis can keep scaled labels trapped in narrow columns.
    flexGrow: 1,
    flexShrink: 0,
    minWidth: 68,
    minHeight: 48,
    paddingVertical: 12,
    paddingHorizontal: 6,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  status: { gap: 8 },
});
