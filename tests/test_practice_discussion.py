"""Discussion turns, the learner's brief, pause/resume, and delete, on SQLite with foreign keys on."""
import json
import unittest
from uuid import uuid4

from project.database import db
from project.models import (
    ArtifactRevision, ContentRevision, PracticeReceipt, PracticeSession, SessionMessage, SessionMessageArtifact,
    User,
)
from project.services import practice_service as service
from project.services.learning_service import NotFoundError
from tests.test_practice_service import NOW, PracticeServiceCase

ALL_AT_ZERO = {"api": 0, "schema": 0, "algorithm": 0}


def entry(entry_id, text, kind="decision", *, pinned=False, sources=None):
    value = {"id": entry_id, "type": kind, "text": text, "pinned": pinned}
    if sources is not None:
        value["sources"] = sources
    return value


class PracticeDiscussionTests(PracticeServiceCase):
    def brief(self, session_id, entries, *, base=0, user=None, edits=None, request_id=None):
        return service.save_work(user or self.user, session_id, edits=edits, request_id=request_id or str(uuid4()),
                                 brief={"base_revision": base, "entries": entries}, now=NOW)

    def view(self, session_id):
        """What a freshly loaded workspace submits: every artifact, the brief, and the latest turn."""
        detail = service.session_detail(1, session_id)
        return {
            "edits": [{"artifact_id": artifact["artifact_id"], "base_revision": artifact["revision"],
                       "language": artifact["language"], "body": artifact["body"]} for artifact in detail["artifacts"]],
            "brief": {"base_revision": detail["session_brief"]["revision"],
                      "entries": [{key: item[key] for key in ("id", "type", "text", "pinned", "sources")}
                                  for item in detail["session_brief"]["entries"]]},
            "expected_sequence": detail["messages"][-1]["sequence"],
        }

    def send(self, session_id, view, body="Should a retry reuse the key?", *, brief=None, request_id=None, **bodies):
        edits = [dict(edit, body=bodies.get(edit["artifact_id"], edit["body"])) for edit in view["edits"]]
        return service.save_and_send(self.user, session_id, edits=edits, brief=brief or view["brief"], body=body,
                                     expected_sequence=view["expected_sequence"],
                                     request_id=request_id or str(uuid4()), now=NOW)

    def api_turn(self, session_id, revisions, *, body="A question from the API", brief_revision=0, expected=1,
                 user=None, request_id=None):
        return service.send_turn(user or self.user, session_id, body=body, expected_sequence=expected,
                                 artifact_revisions=revisions, brief_revision=brief_revision,
                                 request_id=request_id or str(uuid4()), now=NOW)

    def populate(self, session_id, user):
        """An artifact revision, a brief citing a turn, and a learner turn citing the revision."""
        service.save_work(user, session_id, edits=[self.edit("api", "work")], request_id=str(uuid4()),
                          brief={"base_revision": 0, "entries": [entry("e1", "a decision", sources=[{"turn": 1}])]})
        self.api_turn(session_id, dict(ALL_AT_ZERO, api=1), brief_revision=1, user=user)

    def test_send_saves_edits_and_cites_exactly_the_revisions_it_was_sent_with(self):
        session_id = self.start()
        self.save(session_id, [self.edit("schema", "CREATE TABLE orders ();")])
        result = self.send(session_id, self.view(session_id), "Should a retry reuse the key?", api="POST /orders",
                           brief={"base_revision": 0, "entries": [entry("e1", "Keys last 24 hours", "assumption")]})
        cited = [{"artifact_id": "api", "revision": 1}, {"artifact_id": "schema", "revision": 1}]
        # The brief snapshot is record 2; the turn is record 3.
        self.assertEqual((result["sequence"], result["artifact_revisions"], result["brief_revision"]), (3, cited, 1))
        self.assertEqual(result["artifacts"]["api"], {"revision": 1, "changed": True})
        turn = service.session_detail(1, session_id)["messages"][-1]
        self.assertEqual((turn["role"], turn["body"], turn["artifact_revisions"], turn["brief_revision"]),
                         ("learner", "Should a retry reuse the key?", cited, 1))
        # Later revisions don't change what an earlier turn cites.
        self.save(session_id, [self.edit("api", "POST /v2/orders", base=1)])
        self.assertEqual(service.session_detail(1, session_id)["messages"][-1]["artifact_revisions"], cited)
        rows = ArtifactRevision.query.filter(ArtifactRevision.id.in_(
            [citation.artifact_revision_id for citation in SessionMessageArtifact.query.all()]))
        self.assertEqual({(row.artifact_id, row.revision, row.body) for row in rows},
                         {("api", 1, "POST /orders"), ("schema", 1, "CREATE TABLE orders ();")})

    def test_api_turns_cite_saved_revisions_and_need_an_up_to_date_view(self):
        session_id = self.start()
        self.save(session_id, [self.edit("api", "v1")])
        first = self.api_turn(session_id, dict(ALL_AT_ZERO, api=1))
        self.assertEqual((first["sequence"], first["artifact_revisions"]), (2, [{"artifact_id": "api", "revision": 1}]))
        self.save(session_id, [self.edit("api", "v2", base=1)])
        with self.assertRaises(service.StaleViewError) as raised:
            self.api_turn(session_id, dict(ALL_AT_ZERO, api=1), expected=2)
        self.assertEqual((raised.exception.code, raised.exception.conflicts[0]["body"]), ("stale_artifact", "v2"))
        self.brief(session_id, [entry("e1", "Use an Idempotency-Key header")])
        with self.assertRaises(service.StaleViewError) as raised:
            self.api_turn(session_id, dict(ALL_AT_ZERO, api=2), expected=2)
        self.assertEqual((raised.exception.code, raised.exception.brief_conflict["revision"]), ("stale_brief", 1))
        with self.assertRaises(service.StaleViewError) as raised:
            self.api_turn(session_id, dict(ALL_AT_ZERO, api=2), brief_revision=1, expected=1)
        self.assertEqual((raised.exception.code, raised.exception.latest_turn), ("stale_transcript", 2))
        self.assertEqual(SessionMessage.query.filter_by(kind="turn").count(), 2)
        for revisions, brief_revision in (({"api": 2}, 1), (dict(ALL_AT_ZERO, api=2, extra=0), 1),
                                          (dict(ALL_AT_ZERO, api=3), 1), (dict(ALL_AT_ZERO, api="2"), 1),
                                          (dict(ALL_AT_ZERO, api=2), 2), ([], 1)):
            with self.subTest(revisions=revisions, brief_revision=brief_revision):
                with self.assertRaises(service.PracticeValidationError):
                    self.api_turn(session_id, revisions, brief_revision=brief_revision, expected=2)
        second = self.api_turn(session_id, dict(ALL_AT_ZERO, api=2), brief_revision=1, expected=2)
        self.assertEqual((second["sequence"], second["brief_revision"]), (4, 1))

    def test_the_freshness_check_counts_turns_not_brief_records(self):
        session_id = self.start()
        for revision in range(3):
            self.brief(session_id, [entry("e1", f"Assumption, take {revision + 1}")], base=revision)
        self.assertEqual(SessionMessage.query.count(), 4)
        view = self.view(session_id)
        self.assertEqual(view["expected_sequence"], 1)
        self.assertEqual(self.send(session_id, view)["sequence"], 5)

    def test_an_out_of_date_send_saves_and_sends_nothing(self):
        session_id = self.start()
        view = self.view(session_id)
        self.save(session_id, [self.edit("schema", "saved in another tab")])
        with self.assertRaises(service.StaleViewError) as raised:
            self.send(session_id, view, "sent from this tab", api="this tab's API")
        self.assertEqual(raised.exception.code, "out_of_date")
        self.assertEqual([(item["artifact_id"], item["body"]) for item in raised.exception.refresh],
                         [("schema", "saved in another tab")])
        self.assertEqual(ArtifactRevision.query.count(), 1)  # this tab's API edit was not saved either
        view = self.view(session_id)
        self.brief(session_id, [entry("e1", "added in another tab")])
        with self.assertRaises(service.StaleViewError) as raised:
            self.send(session_id, view)
        self.assertEqual((raised.exception.code, raised.exception.brief_refresh["entries"][0]["text"]),
                         ("out_of_date", "added in another tab"))
        self.assertEqual(SessionMessage.query.filter_by(role="learner", kind="turn").count(), 0)

    def test_a_send_after_new_turns_elsewhere_names_the_latest_turn(self):
        session_id = self.start()
        tab_a, tab_b = self.view(session_id), self.view(session_id)
        self.send(session_id, tab_a, "from tab A")
        with self.assertRaises(service.StaleViewError) as raised:
            self.send(session_id, tab_b, "from tab B", api="tab B's API")
        self.assertEqual((raised.exception.code, raised.exception.latest_turn), ("stale_transcript", 2))
        self.assertEqual([turn["body"] for turn in service.session_detail(1, session_id)["messages"]][1:], ["from tab A"])
        self.assertEqual(ArtifactRevision.query.count(), 0)

    def test_a_send_needs_a_message_and_every_artifact(self):
        session_id = self.start()
        view = self.view(session_id)
        for body in ("", "  \r\n ", None, "x" * (service.TURN_MAX_BYTES + 1), "a\x00b"):
            with self.subTest(body=str(body)[:20]):
                with self.assertRaises(service.PracticeValidationError) as raised:
                    self.send(session_id, view, body)
                self.assertEqual(raised.exception.part, "turn")
        with self.assertRaises(service.PracticeValidationError):
            service.save_and_send(self.user, session_id, edits=view["edits"][:2], brief=view["brief"], body="x",
                                  expected_sequence=1, request_id=str(uuid4()))
        self.assertEqual(SessionMessage.query.count(), 1)
        self.assertEqual(self.send(session_id, view, "  surrounding space is trimmed\r\n")["sequence"], 2)
        self.assertEqual(SessionMessage.query.filter_by(sequence=2).one().body, "surrounding space is trimmed")

    def test_sends_replay_by_request_id(self):
        session_id = self.start()
        view = self.view(session_id)
        request_id = str(uuid4())
        first = self.send(session_id, view, "once", request_id=request_id, api="POST /orders")
        # The replay returns the receipt, even though the view is now behind.
        self.assertEqual(self.send(session_id, view, "once", request_id=request_id, api="POST /orders"), first)
        self.assertEqual(SessionMessage.query.filter_by(role="learner").count(), 1)
        with self.assertRaises(service.RequestConflictError):
            self.send(session_id, view, "a different message", request_id=request_id, api="POST /orders")
        api_request = str(uuid4())
        api_first = self.api_turn(session_id, dict(ALL_AT_ZERO, api=1), expected=2, request_id=api_request)
        self.assertEqual(self.api_turn(session_id, dict(ALL_AT_ZERO, api=1), expected=2, request_id=api_request),
                         api_first)
        self.assertEqual(SessionMessage.query.filter_by(role="learner").count(), 2)

    def test_brief_snapshots_unchanged_saves_conflicts_and_untouched_views(self):
        session_id = self.start()
        pinned = entry("e1", "  Orders are retried for 24 hours  ", "assumption", pinned=True)
        self.assertEqual(self.brief(session_id, [pinned])["brief"], {"revision": 1, "changed": True})
        saved = service.session_detail(1, session_id)["session_brief"]
        self.assertEqual(saved["entries"], [{"id": "e1", "type": "assumption", "basis": "learner",
                                             "text": "Orders are retried for 24 hours", "pinned": True, "sources": []}])
        self.assertEqual((saved["revision"], saved["saved_at"]), (1, NOW.isoformat()))
        self.assertEqual(self.brief(session_id, [pinned], base=1)["brief"], {"revision": 1, "changed": False})
        # Another tab revises the entry; this tab, still on revision 1, adds an entry.
        revised = dict(pinned, text="Orders are retried for 48 hours")
        self.brief(session_id, [revised], base=1)
        with self.assertRaises(service.StaleViewError) as raised:
            self.brief(session_id, [pinned, entry("e2", "Use an Idempotency-Key header")], base=1)
        self.assertEqual(raised.exception.code, "stale_brief")
        self.assertEqual(raised.exception.brief_conflict["entries"][0]["text"], "Orders are retried for 48 hours")
        # A view that left its brief untouched keeps the newer brief while saving an artifact.
        untouched = self.brief(session_id, [pinned], base=1, edits=[self.edit("api", "POST /orders")])
        self.assertEqual((untouched["brief"], untouched["artifacts"]["api"]),
                         ({"revision": 2, "changed": False}, {"revision": 1, "changed": True}))
        # Removing every entry is a change too.
        self.assertEqual(self.brief(session_id, [], base=2)["brief"], {"revision": 3, "changed": True})
        self.assertEqual(service.session_detail(1, session_id)["session_brief"]["entries"], [])
        with self.assertRaises(service.PracticeValidationError):
            self.brief(session_id, [entry("e9", "from a revision that doesn't exist")], base=7)
        self.assertEqual(SessionMessage.query.filter_by(kind="brief").count(), 3)

    def test_brief_input_is_validated_before_anything_is_written(self):
        session_id = self.start()
        self.save(session_id, [self.edit("api", "v1")])
        cases = [
            "not a dict", {"entries": []}, {"base_revision": "0", "entries": []}, {"base_revision": 0, "entries": "x"},
            {"base_revision": 0, "entries": [entry(f"e{index}", "x") for index in range(51)]},
            {"base_revision": 0, "entries": [entry("e1", "x"), entry("e1", "y")]},
            {"base_revision": 0, "entries": [entry("E1", "x")]},
            {"base_revision": 0, "entries": [entry("e1", "x", "requirement")]},
            {"base_revision": 0, "entries": [dict(entry("e1", "x"), basis="scenario_fact")]},
            {"base_revision": 0, "entries": [entry("e1", " \n ")]},
            {"base_revision": 0, "entries": [entry("e1", "x" * (service.BRIEF_ENTRY_MAX_BYTES + 1))]},
            {"base_revision": 0, "entries": [entry("e1", "a\x00b")]},
            {"base_revision": 0, "entries": [dict(entry("e1", "x"), pinned="yes")]},
            {"base_revision": 0, "entries": [dict(entry("e1", "x"), extra=1)]},
            {"base_revision": 0, "entries": [entry("e1", "x", sources=[{"turn": 0}])]},
            {"base_revision": 0, "entries": [entry("e1", "x", sources=[{"turn": 1}, {"turn": 1}])]},
            {"base_revision": 0, "entries": [entry("e1", "x", sources=[{"artifact_id": "api"}])]},
            {"base_revision": 0, "entries": [entry("e1", "x", sources=[{"turn": 9}])]},
            {"base_revision": 0, "entries": [entry("e1", "x", sources=[{"artifact_id": "api", "revision": 2}])]},
            {"base_revision": 0, "entries": [entry("e1", "x", sources=[{"turn": n} for n in range(1, 12)])]},
        ]
        for brief in cases:
            with self.subTest(brief=str(brief)[:80]):
                with self.assertRaises(service.PracticeValidationError) as raised:
                    service.save_work(self.user, session_id, brief=brief, request_id=str(uuid4()))
                self.assertEqual(raised.exception.part, "brief")
        self.assertEqual(SessionMessage.query.filter_by(kind="brief").count(), 0)
        sources = [{"turn": 1}, {"artifact_id": "api", "revision": 1}]
        self.brief(session_id, [dict(entry("e1", "Settled the header name", sources=sources), basis="learner")])
        self.assertEqual(service.session_detail(1, session_id)["session_brief"]["entries"][0]["sources"], sources)

    def test_pause_and_resume_repeat_safely_and_a_save_resumes(self):
        session_id = self.start()
        request_id = str(uuid4())
        paused = service.set_status(self.user, session_id, status="paused", request_id=request_id, now=NOW)
        self.assertEqual(paused, {"session_id": session_id, "status": "paused", "changed": True})
        self.assertEqual(service.set_status(self.user, session_id, status="paused", request_id=request_id), paused)
        self.assertFalse(service.set_status(self.user, session_id, status="paused", request_id=str(uuid4()))["changed"])
        with self.assertRaises(service.RequestConflictError):
            service.set_status(self.user, session_id, status="active", request_id=request_id)
        self.assertEqual(service.list_sessions(1)[0]["status"], "paused")
        self.assertEqual(self.save(session_id, [self.edit("api", "back at it")])["status"], "active")
        # The website's "Save and pause" saves first; an unchanged save then resumes.
        both = service.save_work(self.user, session_id, edits=[self.edit("api", "pausing", base=1)],
                                 request_id=str(uuid4()), status="paused")
        self.assertEqual((both["status"], both["artifacts"]["api"]), ("paused", {"revision": 2, "changed": True}))
        self.assertEqual(self.save(session_id, [self.edit("api", "pausing", base=2)])["status"], "active")
        self.assertFalse(service.set_status(self.user, session_id, status="active", request_id=str(uuid4()))["changed"])
        service.set_status(self.user, session_id, status="paused", request_id=str(uuid4()))
        self.assertEqual(self.api_turn(session_id, dict(ALL_AT_ZERO, api=2))["status"], "active")
        # Completion arrives with feedback; until then nothing here reopens or pauses a completed session.
        db.session.get(PracticeSession, session_id).status = "completed"
        db.session.commit()
        with self.assertRaises(service.PracticeValidationError):
            service.set_status(self.user, session_id, status="paused", request_id=str(uuid4()))
        self.assertEqual(self.save(session_id, [self.edit("api", "later", base=2)])["status"], "completed")

    def test_delete_removes_everything_in_the_session_and_nothing_else(self):
        kept, others, session_id = self.start(), self.start(self.other), self.start()
        for target, user in ((kept, self.user), (others, self.other), (session_id, self.user)):
            self.populate(target, user)

        def rows(target):
            return {model.__tablename__: model.query.filter_by(practice_session_id=target).count()
                    for model in (ArtifactRevision, SessionMessage, SessionMessageArtifact, PracticeReceipt)}
        before = {target: rows(target) for target in (kept, others)}
        self.assertEqual(rows(session_id), {"artifact_revision": 1, "session_message": 3,
                                            "session_message_artifact": 1, "practice_receipt": 3})
        counts = service.session_counts(1, session_id)
        self.assertEqual((counts["turns"], counts["brief_revisions"], counts["artifact_revisions"]), (2, 1, 1))
        self.assertEqual(service.delete_session(self.user, session_id),
                         {"session_id": session_id, "concept_id": "idempotency"})
        self.assertIsNone(db.session.get(PracticeSession, session_id))
        self.assertEqual(set(rows(session_id).values()), {0})
        self.assertEqual({target: rows(target) for target in (kept, others)}, before)
        self.assertEqual((User.query.count(), ContentRevision.query.count()), (2, 6))
        for target in (session_id, others, "not-a-uuid"):
            with self.subTest(target=target):
                with self.assertRaises(NotFoundError):
                    service.delete_session(self.user, target)
        self.assertIsNotNone(db.session.get(PracticeSession, others))

    def test_other_accounts_cannot_change_or_delete_a_session(self):
        session_id = self.start()
        view = self.view(session_id)
        for call in (
            lambda: service.save_work(self.other, session_id, brief={"base_revision": 0, "entries": []},
                                      request_id=str(uuid4())),
            lambda: service.save_and_send(self.other, session_id, edits=view["edits"], brief=view["brief"], body="x",
                                          expected_sequence=1, request_id=str(uuid4())),
            lambda: self.api_turn(session_id, ALL_AT_ZERO, user=self.other),
            lambda: service.set_status(self.other, session_id, status="paused", request_id=str(uuid4())),
            lambda: service.delete_session(self.other, session_id),
            lambda: service.session_counts(2, session_id),
        ):
            with self.assertRaises(NotFoundError):
                call()
        self.assertEqual(SessionMessage.query.count(), 1)
        self.assertEqual(db.session.get(PracticeSession, session_id).status, "active")

    def test_receipts_store_no_turn_or_brief_text(self):
        session_id = self.start()
        self.send(session_id, self.view(session_id), "TURN_SENTINEL", api="API_SENTINEL",
                  brief={"base_revision": 0, "entries": [entry("e1", "BRIEF_SENTINEL")]})
        service.set_status(self.user, session_id, status="paused", request_id=str(uuid4()))
        self.assertEqual(PracticeReceipt.query.count(), 3)
        for receipt in PracticeReceipt.query.all():
            serialized = json.dumps(receipt.response) + receipt.payload_sha256
            for sentinel in ("TURN_SENTINEL", "API_SENTINEL", "BRIEF_SENTINEL"):
                self.assertNotIn(sentinel, serialized)


if __name__ == "__main__":
    unittest.main()
