import { Host } from '@expo/ui';
import { useRouter } from 'expo-router';
import { memo, useCallback, useDeferredValue, useMemo, useState } from 'react';
import {
  FlatList,
  Pressable,
  RefreshControl,
  StyleSheet,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  LotteryChoice,
  LotteryStates,
  LotteryStatusNote,
} from '@/components/lottery-content';
import { JobBrowseChoice as BrowseChoice } from '@/components/job-browse-choice';
import { JobToolbarIcon as ToolbarIcon } from '@/components/job-toolbar-icon';
import { NativeField } from '@/components/native-form';
import {
  InlineError,
  NativeAction,
  PageHeading,
  ScreenState,
  SectionHeading,
  screenStyles,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import {
  useLotteryClock,
  useLotteryPreferences,
  useScratchOffs,
} from '@/hooks/use-lottery';
import { useNativeText } from '@/hooks/use-native-text';
import { useTheme } from '@/hooks/use-theme';
import {
  dataIsStale,
  dollars,
  prizeTargets,
  type ScratchGame,
} from '@/lib/lottery-model';

const ScratchRow = memo(function ScratchRow({
  game,
  state,
  target,
  position,
  basis,
}: {
  game: ScratchGame;
  state: string;
  target: number;
  position?: number;
  basis: string;
}) {
  const theme = useTheme(),
    router = useRouter();
  return (
    <Pressable
      accessibilityRole="link"
      accessibilityLabel={`${position ? `Choice ${position}. ` : ''}${game.name}, game ${game.game_number}, ${dollars(game.price)}. ${game.reason ?? `Estimated odds ${game.estimated_odds}`}`}
      onPress={() =>
        router.push({
          pathname: '/scratch-offs/[id]',
          params: { id: game.game_number, state, target },
        })
      }
      style={({ pressed }) => [
        styles.row,
        {
          backgroundColor: pressed
            ? theme.backgroundSelected
            : theme.backgroundElement,
          borderColor: position ? theme.accentSoft : theme.border,
        },
      ]}
    >
      <View style={styles.rowTop}>
        <ThemedText type="smallBold" themeColor="accent">
          {position ? `CHOICE ${position} · ` : ''}#{game.game_number}
        </ThemedText>
        <ThemedText type="smallBold">{dollars(game.price)}</ThemedText>
      </View>
      <ThemedText type="subtitle">{game.name}</ThemedText>
      {game.reason ? (
        <ThemedText type="small" themeColor="textSecondary">
          {game.reason}
        </ThemedText>
      ) : (
        <>
          <ThemedText themeColor="accent">
            {game.estimated_odds} estimated · {dollars(target)}+
          </ThemedText>
          <ThemedText type="small" themeColor="textSecondary">
            Original: {game.original_odds}
            {basis === 'dollar' ? ` · Per $1: ${game.dollar_odds}` : ''}
          </ThemedText>
          <ThemedText type="small">
            {game.qualifying_remaining?.toLocaleString() ?? 'Unverified'}{' '}
            qualifying {game.qualifying_remaining === 1 ? 'prize' : 'prizes'} ·{' '}
            {game.top_remaining?.toLocaleString() ?? 'Unverified'} top{' '}
            {game.top_remaining === 1 ? 'prize' : 'prizes'}
            unclaimed
          </ThemedText>
        </>
      )}
      <ThemedText type="small" themeColor="textSecondary">
        {game.source_date ?? 'Source date unavailable'} · Details ›
      </ThemedText>
    </Pressable>
  );
});
const keyForGame = (game: ScratchGame) => game.game_number;
const targetOptions = prizeTargets.map((value) => ({
  value: String(value),
  label: `${dollars(value)}+`,
}));
const sortOptions = [
  { value: 'ticket', label: 'Per ticket' },
  { value: 'dollar', label: 'Per dollar' },
] as const;
export default function ScratchOffsScreen() {
  const theme = useTheme(),
    prefs = useLotteryPreferences(),
    search = useNativeText();
  const deferredSearch = useDeferredValue(search.text);
  const query = useScratchOffs(prefs.preferences, prefs.ready, deferredSearch);
  const [showSearch, setShowSearch] = useState(false),
    [showPending, setShowPending] = useState(false);
  const now = useLotteryClock();
  const data = query.data;
  const games = useMemo(
    () => [
      ...(data?.games ?? []),
      ...(showPending ? (data?.pending ?? []) : []),
    ],
    [data, showPending],
  );
  const renderGame = useCallback(
    ({ item }: { item: ScratchGame }) => (
      <ScratchRow
        game={item}
        state={prefs.preferences.state}
        target={prefs.preferences.target}
        basis={prefs.preferences.basis}
        position={
          data?.picks.includes(item.game_number)
            ? data.picks.indexOf(item.game_number) + 1
            : undefined
        }
      />
    ),
    [prefs.preferences, data],
  );
  if (!prefs.ready)
    return (
      <ScreenState
        loading={!prefs.accountError}
        title={
          prefs.accountError
            ? 'Couldn’t load your account'
            : 'Loading your preferences'
        }
        onRetry={prefs.accountError ? prefs.retryAccount : undefined}
      />
    );
  return (
    <SafeAreaView
      edges={['left', 'right', 'bottom']}
      style={[styles.fill, { backgroundColor: theme.background }]}
    >
      <FlatList
        data={games}
        keyExtractor={keyForGame}
        renderItem={renderGame}
        contentContainerStyle={screenStyles.collection}
        contentInsetAdjustmentBehavior="automatic"
        keyboardShouldPersistTaps="handled"
        automaticallyAdjustKeyboardInsets
        refreshControl={
          <RefreshControl
            refreshing={query.isRefetching}
            onRefresh={() => void query.refetch()}
          />
        }
        ListHeaderComponent={
          <View style={screenStyles.gap}>
            <View style={styles.headingRow}>
              <View style={styles.headingTitle}>
                <PageHeading title="Scratch-offs" />
              </View>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={
                  showSearch
                    ? 'Close game search'
                    : 'Search game name or number'
                }
                accessibilityState={{ expanded: showSearch }}
                onPress={() => {
                  setShowSearch(!showSearch);
                  if (showSearch) search.clear();
                }}
                style={styles.searchButton}
              >
                <ToolbarIcon name="search" />
              </Pressable>
            </View>
            <LotteryStates
              state={prefs.preferences.state}
              onChange={(state) => prefs.set({ state })}
            />
            <View style={styles.choices}>
              {(data?.available ?? []).map((price) => (
                <LotteryChoice
                  key={price}
                  label={dollars(price)}
                  checkbox
                  selected={data?.prices.includes(price) ?? false}
                  onPress={() => {
                    const selected = data?.prices ?? [];
                    prefs.set({
                      prices: {
                        ...prefs.preferences.prices,
                        [prefs.preferences.state]: selected.includes(price)
                          ? selected.filter((p) => p !== price)
                          : [...selected, price],
                      },
                    });
                  }}
                />
              ))}
            </View>
            <View style={styles.filters}>
              <View style={styles.filter}>
                <BrowseChoice
                  icon="filter"
                  label="Prize target"
                  value={String(prefs.preferences.target)}
                  options={targetOptions}
                  onChange={(value) => prefs.set({ target: Number(value) })}
                />
              </View>
              <View style={styles.filter}>
                <BrowseChoice
                  icon="sort"
                  label="Compare by"
                  value={prefs.preferences.basis}
                  options={sortOptions}
                  onChange={(basis) => prefs.set({ basis })}
                />
              </View>
            </View>
            {showSearch ? (
              <Host matchContents={{ vertical: true }}>
                <NativeField
                  label="Find a game"
                  {...search.input}
                  placeholder="Name or game number"
                />
              </Host>
            ) : null}
            {prefs.saveError ? (
              <InlineError message="Your selections work for this session, but couldn’t be saved on this device." />
            ) : null}
            {query.isError ? (
              <InlineError
                message="Couldn’t reload saved lottery data."
                onRetry={() => void query.refetch()}
              />
            ) : null}
            {data ? (
              <>
                <LotteryStatusNote status={data.status} compact />
                <SectionHeading>
                  {dataIsStale(data.status, now)
                    ? 'Dated comparisons'
                    : 'Top choices'}
                </SectionHeading>
                <ThemedText type="small" themeColor="textSecondary">
                  {dataIsStale(data.status, now)
                    ? 'Data is over 48 hours old or unavailable. Check the source before relying on these results. '
                    : ''}
                  Model estimates. Unclaimed prizes may already be sold.
                </ThemedText>
                <ThemedText type="smallBold" themeColor="textSecondary">
                  {data.games.length}{' '}
                  {data.games.length === 1 ? 'game' : 'games'} ·{' '}
                  {data.picks.length
                    ? 'Top three marked below'
                    : 'No qualifying choices'}
                </ThemedText>
              </>
            ) : null}
          </View>
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <ThemedText>
              {query.isPending
                ? query.isPaused
                  ? 'Reconnect to load saved games.'
                  : 'Loading saved games…'
                : 'No matching games. Try another price, target, or search.'}
            </ThemedText>
          </View>
        }
        ListFooterComponent={
          data?.pending.length ? (
            <View style={styles.empty}>
              <NativeAction
                secondary
                label={
                  showPending
                    ? 'Hide games awaiting details'
                    : `${data.pending.length} games awaiting verified details`
                }
                onPress={() => setShowPending(!showPending)}
              />
              <ThemedText type="small" themeColor="textSecondary">
                New or incomplete NY games stay out of the rankings until their
                metadata is verified.
              </ThemedText>
            </View>
          ) : null
        }
      />
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  fill: { flex: 1 },
  row: {
    borderRadius: 20,
    borderCurve: 'continuous',
    padding: 18,
    gap: 7,
    borderWidth: 1,
    marginTop: 12,
  },
  rowTop: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  choices: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  filters: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  filter: { flex: 1, minWidth: 140 },
  headingRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headingTitle: { flex: 1 },
  searchButton: {
    minWidth: 44,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  empty: { paddingVertical: 24, gap: 12 },
});
