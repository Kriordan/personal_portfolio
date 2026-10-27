import unittest
from datetime import datetime
from project.lottery.planner import draw_plan

class DrawPlannerTests(unittest.TestCase):
    def plan(self, when, state='ny', **kwargs):
        return draw_plan(state=state, now=datetime.fromisoformat(when), **kwargs)

    def test_monday_week_and_prices(self):
        p = self.plan('2026-10-26T12:00:00-04:00')
        self.assertEqual([g['next_draw']['label'] for g in p['games']], ['Mon, Oct 26', 'Tue, Oct 27'])
        self.assertEqual([[d['label'] for d in g['week']] for g in p['games']], [['Mon, Oct 26', 'Wed, Oct 28', 'Sat, Oct 31'], ['Tue, Oct 27', 'Fri, Oct 30']])
        self.assertEqual(sum(len(g['week']) * g['price'] for g in p['games']), 16)
        self.assertEqual(sum(g['maximum_draws'] * g['price'] for g in p['games']), 208)

    def test_state_cutoffs_and_exact_boundary(self):
        for state, cutoff in [('ny', '22:00:00'), ('ct', '22:45:00')]:
            before = self.plan('2026-10-27T21:59:59-04:00', state)
            after = self.plan(f'2026-10-27T{cutoff}-04:00', state)
            self.assertEqual(before['games'][1]['next_draw']['label'], 'Tue, Oct 27')
            self.assertEqual(after['games'][1]['next_draw']['label'], 'Fri, Oct 30')
            self.assertTrue(after['games'][1]['sales_closed'])
        self.assertEqual(self.plan('2026-10-27T22:30:00-04:00', 'ct')['games'][1]['next_draw']['label'], 'Tue, Oct 27')
        self.assertFalse(self.plan('2026-10-28T00:01:00-04:00')['games'][1]['sales_closed'])

    def test_weekends_dst_year_boundary_and_each_weekday(self):
        for day in range(26, 32):
            p = self.plan(f'2026-10-{day}T18:00:00-04:00')
            for game in p['games']:
                dates = [datetime.fromisoformat(d['date']) for d in game['week']]
                self.assertEqual(len(dates), 3 if game['name'] == 'Powerball' else 2)
                self.assertEqual(dates, sorted(set(dates)))
        p = self.plan('2026-10-31T23:59:00-04:00')
        self.assertTrue(p['games'][0]['next_draw']['date'].endswith('-05:00'))
        self.assertEqual(p['games'][0]['next_draw']['label'], 'Mon, Nov 2')
        self.assertEqual(self.plan('2026-12-31T12:00:00-05:00')['games'][1]['next_draw']['label'], 'Fri, Jan 1')

    def test_never_attach_old_jackpot_to_a_future_draw(self):
        saved = [dict(name='Powerball', jackpot=687000000, cash=300000000, odds=292201338, next_draw='2026-10-27T02:59:00+00:00')]
        self.assertEqual(self.plan('2026-10-26T12:00:00-04:00', summaries=saved, stale=False)['games'][0]['jackpot'], 687000000)
        self.assertIsNone(self.plan('2026-10-26T22:00:00-04:00', summaries=saved, stale=False)['games'][0]['jackpot'])
        self.assertIsNone(self.plan('2026-10-26T12:00:00-04:00', summaries=saved, stale=True)['games'][0]['jackpot'])
