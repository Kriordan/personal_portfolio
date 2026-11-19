import assert from 'node:assert/strict';
import test from 'node:test';
import { dataIsStale, drawPlanExpired, homeDrawsExpired, lotteryDefaults, readLotteryPreferences, scratchQuery } from '../src/lib/lottery-model.ts';
import { createMondayLotteryReminder, mondayLotteryDay } from '../src/lib/lottery-reminder.ts';

test('preferences validate corrupt data and preserve separate empty selections', () => {
  assert.deepEqual(readLotteryPreferences('bad json'), lotteryDefaults);
  assert.deepEqual(readLotteryPreferences('null'), lotteryDefaults);
  const p = readLotteryPreferences(JSON.stringify({ state: 'ct', target: 100000, basis: 'dollar', prices: { ny: [], ct: [10, 50, 50, 999, '20'] } }));
  assert.deepEqual(p.prices, { ny: [], ct: [10, 50] });
  const query = new URLSearchParams(scratchQuery(p, ' Game #1 '));
  assert.deepEqual(query.getAll('price'), ['10', '50']);
  assert.equal(query.get('basis'), 'dollar');
  assert.equal(query.get('q'), 'Game #1');
  assert.equal(new URLSearchParams(scratchQuery({ ...p, state: 'ny' })).get('prices_set'), '1');
  assert.equal(new URLSearchParams(scratchQuery(lotteryDefaults)).has('prices_set'), false);
});

test('saved data becomes stale even without a fresh response', () => {
  const status = { stale: false, source_at: '2026-10-26T12:00:00Z', checked_at: '2026-10-26T13:00:00Z' };
  assert.equal(dataIsStale(status, Date.parse('2026-10-27T12:00:00Z')), false);
  assert.equal(dataIsStale(status, Date.parse('2026-10-28T12:00:01Z')), true);
  assert.equal(dataIsStale({ ...status, checked_at: null }), true);
});

test('today reference expires at Eastern cutoff and midnight regardless of phone zone', () => {
  const plan = { as_of: '2026-10-26T20:00:00-04:00', games: [{ next_draw: { cutoff_at: '2026-10-26T22:00:00-04:00' } }] };
  assert.equal(drawPlanExpired(plan, Date.parse('2026-10-27T01:59:59Z')), false);
  assert.equal(drawPlanExpired(plan, Date.parse('2026-10-27T02:00:00Z')), true);
  const noDrawToday = { ...plan, games: [{ next_draw: { cutoff_at: '2026-10-28T22:00:00-04:00' } }] };
  assert.equal(drawPlanExpired(noDrawToday, Date.parse('2026-10-27T04:00:00Z')), true);
});

test('compact Home reference lasts until the drawing, including after sales close', () => {
  const home = { upcoming: { date: '2026-11-23T22:59:00-05:00' }, latest: { date: '2026-11-21T22:59:00-05:00' } };
  assert.equal(homeDrawsExpired(home, Date.parse('2026-11-23T22:30:00-05:00')), false);
  assert.equal(homeDrawsExpired(home, Date.parse('2026-11-23T22:59:00-05:00')), true);
  assert.equal(homeDrawsExpired(home, Date.parse('2026-11-20T23:00:00-05:00')), true);
  assert.equal(homeDrawsExpired({ ...home, upcoming: { date: 'invalid' } }), true);
});

test('weekly reminder uses Monday in Eastern time and stops at the purchase cutoff', () => {
  for (const [when, expected] of [
    ['2026-11-23T04:59:59Z', null],
    ['2026-11-23T05:00:00Z', '2026-11-23'],
    ['2026-11-24T02:59:59Z', '2026-11-23'],
    ['2026-11-24T03:00:00Z', null],
    ['2026-11-24T05:00:00Z', null],
    ['2026-10-26T04:00:00Z', '2026-10-26'],
    ['2026-11-02T05:00:00Z', '2026-11-02'],
  ]) assert.equal(mondayLotteryDay(Date.parse(when)), expected, when);
});

function reminderStorage() {
  const values = new Map();
  return {
    get: async (key) => values.get(key) ?? null,
    set: async (key, value) => { values.set(key, value); },
  };
}
const monday = () => Date.parse('2026-11-23T12:00:00-05:00');

test('reminder appears once per account and Monday, including after app restart', async () => {
  const store = reminderStorage();
  let reminder = createMondayLotteryReminder(store);
  assert.equal(await reminder.claim(1, () => true, monday), true);
  assert.equal(await reminder.claim(1, () => true, monday), false);
  reminder = createMondayLotteryReminder(store);
  assert.equal(await reminder.claim(1, () => true, monday), false);
  assert.equal(await reminder.claim(2, () => true, monday), true);
  assert.equal(await reminder.claim(1, () => true, () => Date.parse('2026-11-30T12:00:00-05:00')), true);
});

test('concurrent reminder checks cannot show duplicate popups', async () => {
  const reminder = createMondayLotteryReminder(reminderStorage());
  const results = await Promise.all([
    reminder.claim(1, () => true, monday),
    reminder.claim(1, () => true, monday),
  ]);
  assert.deepEqual(results, [true, false]);
});

test('a reminder storage read finishing after logout or navigation does not consume the reminder', async () => {
  let release;
  let active = true;
  let writes = 0;
  const reminder = createMondayLotteryReminder({
    get: () => new Promise((resolve) => { release = resolve; }),
    set: async () => { writes++; },
  });
  const first = reminder.claim(1, () => active, monday);
  active = false;
  release(null);
  assert.equal(await first, false);
  assert.equal(writes, 0);
  active = true;
  const second = reminder.claim(1, () => active, monday);
  release(null);
  assert.equal(await second, true);
});

test('a delayed check past the Monday cutoff never shows obsolete weekly instructions', async () => {
  let release;
  let now = Date.parse('2026-11-23T21:59:59-05:00');
  const reminder = createMondayLotteryReminder({
    get: () => new Promise((resolve) => { release = resolve; }),
    set: async () => { assert.fail('Should not record an undisplayed reminder'); },
  });
  const check = reminder.claim(1, () => true, () => now);
  now += 1000;
  release(null);
  assert.equal(await check, false);
});

test('unavailable device storage still allows one reminder in the current app session', async () => {
  const reminder = createMondayLotteryReminder({
    get: async () => { throw new Error('Storage unavailable'); },
    set: async () => { throw new Error('Storage unavailable'); },
  });
  assert.equal(await reminder.claim(1, () => true, monday), true);
  assert.equal(await reminder.claim(1, () => true, monday), false);
});
