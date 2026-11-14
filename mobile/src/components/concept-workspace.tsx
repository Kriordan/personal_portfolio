import { useLocalSearchParams, useRouter } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';
import { InlineError, NativeAction, PageHeading } from './screen';
import { ThemedText } from './themed-text';
import { useTheme } from '@/hooks/use-theme';
import type { useConceptStudy } from '@/hooks/use-concepts';
import type { Concept } from '@/lib/concept-model';

export function ConceptHeader({
  concept,
  mode,
}: {
  concept: Concept;
  mode: 'learn' | 'review' | 'discuss';
}) {
  const router = useRouter();
  const { practice_session } = useLocalSearchParams<{ practice_session?: string }>();
  const theme = useTheme();
  return (
    <>
      <PageHeading title={concept.title} eyebrow="ENGINEERING PRACTICE" />
      {concept.private_pilot_draft || concept.local_draft ? (
        <ThemedText type="small" themeColor="textSecondary">
          Private Learning pilot · Draft content
        </ThemedText>
      ) : null}
      <View accessibilityRole="tablist" style={styles.tabs}>
        {(['learn', 'review', 'discuss'] as const).map((view) => (
          <Pressable
            key={view}
            accessibilityRole="tab"
            accessibilityState={{ selected: mode === view }}
            accessibilityLabel={view === 'learn' ? 'Learn' : view === 'review' ? 'Review' : 'Discuss'}
            onPress={() => {
              if (view !== mode)
                router.replace({
                  pathname:
                    view === 'learn'
                      ? '/learning/concepts/[id]'
                      : view === 'review' ? '/learning/concepts/[id]/review' : '/learning/concepts/[id]/discuss',
                  params: { id: concept.id, ...(practice_session ? { practice_session } : {}) },
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
              {view === 'learn' ? 'Learn' : view === 'review' ? 'Review' : 'Discuss'}
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
  tabs: { flexDirection: 'row', gap: 8 },
  tab: {
    flex: 1,
    minHeight: 48,
    padding: 12,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  status: { gap: 8 },
});
