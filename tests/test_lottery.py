import copy
import json
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import requests
from flask import g

from project import create_app
from project.database import db
from project.models import User
from project.lottery.calculations import calculate, is_stale, money, odds, rank
from project.lottery.metadata import validate_metadata
from project.lottery.models import LotteryGameMetadata, LotteryRefreshRun, LotterySnapshot
from project.lottery.service import LOCK_NAMESPACE, import_metadata, latest_snapshot, refresh
from project.lottery.views import source_stamp
from project.lottery.sources import CT_CATALOG, NY_COUNT, NY_FEED, NY_INFO, PublicClient, SourceError, ct_catalog, ct_game, draw_game, flight_values, ny_games
from project.jobwizard.capture_lock import capture_lock

FIXTURES = Path(__file__).parent / "fixtures" / "lottery"
SEED = Path(__file__).parents[1] / "project" / "lottery" / "data" / "ny_metadata.json"


def fixture(name):
    return (FIXTURES / name).read_text()


def example(number="1", price=20):
    # 1,000 launch tickets; low prizes half unclaimed; 8 of 10 $1k prizes remain.
    # $1k+ = (.01 * .8 + .001 * 1) / .5 = .018, original .011.
    return dict(game_number=number, name="Example", price=price, status="active", tiers=[
        dict(label="$100,000", amount=100000, original=1, remaining=1, launch_probability=.001),
        dict(label="$1,000", amount=1000, original=10, remaining=8, launch_probability=.01),
        dict(label="$20", amount=20, original=200, remaining=100, launch_probability=.2)])


class CalculationTests(unittest.TestCase):
    def test_hand_worked_targets(self):
        g = calculate(example(), 1000)
        self.assertAlmostEqual(g["probability"], .018)
        self.assertAlmostEqual(g["launch_probability"], .011)
        self.assertEqual(g["qualifying_remaining"], 9)
        self.assertAlmostEqual(g["per_dollar"], .0009)
        self.assertAlmostEqual(calculate(example(), 100000)["probability"], .002)

    def test_ticket_and_dollar_order_and_ties(self):
        a, b = example("2", 50), example("1", 10)
        b["tiers"][1]["remaining"] = 2
        self.assertEqual(rank([b, a], 1000)[0]["game_number"], "2")
        self.assertEqual(rank([a, b], 1000, "dollar")[0]["game_number"], "1")
        self.assertEqual([g["game_number"] for g in rank([example("12"), example("2"), example("3",10)],1000)], ["3", "2", "12"])

    def test_exhausted_ended_missing_and_invalid(self):
        cases = []
        g=example(); g["tiers"][0]["remaining"]=0; cases.append((g,100000))
        g=example(); g["status"]="ended"; cases.append((g,1000))
        g=example(); g["tiers"][0]["amount"]=None; cases.append((g,1000))
        g=example(); g["tiers"][2]["remaining"]=0; cases.append((g,1000))
        g=example(); g["tiers"][1]["remaining"]=11; cases.append((g,1000))
        g=example(); g["tiers"][0]["launch_probability"]=float("nan"); cases.append((g,1000))
        for game,target in cases:
            with self.subTest(game=game): self.assertTrue(calculate(game,target)["reason"])

    def test_freshness_and_formatting(self):
        now=datetime.now(timezone.utc)
        self.assertFalse(is_stale(now-timedelta(hours=47),now,now))
        self.assertTrue(is_stale(now-timedelta(hours=49),now,now))
        self.assertTrue(is_stale(now,now-timedelta(hours=49),now))
        self.assertEqual(money(1000000),"$1,000,000")
        self.assertEqual(odds(.0000312),"1 in 32,000")
        self.assertEqual(odds(0),"No qualifying prizes")
        self.assertEqual(source_stamp('2026-10-25T04:00:00+00:00','ct'),'Oct 25, 2026')


class SourceTests(unittest.TestCase):
    def test_catalog_and_annuity(self):
        catalog=ct_catalog(fixture("ct_catalog.html"))
        self.assertEqual(len(catalog),22)
        self.assertEqual({g["ticketCostRaw"] for g in catalog},{10,20,30,50})
        game=ct_game(fixture("ct_1850.html"),1850)
        self.assertEqual(game["total_tickets"],2067660)
        self.assertEqual(game["tiers"][0]["amount"],1000000)
        self.assertIn("$750,000 cash option",game["tiers"][0]["label"])
        self.assertIn("20-year",game["tiers"][0]["label"])
        self.assertEqual(calculate(game,1000000)["qualifying_remaining"],1)

    def test_missing_and_conflicting_ct_values(self):
        raw=next(v for v in flight_values(fixture("ct_1850.html"),"game") if isinstance(v,dict))
        def html(g): return '<script>self.__next_f.push('+json.dumps([1,json.dumps({'game':g})])+')</script>'
        g=copy.deepcopy(raw); del g["totalTickets"]
        with self.assertRaises(SourceError): ct_game(html(g),1850)
        g=copy.deepcopy(raw); g["howToPlay"]["core"]="Unclear annuity"
        self.assertTrue(ct_game(html(g),1850)["issue"])
        g=copy.deepcopy(raw); g["displayTopPrize"]=None
        self.assertEqual(ct_game(html(g),1850)["tiers"][0]["amount"],750000)
        g=copy.deepcopy(raw); g["status"]="ended"
        self.assertEqual(ct_game(html(g),1850)["status"],"ended")
        g=copy.deepcopy(raw); terms=g["howToPlay"]["core"];g["howToPlay"]["core"]="$15"
        stream='15:T'+format(len(terms.encode('utf-8')),'x')+','+terms+'\n0:'+json.dumps({'game':g})
        response='<script>self.__next_f.push('+json.dumps([1,stream])+')</script>'
        self.assertEqual(ct_game(response,1850)["tiers"][0]["amount"],1000000)

    def test_ny_metadata_join_and_change_detection(self):
        metadata={g["game_number"]:g for g in validate_metadata(json.loads(SEED.read_text()))}
        rows=json.loads(fixture("ny_prizes.json"))
        games={g["game_number"]:g for g in ny_games(rows,metadata,"2026-10-26T07:34:11+00:00")}
        self.assertEqual(games["1713"]["tiers"][0]["amount"],3000000)
        self.assertEqual(games["1713"]["tiers"][0]["remaining"],4)
        self.assertIn("conflict",games["1688"]["issue"])
        self.assertEqual(games["1712"]["issue"],"Awaiting verified game details")
        changed=copy.deepcopy(rows); changed[0]["total"]=str(int(changed[0]["total"])+1); changed[0]["paid"]=str(int(changed[0]["paid"])+1)
        games=ny_games(changed,metadata,"2026-10-26T07:34:11+00:00")
        self.assertTrue(any("structure" in g.get("issue","") for g in games))
        metadata["1713"]["tiers"][0]["source_label"]="Unexpected tier"
        self.assertTrue(next(g for g in ny_games(rows,metadata,"2026-10-26") if g["game_number"]=="1713")["issue"])
        placeholder=[dict(game_number="9999",game_name="New",paid="0",unpaid="0",total="0",prize_amount="$10")]
        self.assertEqual(ny_games(placeholder,metadata,"2026-10-26")[0]["issue"],"Awaiting verified game details")

    def test_metadata_validation_and_ended_seed(self):
        seed=json.loads(SEED.read_text()); games=validate_metadata(seed)
        self.assertEqual(len(games),40)
        self.assertEqual(sum(g["status"]=="ended" for g in games),8)
        bad=copy.deepcopy(seed); bad["games"][0]["tiers"][0]["odds_denominator"]=0
        with self.assertRaises(ValueError): validate_metadata(bad)
        bad=copy.deepcopy(seed); bad["games"][0]["url"]="javascript:alert(1)"
        with self.assertRaises(ValueError): validate_metadata(bad)

    def test_draw_games(self):
        power=draw_game(fixture("ct_powerball.html"),"powerball")
        mega=draw_game(fixture("ct_mega.html"),"mega-millions")
        self.assertEqual((power["price"],power["odds"]),(2,292201338))
        self.assertEqual((mega["price"],mega["odds"]),(5,290472336))
        self.assertEqual(mega["next_draw"],"2026-10-28T03:00:00+00:00")

    def test_timeouts_blocks_backoff_spacing(self):
        session=Mock(); sleep=Mock(); client=PublicClient(session,sleep=sleep,clock=lambda:1)
        session.get.side_effect=[requests.Timeout(),Mock(status_code=200,text="ok",headers={})]
        self.assertEqual(client.get(CT_CATALOG),"ok")
        self.assertEqual(client.count,2); sleep.assert_any_call(2)
        for status in (403,429):
            session=Mock();session.get.return_value=Mock(status_code=status,headers={"Retry-After":"86400"})
            client=PublicClient(session,sleep=Mock())
            with self.assertRaises(SourceError): client.get(CT_CATALOG)
            with self.assertRaises(SourceError): client.get(CT_CATALOG)
            self.assertEqual(session.get.call_count,1)
        session=Mock();session.get.return_value=Mock(status_code=200,headers={},text="<title>Just a moment</title>")
        with self.assertRaises(SourceError): PublicClient(session).get(CT_CATALOG)
        session=Mock();session.get.side_effect=requests.Timeout()
        with self.assertRaises(SourceError): PublicClient(session,sleep=Mock()).get(NY_FEED)
        self.assertEqual(session.get.call_count,3)
        session=Mock();session.get.return_value=Mock(status_code=503,headers={"Retry-After":"3600"})
        with self.assertRaises(SourceError): PublicClient(session,sleep=Mock()).get(NY_FEED)
        self.assertEqual(session.get.call_count,1)


class LotteryIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.app=create_app(dict(TESTING=True,SECRET_KEY="lottery-test",SQLALCHEMY_DATABASE_URI="sqlite://",SQLALCHEMY_TRACK_MODIFICATIONS=False,WTF_CSRF_ENABLED=False))
        self.context=self.app.app_context();self.context.push();db.create_all()
        self.client=self.app.test_client()
        self.seed=json.loads(SEED.read_text())

    def tearDown(self):
        db.session.remove();db.drop_all();self.context.pop()

    def http(self):
        client=Mock(count=0)
        def get(url):
            client.count+=1
            if url==NY_INFO: return json.dumps({"rowsUpdatedAt":int(datetime.now(timezone.utc).timestamp())})
            if url==NY_FEED: return fixture("ny_prizes.json")
            if url==NY_COUNT: return json.dumps([{"count":len(json.loads(fixture("ny_prizes.json")))}])
            if url==CT_CATALOG: return fixture("ct_catalog.html")
            if "scratch-games/" in url:
                return fixture("ct_1850.html").replace('1850',url.rsplit('/',1)[-1])
            return fixture("ct_powerball.html" if url.endswith("powerball") else "ct_mega.html")
        client.get.side_effect=get
        return client

    def test_import_dry_run_atomic_validation(self):
        self.assertEqual(import_metadata(self.seed,True),40)
        self.assertEqual(LotteryGameMetadata.query.count(),0)
        invalid=copy.deepcopy(self.seed);invalid["games"][-1]["price"]=0
        with self.assertRaises(ValueError): import_metadata(invalid)
        self.assertEqual(LotteryGameMetadata.query.count(),0)
        import_metadata(self.seed);import_metadata(self.seed)
        self.assertEqual(LotteryGameMetadata.query.count(),40)

    def test_refresh_duplicate_dry_run_and_lock(self):
        import_metadata(self.seed)
        self.assertEqual(refresh("ny",True,client=self.http())[0]["status"],"dry-run")
        self.assertEqual(LotterySnapshot.query.count(),0);self.assertEqual(LotteryRefreshRun.query.count(),0)
        client=self.http();timestamp=int(datetime.now(timezone.utc).timestamp())
        original=client.get.side_effect
        client.get.side_effect=lambda url: json.dumps({"rowsUpdatedAt":timestamp}) if url==NY_INFO else original(url)
        refresh("ny",client=client);refresh("ny",client=client)
        self.assertEqual(LotterySnapshot.query.count(),1);self.assertEqual(LotteryRefreshRun.query.count(),2)
        with capture_lock(0,namespace=LOCK_NAMESPACE):
            self.assertEqual(refresh("ny",client=self.http())[0]["status"],"skipped")

    def test_partial_failure_preserves_previous_success(self):
        import_metadata(self.seed)
        refresh("all",client=self.http(),scheduled=True)
        ids={s:latest_snapshot(s).id for s in ("ny","ct","draw")}
        client=self.http();get=client.get.side_effect
        client.get.side_effect=lambda url: (_ for _ in ()).throw(SourceError("Source returned HTTP 403")) if "scratch-games/" in url else get(url)
        results=refresh("all",client=client)
        self.assertEqual([r["status"] for r in results],["success","failed","success"])
        self.assertEqual(latest_snapshot("ct").id,ids["ct"])
        self.assertEqual(LotteryRefreshRun.query.filter_by(source="ct",status="failed").count(),1)

    def test_retry_after_across_runs(self):
        client=self.http();error=SourceError("Rate limited");error.retry_after="172800";client.get.side_effect=error
        self.assertEqual(refresh("ct",client=client)[0]["status"],"failed")
        client=self.http();results=refresh("ct",client=client)
        self.assertTrue(all(r["status"]=="skipped" for r in results));client.get.assert_not_called()

    def test_incomplete_or_mid_publication_ny_preserves_snapshot(self):
        import_metadata(self.seed); refresh('ny',client=self.http()); identifier=latest_snapshot('ny').id
        client=self.http();get=client.get.side_effect
        client.get.side_effect=lambda url: '[{"count":999}]' if url==NY_COUNT else get(url)
        self.assertEqual(refresh('ny',client=client)[0]['status'],'failed')
        self.assertEqual(latest_snapshot('ny').id,identifier)
        client=self.http();get=client.get.side_effect;versions=iter([1,2])
        client.get.side_effect=lambda url: json.dumps({'rowsUpdatedAt':next(versions)}) if url==NY_INFO else get(url)
        self.assertEqual(refresh('ny',client=client)[0]['status'],'failed')
        self.assertEqual(latest_snapshot('ny').id,identifier)

    def test_draw_duplicates_and_ct_structure_hold(self):
        refresh('ct',client=self.http()); refresh('ct',client=self.http())
        self.assertEqual(LotterySnapshot.query.filter_by(source='draw').count(),1)
        snapshot=latest_snapshot('ct');data=copy.deepcopy(snapshot.data);data['games'][0]['total_tickets']+=1;snapshot.data=data;db.session.commit()
        refresh('ct',client=self.http())
        self.assertTrue(latest_snapshot('ct').data['games'][0]['structure_hold'])
        refresh('ct',client=self.http())
        self.assertTrue(latest_snapshot('ct').data['games'][0]['structure_hold'])

    def test_auth_filters_expansion_stale_and_zero_upstream_requests(self):
        import_metadata(self.seed);refresh("all",client=self.http(),scheduled=True)
        self.assertEqual(self.client.get('/scratch-offs',base_url='https://localhost').status_code,302)
        user=User(email='lottery@example.com',username='lottery',email_verified=True);db.session.add(user);db.session.commit()
        with self.client.session_transaction(base_url='https://localhost') as session: session['_user_id']=str(user.id);session['_fresh']=True
        g.pop('_login_user', None)
        with patch('requests.sessions.Session.request',side_effect=AssertionError("Page must not request lottery sites")) as network:
            for query in ('','?state=ct&target=100000&basis=dollar&price=50','?state=ny&preset=100000','?q=1713','?state=invalid&target=123','?prices_set=1'):
                response=self.client.get('/scratch-offs'+query,base_url='https://localhost')
                self.assertEqual(response.status_code,200)
                self.assertIn('private, no-store',response.headers['Cache-Control'])
            text=self.client.get('/scratch-offs?q=1713',base_url='https://localhost').text
            self.assertIn('id="game-1713"',text);self.assertIn('<table>',text);self.assertIn('Today’s picks',text)
            network.assert_not_called()
            snapshot=latest_snapshot('ny');snapshot.source_at=datetime.now(timezone.utc)-timedelta(days=3);db.session.commit()
            text=self.client.get('/scratch-offs',base_url='https://localhost').text
            self.assertNotIn('Today’s picks',text);self.assertIn('Dated comparisons',text)


if __name__ == '__main__': unittest.main()
