import assert from 'node:assert/strict';
import test from 'node:test';
import { dataIsStale, drawPlanExpired, lotteryDefaults, readLotteryPreferences, scratchQuery } from '../src/lib/lottery-model.ts';

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
