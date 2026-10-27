"""Small, immutable source snapshots; the page never refreshes upstream data."""
from project.database import db


class LotteryGameMetadata(db.Model):
    __tablename__ = "lottery_game_metadata"
    id = db.Column(db.Integer, primary_key=True)
    state = db.Column(db.String(2), nullable=False)
    game_number = db.Column(db.String(16), nullable=False)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    __table_args__ = (db.UniqueConstraint("state", "game_number"),)


class LotterySnapshot(db.Model):
    __tablename__ = "lottery_snapshot"
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(12), nullable=False, index=True)
    source_at = db.Column(db.DateTime(timezone=True), nullable=False)
    fetched_at = db.Column(db.DateTime(timezone=True), nullable=False)
    digest = db.Column(db.String(64), nullable=False)
    data = db.Column(db.JSON, nullable=False)
    __table_args__ = (db.UniqueConstraint("source", "digest"),)


class LotteryRefreshRun(db.Model):
    __tablename__ = "lottery_refresh_run"
    id = db.Column(db.Integer, primary_key=True)
    source = db.Column(db.String(12), nullable=False, index=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    finished_at = db.Column(db.DateTime(timezone=True))
    status = db.Column(db.String(16), nullable=False)
    error = db.Column(db.String(240))
    snapshot_id = db.Column(db.Integer, db.ForeignKey("lottery_snapshot.id", ondelete="SET NULL"))
    request_count = db.Column(db.Integer, nullable=False, default=0)
    scheduled = db.Column(db.Boolean, nullable=False, default=False)
    retry_not_before = db.Column(db.DateTime(timezone=True))
