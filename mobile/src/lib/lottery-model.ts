export type LotteryState = 'ny' | 'ct';
export type LotteryBasis = 'ticket' | 'dollar';
export interface LotteryPreferences {
  state: LotteryState;
  target: number;
  basis: LotteryBasis;
  prices: Record<LotteryState, number[] | null>;
}
export const lotteryDefaults: LotteryPreferences = {
  state: 'ny',
  target: 1000,
  basis: 'ticket',
  prices: { ny: null, ct: null },
};
export const prizeTargets = [500, 1000, 10000, 100000, 1000000];
const currency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});
export const dollars = (value: number | null) =>
  value === null ? 'Unverified' : currency.format(value);
const compactCurrency = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});
export const jackpotLabel = (value: number | null) =>
  value === null
    ? 'Awaiting updated jackpot'
    : `${compactCurrency.format(value / 1000000)}M est. jackpot`;
export function readLotteryPreferences(raw: string | null): LotteryPreferences {
  try {
    const value = JSON.parse(raw ?? '{}');
    const prices = (state: LotteryState) =>
      Array.isArray(value?.prices?.[state])
        ? [
            ...new Set<number>(
              value.prices[state].filter((p: number) =>
                [10, 20, 30, 50].includes(p),
              ),
            ),
          ]
        : null;
    return {
      state: value?.state === 'ct' ? 'ct' : 'ny',
      target: prizeTargets.includes(value?.target) ? value.target : 1000,
      basis: value?.basis === 'dollar' ? 'dollar' : 'ticket',
      prices: { ny: prices('ny'), ct: prices('ct') },
    };
  } catch {
    return lotteryDefaults;
  }
}
export function scratchQuery(preferences: LotteryPreferences, search = '') {
  const params = new URLSearchParams({
    state: preferences.state,
    target: String(preferences.target),
    basis: preferences.basis,
  });
  const prices = preferences.prices[preferences.state];
  if (prices !== null) {
    params.set('prices_set', '1');
    prices.forEach((price) => params.append('price', String(price)));
  }
  if (search.trim()) params.set('q', search.trim().slice(0, 100));
  return params.toString();
}
export interface LotteryStatus {
  stale: boolean;
  source_date: string | null;
  source_at: string | null;
  checked_at: string | null;
  checked: string;
  failure: string | null;
  interrupted: boolean;
  scheduled_status: string;
  scheduled_at: string | null;
}
export function dataIsStale(status: LotteryStatus, now = Date.now()) {
  return (
    status.stale ||
    [status.source_at, status.checked_at].some(
      (value) =>
        !value ||
        !Number.isFinite(Date.parse(value)) ||
        now - Date.parse(value) > 48 * 3600000,
    )
  );
}
export interface PrizeTier {
  label: string;
  amount: number | null;
  original: number;
  remaining: number;
  launch_probability: number;
}
export interface ScratchGame {
  game_number: string;
  name: string;
  price: number | null;
  status: string;
  url: string;
  tiers: PrizeTier[];
  reason: string | null;
  estimated_odds: string;
  original_odds: string;
  dollar_odds: string;
  qualifying_remaining: number | null;
  top_remaining: number | null;
  source_date: string | null;
  retention?: number;
  verified_at?: string;
  start_date?: string;
  end_date?: string;
}
export interface ScratchResponse {
  state: LotteryState;
  target: number;
  basis: LotteryBasis;
  prices: number[];
  available: number[];
  games: ScratchGame[];
  picks: string[];
  pending: ScratchGame[];
  status: LotteryStatus;
}
export interface DrawDate {
  date: string;
  label: string;
  cutoff_at: string;
}
export interface DrawGame {
  name: string;
  price: number;
  maximum_draws: number;
  cutoff: string;
  sales_closed: boolean;
  next_draw: DrawDate;
  week: DrawDate[];
  jackpot: number | null;
  cash: number | null;
  odds: number | null;
  saved_draw: string | null;
  url: string;
}
export interface DrawResponse {
  status: LotteryStatus;
  plan: {
    state: LotteryState;
    as_of: string;
    date_label: string;
    games: DrawGame[];
    weekly_cost: number;
    maximum_cost: number;
    rules_verified: string;
    next_draw_stops: { day: string; tickets: string }[];
  };
}
export function drawPlanExpired(plan: DrawResponse['plan'], now = Date.now()) {
  const easternDate = (date: Date) =>
    date.toLocaleDateString('en-US', { timeZone: 'America/New_York' });
  return (
    easternDate(new Date(plan.as_of)) !== easternDate(new Date(now)) ||
    plan.games.some((game) => now >= Date.parse(game.next_draw.cutoff_at))
  );
}
