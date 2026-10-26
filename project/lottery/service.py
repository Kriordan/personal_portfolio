"""CLI-only refresh orchestration and atomic publication of complete source snapshots."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from project.database import db
from project.jobwizard.capture_lock import capture_lock
from .calculations import MODEL_VERSION, utc
from .metadata import validate_metadata
from .models import LotteryGameMetadata, LotteryRefreshRun, LotterySnapshot
from .sources import CT_CATALOG, NY_COUNT, NY_FEED, NY_INFO, PublicClient, SourceError, ct_catalog, ct_game, draw_game, ny_games

LOCK_NAMESPACE = 741938210


def latest_snapshot(source):
    return LotterySnapshot.query.filter_by(source=source).order_by(LotterySnapshot.source_at.desc(), LotterySnapshot.id.desc()).first()


def import_metadata(document, dry_run=False):
    games = validate_metadata(document)
    with capture_lock(0, namespace=LOCK_NAMESPACE) as fence:
        if not fence:
            raise SourceError("Another lottery import/refresh is running")
        if not dry_run:
            for game in games:
                record = LotteryGameMetadata.query.filter_by(state="ny", game_number=game["game_number"]).first()
                if not record:
                    record = LotteryGameMetadata(state="ny", game_number=game["game_number"])
                    db.session.add(record)
                record.verified_at, record.data = utc(game["verified_at"]), game
            fence()
            db.session.commit()
    return len(games)


def collect(source, client, now):
    if source == "ny":
        # Read the feed between two version checks, rejecting a publication that changes mid-read.
        before = json.loads(client.get(NY_INFO))["rowsUpdatedAt"]
        rows = json.loads(client.get(NY_FEED))
        count = int(json.loads(client.get(NY_COUNT))[0]["count"])
        after = json.loads(client.get(NY_INFO))["rowsUpdatedAt"]
        if before != after:
            raise SourceError("NY feed changed during collection; keeping the previous snapshot")
        if count != len(rows):
            raise SourceError("NY prize feed is incomplete; keeping the previous snapshot")
        source_at = datetime.fromtimestamp(int(after), timezone.utc)
        metadata = {m.game_number: m.data for m in LotteryGameMetadata.query.filter_by(state="ny")}
        games = ny_games(rows, metadata, source_at.isoformat())
    elif source == "ct":
        catalog = ct_catalog(client.get(CT_CATALOG))
        if not catalog:
            raise SourceError("CT eligible catalog empty")
        games = [ct_game(client.get(f"{CT_CATALOG}/{g['gameNo']}"), g["gameNo"]) for g in catalog]
        source_at = min(utc(g["source_at"]) for g in games)
        previous = latest_snapshot("ct")
        old = {g["game_number"]: g for g in previous.data["games"]} if previous else {}
        for g in games:
            original = old.get(g["game_number"])
            signature = lambda value: (value.get("total_tickets"), [(t["amount"], t["original"]) for t in value["tiers"]])
            if original and (original.get("structure_hold") or signature(original) != signature(g)):
                g.update(issue="Original prize structure changed; verification required", structure_hold=True)
    else:
        games = [draw_game(client.get(f"https://ctlottery.com/games/draw-games/{slug}"), slug)
                 for slug in ("powerball", "mega-millions")]
        source_at = now
    if source_at > now + timedelta(hours=1):
        raise SourceError("Source date is unexpectedly in the future")
    return dict(model_version=MODEL_VERSION, source_at=source_at.isoformat(), games=games), source_at


def retry_time(raw, now):
    if not raw:
        return None
    try:
        return now + timedelta(seconds=max(0, int(raw))) if raw.isdigit() else utc(parsedate_to_datetime(raw))
    except (ValueError, TypeError, OverflowError):
        return now + timedelta(days=1)


def refresh(state="all", dry_run=False, scheduled=False, client=None):
    sources = ("ny", "ct", "draw") if state == "all" else (("ct", "draw") if state == "ct" else ("ny",))
    client = client or PublicClient()
    results = []
    with capture_lock(0, namespace=LOCK_NAMESPACE) as fence:
        if not fence:
            return [{"source": "all", "status": "skipped", "message": "Another lottery refresh/import is running"}]
        for source in sources:
            now = datetime.now(timezone.utc)
            related = ("ct", "draw") if source in ("ct", "draw") else (source,)
            cooldown = LotteryRefreshRun.query.filter(LotteryRefreshRun.source.in_(related), LotteryRefreshRun.retry_not_before > now).first()
            if cooldown:
                results.append(dict(source=source, status="skipped", message="Respecting source Retry-After", retry_at=utc(cooldown.retry_not_before).isoformat()))
                continue
            run = LotteryRefreshRun(source=source, started_at=now, status="running", scheduled=scheduled)
            if not dry_run:
                db.session.add(run)
                db.session.commit()
            start_count = client.count
            try:
                data, source_at = collect(source, client, now)
                previous = latest_snapshot(source)
                if previous and source_at < utc(previous.source_at):
                    raise SourceError("Source date regressed; keeping the previous snapshot")
                fingerprint = dict(data, source_at=now.date().isoformat()) if source == "draw" else data
                digest = hashlib.sha256(json.dumps(fingerprint, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                snapshot = LotterySnapshot.query.filter_by(source=source, digest=digest).first()
                if not dry_run:
                    if not snapshot:
                        snapshot = LotterySnapshot(source=source, source_at=source_at, fetched_at=now, digest=digest, data=data)
                        db.session.add(snapshot)
                        db.session.flush()
                    run.snapshot_id, run.status = snapshot.id, "success"
                    run.finished_at, run.request_count = datetime.now(timezone.utc), client.count - start_count
                    fence()
                    db.session.commit()
                results.append(dict(source=source, status="dry-run" if dry_run else "success", games=len(data["games"]),
                                    awaiting_details=sum(bool(g.get("issue")) for g in data["games"]), requests=client.count-start_count,
                                    source_at=source_at.isoformat()))
            except Exception as exc:
                db.session.rollback()
                message = str(exc) if isinstance(exc, SourceError) else "Source data could not be validated; keeping the previous snapshot"
                if not dry_run:
                    run.status, run.error = "failed", message[:240]
                    run.finished_at, run.request_count = datetime.now(timezone.utc), client.count - start_count
                    run.retry_not_before = retry_time(getattr(exc, "retry_after", None), now)
                    db.session.add(run)
                    db.session.commit()
                results.append(dict(source=source, status="failed", message=message, requests=client.count-start_count))
        if not dry_run:
            prune()
    return results


def prune():
    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    # Keep one last-good snapshot per source, even through an extended outage.
    keep = [s.id for source in ("ny", "ct", "draw") if (s := latest_snapshot(source))]
    expired = [s.id for s in LotterySnapshot.query.filter(LotterySnapshot.fetched_at < cutoff, ~LotterySnapshot.id.in_(keep))]
    if expired:
        LotteryRefreshRun.query.filter(LotteryRefreshRun.snapshot_id.in_(expired)).update({"snapshot_id": None}, synchronize_session=False)
        LotterySnapshot.query.filter(LotterySnapshot.id.in_(expired)).delete(synchronize_session=False)
    LotteryRefreshRun.query.filter(LotteryRefreshRun.started_at < cutoff, ~LotteryRefreshRun.snapshot_id.in_(keep) | LotteryRefreshRun.snapshot_id.is_(None)).delete(synchronize_session=False)
    db.session.commit()
