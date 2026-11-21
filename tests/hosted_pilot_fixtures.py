"""Deterministic operator approvals; no real identity, spending, or provider access."""
from project.learning import hosted_pilot as hosted


def approval(**changes):
    return dict(format_version=1, handoff_id="00000000-0000-4000-8000-000000000001",
        source_instance_id="00000000-0000-4000-8000-000000000002", frozen_at="2026-11-01T00:00:00+00:00",
        target_app=hosted.APP_NAME, owner_id=1, owner_email="owner@example.com",
        total_microusd=5_000_000, verification_microusd=1_000_000,
        carryover_microusd=37_859, carryover_by_period={"2026-11": 37_859}, source_charge_count=5,
        source_ledger_sha256="a" * 64, draft_revisions=hosted.exact_drafts()) | changes


def environment(policy=None, *, mode="off", **changes):
    return {"LEARNING_HOSTED_PILOT": "1", hosted.APPROVAL_VARIABLE: hosted.canonical(policy or approval()),
            "LEARNING_HOSTED_AI_MODE": mode} | changes


def config(url="sqlite://", *, policy=None, mode="off", **changes):
    return dict(TESTING=True, SECRET_KEY="fixture-secret-at-least-32-characters", SENTRY_ENABLED=False,
                SQLALCHEMY_DATABASE_URI=url, WTF_CSRF_ENABLED=True,
                **hosted.settings(environment(policy, mode=mode))) | changes
