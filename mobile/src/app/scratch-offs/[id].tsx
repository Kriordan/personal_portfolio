import { useQuery } from '@tanstack/react-query';
import { useLocalSearchParams } from 'expo-router';
import { RefreshControl, StyleSheet, View } from 'react-native';
import {
  LotteryStatusNote,
  OfficialLotteryLink,
} from '@/components/lottery-content';
import {
  Card,
  InlineError,
  PageHeading,
  Screen,
  ScreenState,
  SectionHeading,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import { useLotteryClock } from '@/hooks/use-lottery';
import { useAuth } from '@/lib/auth-context';
import { lotteryApi } from '@/lib/lottery-api';
import { dataIsStale, dollars, prizeTargets } from '@/lib/lottery-model';

export default function ScratchDetail() {
  const params = useLocalSearchParams<{
    id: string;
    state: string;
    target: string;
  }>();
  const { user } = useAuth();
  const state = params.state === 'ct' ? 'ct' : 'ny',
    target = prizeTargets.includes(Number(params.target))
      ? Number(params.target)
      : 1000;
  const now = useLotteryClock();
  const query = useQuery({
    queryKey: ['lottery', 'game', user?.id, state, params.id, target],
    queryFn: () => lotteryApi.game(state, params.id, target),
    enabled: !!user,
    staleTime: 60000,
  });
  if (!query.data)
    return (
      <ScreenState
        loading={query.isPending && !query.isPaused}
        title={
          query.isPending
            ? query.isPaused
              ? 'You’re offline'
              : 'Loading game details'
            : 'Game details unavailable'
        }
        onRetry={() => void query.refetch()}
      />
    );
  const { game, status } = query.data;
  return (
    <Screen
      refreshControl={
        <RefreshControl
          refreshing={query.isRefetching}
          onRefresh={() => void query.refetch()}
        />
      }
    >
      <PageHeading
        eyebrow={`${state.toUpperCase()} · GAME #${game.game_number} · ${dollars(game.price)}`}
        title={game.name}
      />
      {query.isError ? (
        <InlineError
          message="Couldn’t reload. These are the last loaded details."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {dataIsStale(status, now) ? (
        <InlineError message="Dated results: the source or last successful check is over 48 hours old." />
      ) : null}
      <Card>
        <ThemedText type="smallBold" themeColor="accent">
          {dollars(target)}+ GROSS PRIZE
        </ThemedText>
        <ThemedText type="title">
          {game.reason ? 'Unranked' : game.estimated_odds}
        </ThemedText>
        <ThemedText>
          {game.reason ?? 'Estimated chance on one ticket'}
        </ThemedText>
        <ThemedText>Original chance: {game.original_odds}</ThemedText>
        <ThemedText>Chance per $1: {game.dollar_odds}</ThemedText>
        <ThemedText>
          {game.qualifying_remaining?.toLocaleString() ?? 'Unverified'}{' '}
          qualifying prizes unclaimed
        </ThemedText>
        <ThemedText>
          {game.top_remaining?.toLocaleString() ?? 'Unverified'} top{' '}
          {game.top_remaining === 1 ? 'prize' : 'prizes'}
          unclaimed
        </ThemedText>
      </Card>
      <LotteryStatusNote status={status} />
      <SectionHeading>Prize table</SectionHeading>
      {game.tiers.length ? (
        game.tiers.map((tier, index) => (
          <Card key={`${tier.label}-${index}`}>
            <ThemedText type="smallBold">{tier.label}</ThemedText>
            <View style={styles.row}>
              <ThemedText type="small">
                Original: {tier.original.toLocaleString()}
              </ThemedText>
              <ThemedText type="small">
                Unclaimed: {tier.remaining.toLocaleString()}
              </ThemedText>
            </View>
            <ThemedText type="small" themeColor="textSecondary">
              Gross award: {dollars(tier.amount)}
            </ThemedText>
          </Card>
        ))
      ) : (
        <ThemedText themeColor="textSecondary">
          Prize details await verification.
        </ThemedText>
      )}
      <SectionHeading>How the estimate works</SectionHeading>
      <ThemedText>
        We estimate tickets remaining from the share of prizes below $1,000
        still unclaimed. Each qualifying tier’s original probability is
        multiplied by its unclaimed share, then divided by that estimated ticket
        share.
      </ThemedText>
      {game.retention !== undefined ? (
        <ThemedText>
          Estimated ticket share remaining:{' '}
          {Number((game.retention * 100).toPrecision(2))}%.
        </ThemedText>
      ) : null}
      <ThemedText themeColor="textSecondary">
        Claim delays and tickets already sold can skew this model. These are
        estimates, not verified current odds. Prize targets use the advertised
        total award; annuity and cash-option labels are preserved. Stores may
        not stock every game.
      </ThemedText>
      {game.verified_at ? (
        <ThemedText type="small" themeColor="textSecondary">
          Metadata verified: {game.verified_at.slice(0, 10)}
        </ThemedText>
      ) : null}
      <OfficialLotteryLink url={game.url} />
    </Screen>
  );
}
const styles = StyleSheet.create({
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
});
