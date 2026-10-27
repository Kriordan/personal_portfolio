import { RefreshControl, View } from 'react-native';
import {
  LotteryStates,
  LotteryStatusNote,
  OfficialLotteryLink,
} from '@/components/lottery-content';
import {
  Card,
  InlineError,
  PageHeading,
  Screen,
  SectionHeading,
} from '@/components/screen';
import { ThemedText } from '@/components/themed-text';
import {
  useLotteryClock,
  useLotteryDraws,
  useLotteryPreferences,
} from '@/hooks/use-lottery';
import {
  dataIsStale,
  dollars,
  drawPlanExpired,
  jackpotLabel,
} from '@/lib/lottery-model';

export default function DrawGamesScreen() {
  const prefs = useLotteryPreferences(),
    now = useLotteryClock();
  const query = useLotteryDraws(prefs.preferences.state, prefs.ready);
  const data = query.data,
    expired = data ? drawPlanExpired(data.plan, now) : true;
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
        eyebrow="POWERBALL + MEGA MILLIONS"
        title="Fewer stops. Every draw."
        subtitle="One play for each drawing, with a routine that fits your week."
      />
      <LotteryStates
        state={prefs.preferences.state}
        onChange={(state) => prefs.set({ state })}
      />
      <Card>
        <ThemedText type="subtitle" accessibilityRole="header">
          One stop a week · $16
        </ThemedText>
        <ThemedText>
          On Monday before 10 p.m. Eastern, ask for one Powerball play for 3
          consecutive draws and one Mega Millions play for 2 consecutive draws.
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          Covers Powerball Monday, Wednesday and Saturday; Mega Millions Tuesday
          and Friday. $6 + $10, without optional Powerball add-ons. A Sunday
          stop works too.
        </ThemedText>
      </Card>
      <SectionHeading>Buying only the next drawing?</SectionHeading>
      <Card>
        <ThemedText>Three stops per week is the minimum:</ThemedText>
        <ThemedText>
          Monday · Powerball for Monday + Mega Millions for Tuesday
        </ThemedText>
        <ThemedText>Wednesday · Powerball for Wednesday</ThemedText>
        <ThemedText>
          Friday · Mega Millions for Friday + Powerball for Saturday
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          Go before 10 p.m. Eastern on each day. This lets you decide again as
          jackpots change. All five plays still total $16.
        </ThemedText>
      </Card>
      <SectionHeading>If you’re stopping today</SectionHeading>
      <ThemedText type="small" themeColor="textSecondary">
        Choose the next drawing only, or the rolling week below. This reference
        does not track purchases: skip any drawings already on your tickets.
      </ThemedText>
      {data && !expired ? (
        data.plan.games.map((game) => (
          <Card key={game.name}>
            <ThemedText type="subtitle">{game.name}</ThemedText>
            <ThemedText>
              {game.next_draw.label} · {dollars(game.price)} per play
            </ThemedText>
            <ThemedText themeColor="accent">
              {dataIsStale(data.status, now)
                ? 'Jackpot needs an update'
                : jackpotLabel(game.jackpot)}
            </ThemedText>
            {game.cash !== null && !dataIsStale(data.status, now) ? (
              <ThemedText type="small">
                Cash option: {dollars(game.cash)}
              </ThemedText>
            ) : null}
            <ThemedText type="small">
              {game.sales_closed
                ? 'Sales for tonight are closed. Confirm when future-draw sales reopen.'
                : `Draw-day sales close at ${game.cutoff}.`}
            </ThemedText>
            <ThemedText type="smallBold">
              A rolling week: {game.week.length} consecutive draws ·{' '}
              {dollars(game.week.length * game.price)}
            </ThemedText>
            <ThemedText type="small">
              {game.week.map((draw) => draw.label).join(' · ')}
            </ThemedText>
            {game.odds ? (
              <ThemedText type="small" themeColor="textSecondary">
                Published jackpot odds: 1 in {game.odds.toLocaleString()}
              </ThemedText>
            ) : null}
            <OfficialLotteryLink url={game.url} />
          </Card>
        ))
      ) : (
        <ThemedText themeColor="textSecondary">
          {query.isPending
            ? 'Loading saved drawings…'
            : 'Reload to update today’s dates and jackpots. Use the weekly reference above in the meantime.'}
        </ThemedText>
      )}
      {query.isError ? (
        <InlineError
          message="Couldn’t reload saved drawing details."
          onRetry={() => void query.refetch()}
        />
      ) : null}
      {prefs.saveError ? (
        <InlineError message="Couldn’t save your state selection on this device." />
      ) : null}
      {data ? <LotteryStatusNote status={data.status} /> : null}
      <SectionHeading>The fewest trips overall</SectionHeading>
      <Card>
        <ThemedText>
          Both states allow up to 39 consecutive Powerball draws and 26 Mega
          Millions draws: about 13 weeks from one stop, for $208 at base prices.
        </ThemedText>
        <ThemedText type="small" themeColor="textSecondary">
          Advance play includes the next drawing and keeps playing even if a
          jackpot is won and resets. The weekly option commits less money ahead
          of time. Ask the retailer to confirm your start and end dates.
        </ThemedText>
      </Card>
      <View>
        <ThemedText type="small" themeColor="textSecondary">
          Schedule and advance-draw rules checked October 26, 2026. All times
          are Eastern. Jackpots are saved daily and can change between checks;
          amounts shown apply only to their listed drawing.
        </ThemedText>
      </View>
    </Screen>
  );
}
