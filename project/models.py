import secrets
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from flask_login import UserMixin
from sqlalchemy import BigInteger, Boolean, Column, Float, ForeignKey, Integer, String, Table, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from project.database import db
from project.curriculum_terms import ARTIFACT_FORMATS, ARTIFACT_LANGUAGES, INTERACTION_STYLES

COMPLETED_DISPLAY_MODES = {
    "inline_bottom": "Inline at Bottom",
    "category_section": "Category Completed Section",
    "global_section": "Global Completed Section",
}

list_shares = Table(
    "list_shares",
    db.metadata,
    Column("list_id", Integer, ForeignKey("custom_list.id")),
    Column("user_id", Integer, ForeignKey("user.id")),
)


class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    email: Mapped[str] = mapped_column(String(120), index=True, unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(256))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    scheduler_preference: Mapped[str] = mapped_column(
        String(32), default="sm2_v2_steps"
    )
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verification_token: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, unique=True, index=True
    )
    email_verification_expires_at: Mapped[Optional[datetime]] = mapped_column(
        db.DateTime(timezone=True), nullable=True
    )

    gifts: Mapped[list["Gift"]] = relationship("Gift", back_populates="author")
    custom_lists: Mapped[list["CustomList"]] = relationship(
        "CustomList", back_populates="owner", lazy="dynamic"
    )
    shared_lists: Mapped[list["CustomList"]] = relationship(
        "CustomList",
        secondary=list_shares,
        back_populates="shared_with",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class YouTubeConnection(db.Model):
    """One maintainer-managed connection for the catalog shared by all users."""

    __tablename__ = "youtube_connection"
    __table_args__ = (db.CheckConstraint("id = 1", name="ck_youtube_connection_singleton"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    encrypted_refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    oauth_client_id: Mapped[str] = mapped_column(String(512), nullable=False)
    connected_by_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    granted_scopes: Mapped[Optional[list]] = mapped_column(db.JSON)
    channel_id: Mapped[Optional[str]] = mapped_column(String(255))


class PasswordResetAttempt(db.Model):
    """Track password reset attempts for rate limiting."""

    __tablename__ = "password_reset_attempt"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), index=True)
    attempted_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class EmailVerificationAttempt(db.Model):
    """Track email verification resend attempts for rate limiting."""

    __tablename__ = "email_verification_attempt"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120), index=True)
    attempted_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class CustomList(db.Model):
    __tablename__ = "custom_list"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    completed_display_mode: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, default="category_section"
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    owner: Mapped["User"] = relationship("User", back_populates="custom_lists")
    categories: Mapped[list["ListCategory"]] = relationship(
        "ListCategory", back_populates="custom_list", lazy="dynamic", cascade="all, delete-orphan"
    )
    shared_with: Mapped[list["User"]] = relationship(
        "User", secondary=list_shares, back_populates="shared_lists", lazy="dynamic"
    )
    invitations: Mapped[list["ListInvitation"]] = relationship(
        "ListInvitation", back_populates="custom_list", lazy="dynamic", cascade="all, delete-orphan"
    )


class ListCategory(db.Model):
    __tablename__ = "list_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, default=0)
    custom_list_id: Mapped[int] = mapped_column(ForeignKey("custom_list.id"))
    custom_list: Mapped["CustomList"] = relationship(
        "CustomList", back_populates="categories"
    )
    items: Mapped[list["ListItem"]] = relationship(
        "ListItem", back_populates="category", lazy="dynamic", cascade="all, delete-orphan"
    )


class ListItem(db.Model):
    __tablename__ = "list_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    ordering: Mapped[int] = mapped_column(Integer, default=0)
    category_id: Mapped[int] = mapped_column(ForeignKey("list_category.id"))
    category: Mapped["ListCategory"] = relationship(
        "ListCategory", back_populates="items"
    )


class InvitationMixin:
    """Shared columns and logic for invitation models."""

    email: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    token: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        db.DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False
    )

    @property
    def is_expired(self) -> bool:
        """Check if the invitation has expired."""
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            # Some DB backends/tests may deserialize timezone columns as naive values.
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires_at

    @property
    def is_accepted(self) -> bool:
        """Check if the invitation has been accepted."""
        return self.accepted_at is not None

    def accept(self) -> None:
        """Mark the invitation as accepted."""
        self.accepted_at = datetime.now(timezone.utc)


class ListInvitation(InvitationMixin, db.Model):
    """
    Represents a pending invitation to share a list with a user who may not have an account yet.
    """

    __tablename__ = "list_invitation"

    id: Mapped[int] = mapped_column(primary_key=True)
    list_id: Mapped[int] = mapped_column(ForeignKey("custom_list.id"), nullable=False)

    custom_list: Mapped["CustomList"] = relationship(
        "CustomList", back_populates="invitations"
    )

    @classmethod
    def create_invitation(cls, email: str, list_id: int, expires_in_days: int = 7):
        """
        Create a new invitation with a secure token.

        Args:
            email: The email address to invite
            list_id: The ID of the list to share
            expires_in_days: Number of days until the invitation expires

        Returns:
            ListInvitation: The created invitation
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        return cls(email=email, list_id=list_id, token=token, expires_at=expires_at)


class SiteInvitation(InvitationMixin, db.Model):
    """
    Represents a general invitation to sign up (not tied to a specific list).
    """

    __tablename__ = "site_invitation"

    id: Mapped[int] = mapped_column(primary_key=True)
    invited_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("user.id"), nullable=True
    )

    invited_by: Mapped[Optional["User"]] = relationship("User")

    @classmethod
    def create_invitation(cls, email: str, expires_in_days: int = 7):
        """
        Create a new general invitation with a secure token.

        Args:
            email: The email address to invite
            expires_in_days: Number of days until the invitation expires

        Returns:
            SiteInvitation: The created invitation
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
        return cls(email=email, token=token, expires_at=expires_at)


class Gift(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(140))
    body: Mapped[str] = mapped_column(String(140))
    image_url: Mapped[Optional[str]] = mapped_column(String(140), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        index=True,
        default=lambda: datetime.now(timezone.utc),
    )
    user_id: Mapped[int] = mapped_column(ForeignKey(User.id), index=True)

    author: Mapped[User] = relationship("User", back_populates="gifts")


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    company_name = db.Column(db.String, nullable=False)
    listing_url = db.Column(db.String, nullable=False)
    listing_image = db.Column(db.String, default="")
    posted_date = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False, index=True
    )

    saved_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))
    archived_at = db.Column(db.DateTime(timezone=True))
    revision = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    accepted_details = db.Column(db.JSON)

    owner = db.relationship("User")

    def __init__(self, title, company_name, listing_url, posted_date, user_id):
        self.title = title
        self.company_name = company_name
        self.listing_url = listing_url
        self.posted_date = posted_date
        self.user_id = user_id

    def __repr__(self):
        return "<Job %r>" % self.company_name

    def render_screenshot(self):
        """Legacy compatibility only. Captures require an explicit tracked action."""
        return False


class JobMutationReceipt(db.Model):
    __tablename__ = "job_mutation_receipt"
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    request_id = db.Column(db.String(36), primary_key=True)
    payload = db.Column(db.JSON, nullable=False)
    response = db.Column(db.JSON, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)


class JobCapture(db.Model):
    __tablename__ = "job_capture"
    id = db.Column(db.String(36), primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    source_url = db.Column(db.String, nullable=False)
    source_revision = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(16), nullable=False)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    finished_at = db.Column(db.DateTime(timezone=True))
    error_code = db.Column(db.String(32))
    object_key = db.Column(db.String(200))
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)


class JobExtraction(db.Model):
    """Private, expiring two-stage receipt. Accepted excerpts live on the job."""
    __tablename__ = "job_extraction"
    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"))
    source_revision = db.Column(db.Integer)
    source_url = db.Column(db.String(2048), nullable=False)
    retry_of = db.Column(db.String(36))
    status = db.Column(db.String(20), nullable=False)
    stage = db.Column(db.String(12), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    fetched_at = db.Column(db.DateTime(timezone=True))
    summary_started_at = db.Column(db.DateTime(timezone=True))
    finished_at = db.Column(db.DateTime(timezone=True))
    accepted_at = db.Column(db.DateTime(timezone=True))
    error_code = db.Column(db.String(32))
    source = db.Column(db.JSON)
    result = db.Column(db.JSON)
    metrics = db.Column(db.JSON)


class LibrarySyncRun(db.Model):
    """Durable receipt; success and imported catalog changes commit together."""

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True))
    summary: Mapped[Optional[dict]] = mapped_column(db.JSON)
    error: Mapped[Optional[str]] = mapped_column(String(255))


class Playlist(db.Model):
    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, index=True
    )
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    videos: Mapped[list["Video"]] = relationship("Video", back_populates="playlist")


class LibraryPin(db.Model):
    """Personal shortcuts; the catalog itself remains shared."""

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), primary_key=True)
    playlist_id: Mapped[str] = mapped_column(ForeignKey("playlist.id", ondelete="CASCADE"), primary_key=True)
    pinned_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)


class LibraryWorkflow(db.Model):
    __table_args__ = (db.CheckConstraint("id = 1", name="ck_library_workflow_singleton"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_playlist_id: Mapped[str] = mapped_column(ForeignKey("playlist.id"), nullable=False)
    destination_playlist_id: Mapped[str] = mapped_column(ForeignKey("playlist.id"), nullable=False)
    membership_checked_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True))


class LibraryWatchedMembership(db.Model):
    """Confirmed upstream membership, never inferred from retained catalog rows."""
    video_url_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    confirmed_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)


class LibraryMove(db.Model):
    """An intent and checkpoints committed before each non-atomic YouTube write."""
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False, index=True)
    channel_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_playlist_id: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_playlist_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_entry_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    destination_entry_id: Mapped[Optional[str]] = mapped_column(String(255))
    video_url_id: Mapped[str] = mapped_column(String(255), nullable=False)
    video_title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_title: Mapped[str] = mapped_column(String(255), nullable=False)
    destination_title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(16), nullable=False)
    started_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True), nullable=False)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True))
    removal_request_id: Mapped[Optional[str]] = mapped_column(String(36))
    error: Mapped[Optional[str]] = mapped_column(String(255))


class Video(db.Model):
    id: Mapped[str] = mapped_column(primary_key=True)
    playlist_id: Mapped[str] = mapped_column(
        ForeignKey("playlist.id"), nullable=False, index=True
    )
    video_url_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), nullable=False, index=True
    )
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embed_url: Mapped[str] = mapped_column(String(255), nullable=False)
    watched: Mapped[bool] = mapped_column(default=False)
    position: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="videos")


class ReviewProgress(db.Model):
    """
    Current review state for a card.

    next_review is the canonical source of truth for scheduling.
    interval is derived/informational.
    """

    __tablename__ = "review_progress"
    __table_args__ = (db.UniqueConstraint("user_id", "card_id", name="uq_review_progress_user_card"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    card_id: Mapped[str] = mapped_column(String(128), index=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    scheduler_version: Mapped[str] = mapped_column(String(32), default="sm2_v2_steps")
    learning_state: Mapped[str] = mapped_column(String(16), default="new")
    step_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lapses: Mapped[int] = mapped_column(Integer, default=0)
    last_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    half_life_days: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_recall: Mapped[float] = mapped_column(Float, default=0.9)
    predicted_recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    graduated_at: Mapped[Optional[datetime]] = mapped_column(
        db.DateTime(timezone=True), nullable=True
    )
    easiness: Mapped[float] = mapped_column(Float, default=2.5)
    interval: Mapped[int] = mapped_column(Integer, default=1)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    next_review: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_reviewed: Mapped[Optional[datetime]] = mapped_column(
        db.DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User")


class CurriculumItem(db.Model):
    """Stable identity, independent of content revisions and learner progress."""

    __tablename__ = "curriculum_item"
    __table_args__ = (db.CheckConstraint(
        "kind IN ('concept', 'question', 'exercise')", name="ck_curriculum_item_kind"
    ),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))


class ContentRevision(db.Model):
    """Immutable content snapshot; publication metadata is recorded separately."""

    __tablename__ = "content_revision"
    __table_args__ = (
        db.CheckConstraint("version > 0", name="ck_content_revision_version"),
        db.CheckConstraint("schema_version > 0", name="ck_content_revision_schema_version"),
        db.CheckConstraint(
            "(published_at IS NULL AND reviewed_by IS NULL AND reviewed_on IS NULL) OR "
            "(published_at IS NOT NULL AND reviewed_by IS NOT NULL AND reviewed_on IS NOT NULL)",
            name="ck_content_revision_review",
        ),
    )

    item_id: Mapped[str] = mapped_column(ForeignKey("curriculum_item.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    schema_version: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(db.JSON)
    imported_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))
    published_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True))
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(120))
    reviewed_on: Mapped[Optional[date]] = mapped_column(db.Date)


class ReviewReceipt(db.Model):
    """A rating and its response commit together, scoped to the signed-in user."""

    __tablename__ = "review_receipt"
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[dict] = mapped_column(db.JSON)
    response: Mapped[dict] = mapped_column(db.JSON)
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))


class ReviewLog(db.Model):
    __tablename__ = "review_log"
    __table_args__ = (db.ForeignKeyConstraint(
        ["card_id", "content_version"], ["content_revision.item_id", "content_revision.version"],
        name="fk_review_log_content_revision",
    ),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    card_id: Mapped[str] = mapped_column(String(128), index=True)
    content_version: Mapped[Optional[int]] = mapped_column(Integer)
    reviewed_at: Mapped[datetime] = mapped_column(
        db.DateTime(timezone=True), index=True
    )
    rating: Mapped[int] = mapped_column(Integer)
    scheduler_version: Mapped[str] = mapped_column(String(32))
    learning_state_before: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True
    )
    learning_state_after: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True
    )
    step_index_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    step_index_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lapses_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lapses_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    half_life_before: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    half_life_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    predicted_recall_before: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    predicted_recall_after: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )
    target_recall: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    interval_before: Mapped[int] = mapped_column(Integer)
    easiness_before: Mapped[float] = mapped_column(Float)
    repetitions_before: Mapped[int] = mapped_column(Integer)
    next_review_before: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))

    interval_after: Mapped[int] = mapped_column(Integer)
    easiness_after: Mapped[float] = mapped_column(Float)
    repetitions_after: Mapped[int] = mapped_column(Integer)
    next_review_after: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))

    response_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    user: Mapped["User"] = relationship("User")


def _one_of(column, values):
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


# Practice records deliberately have no ORM relationships: deletes cascade in the
# database, and every query is explicit and owner-scoped in practice_service.
class PracticeSession(db.Model):
    """One learner's attempt at a pinned exercise revision: conversation and artifacts."""

    __tablename__ = "practice_session"
    __table_args__ = (
        db.ForeignKeyConstraint(["exercise_id", "exercise_version"],
                                ["content_revision.item_id", "content_revision.version"],
                                name="fk_practice_session_exercise"),
        db.CheckConstraint(_one_of("interaction_style", INTERACTION_STYLES), name="ck_practice_session_style"),
        db.CheckConstraint("status IN ('active', 'paused', 'completed')", name="ck_practice_session_status"),
        db.Index("ix_practice_session_user_exercise", "user_id", "exercise_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", name="fk_practice_session_user"))
    exercise_id: Mapped[str] = mapped_column(String(128))
    exercise_version: Mapped[int] = mapped_column(Integer)
    interaction_style: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    # The interviewer behaviour this session uses, pinned at start. Versions are immutable.
    profile_version: Mapped[str] = mapped_column(String(32), default="interviewer-1", server_default="interviewer-1")
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))


class ArtifactRevision(db.Model):
    """Immutable learner work. Revisions of one artifact share its stable artifact ID."""

    __tablename__ = "artifact_revision"
    __table_args__ = (
        db.UniqueConstraint("practice_session_id", "artifact_id", "revision", name="uq_artifact_revision_number"),
        # Target for composite foreign keys that keep citations inside one session.
        db.UniqueConstraint("practice_session_id", "id", name="uq_artifact_revision_session_id"),
        db.CheckConstraint("revision > 0", name="ck_artifact_revision_revision"),
        db.CheckConstraint(_one_of("format", ARTIFACT_FORMATS), name="ck_artifact_revision_format"),
        db.CheckConstraint(_one_of("language", ARTIFACT_LANGUAGES), name="ck_artifact_revision_language"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_session.id", ondelete="CASCADE", name="fk_artifact_revision_session"))
    artifact_id: Mapped[str] = mapped_column(String(128))
    revision: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    format: Mapped[str] = mapped_column(String(32))
    language: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    body_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))


class SessionMessage(db.Model):
    """Ordered session record: conversation turns plus structured system records."""

    __tablename__ = "session_message"
    __table_args__ = (
        db.UniqueConstraint("practice_session_id", "sequence", name="uq_session_message_sequence"),
        db.UniqueConstraint("practice_session_id", "id", name="uq_session_message_session_id"),
        db.CheckConstraint("sequence > 0", name="ck_session_message_sequence"),
        db.CheckConstraint("role IN ('learner', 'interviewer', 'system')", name="ck_session_message_role"),
        db.CheckConstraint("kind IN ('turn', 'brief', 'context', 'submission', 'assistance')",
                           name="ck_session_message_kind"),
        db.CheckConstraint("modality IN ('text')", name="ck_session_message_modality"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_session.id", ondelete="CASCADE", name="fk_session_message_session"))
    sequence: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    kind: Mapped[str] = mapped_column(String(16))
    modality: Mapped[str] = mapped_column(String(16))
    body: Mapped[str] = mapped_column(Text)
    data: Mapped[Optional[dict]] = mapped_column(db.JSON)
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))


class SessionMessageArtifact(db.Model):
    """The exact artifact revisions a record cites, constrained to the record's session."""

    __tablename__ = "session_message_artifact"
    __table_args__ = (
        db.ForeignKeyConstraint(["practice_session_id", "message_id"],
                                ["session_message.practice_session_id", "session_message.id"],
                                ondelete="CASCADE", name="fk_session_message_artifact_message"),
        db.ForeignKeyConstraint(["practice_session_id", "artifact_revision_id"],
                                ["artifact_revision.practice_session_id", "artifact_revision.id"],
                                ondelete="CASCADE", name="fk_session_message_artifact_revision"),
    )

    message_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artifact_revision_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(String(36))


class PracticeReceipt(db.Model):
    """A practice mutation's recorded result. It stores a payload hash, never learner text."""

    __tablename__ = "practice_receipt"
    __table_args__ = (db.CheckConstraint(
        "operation IN ('start', 'save', 'send', 'pause', 'resume', 'reply', 'submit')", name="ck_practice_receipt_operation"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", name="fk_practice_receipt_user"), primary_key=True)
    request_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_session.id", ondelete="CASCADE", name="fk_practice_receipt_session"), index=True)
    operation: Mapped[str] = mapped_column(String(16))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(db.JSON)
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))


REPLY_STATUSES = ("pending", "running", "completed", "failed", "interrupted", "cancelled")
LIVE_REPLY = "status IN ('pending', 'running')"


class AIRequest(db.Model):
    """One generation for a practice session, tracked in the database so it survives restarts.

    The id is the public reply ID. Its inputs are pinned to the learner turn it answers
    (that turn's cited revisions and brief revision). A claim token and lease fence late
    writers; nothing here ever holds learner text or model output.
    """

    __tablename__ = "ai_request"
    __table_args__ = (
        db.ForeignKeyConstraint(["practice_session_id", "turn_message_id"],
                                ["session_message.practice_session_id", "session_message.id"],
                                ondelete="CASCADE", name="fk_ai_request_turn"),
        db.ForeignKeyConstraint(["practice_session_id", "reply_message_id"],
                                ["session_message.practice_session_id", "session_message.id"],
                                ondelete="CASCADE", name="fk_ai_request_reply"),
        db.CheckConstraint("kind IN ('reply', 'feedback')", name="ck_ai_request_kind"),
        db.CheckConstraint(_one_of("status", REPLY_STATUSES), name="ck_ai_request_status"),
        db.CheckConstraint("context_from_sequence > 0", name="ck_ai_request_context_from"),
        # One live generation per session, and at most one completed reply per turn.
        db.Index("uq_ai_request_live", "practice_session_id", unique=True,
                 postgresql_where=text(LIVE_REPLY), sqlite_where=text(LIVE_REPLY)),
        db.Index("uq_ai_request_completed_turn", "turn_message_id", unique=True,
                 postgresql_where=text("status = 'completed'"), sqlite_where=text("status = 'completed'")),
        db.Index("ix_ai_request_status_created", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    practice_session_id: Mapped[str] = mapped_column(
        ForeignKey("practice_session.id", ondelete="CASCADE", name="fk_ai_request_session"))
    turn_message_id: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    error_code: Mapped[Optional[str]] = mapped_column(String(32))
    context_from_sequence: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    profile_version: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    selector_model: Mapped[str] = mapped_column(String(64))
    claim_token: Mapped[Optional[str]] = mapped_column(String(64))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True))
    reply_message_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))
    started_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True))


class LearningAICharge(db.Model):
    """What a Learning AI call cost, or may have cost. Content-free.

    No foreign key to sessions or requests: deleting practice work keeps the accounting.
    A reservation still unsettled after `expires_at` is an uncertain charge and keeps counting.
    """

    __tablename__ = "learning_ai_charge"
    __table_args__ = (
        db.CheckConstraint("purpose IN ('select', 'reply', 'feedback')", name="ck_learning_ai_charge_purpose"),
        db.CheckConstraint("state IN ('reserved', 'settled', 'released')", name="ck_learning_ai_charge_state"),
        db.CheckConstraint("reserved_microusd >= 0 AND (cost_microusd IS NULL OR cost_microusd >= 0)",
                           name="ck_learning_ai_charge_amounts"),
        db.Index("ix_learning_ai_charge_period", "period"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", name="fk_learning_ai_charge_user"))
    reply_id: Mapped[str] = mapped_column(String(36))
    purpose: Mapped[str] = mapped_column(String(16))
    period: Mapped[str] = mapped_column(String(7))
    provider: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(64))
    service_tier: Mapped[str] = mapped_column(String(16))
    pricing_version: Mapped[str] = mapped_column(String(32))
    state: Mapped[str] = mapped_column(String(16))
    reserved_microusd: Mapped[int] = mapped_column(BigInteger)
    cost_microusd: Mapped[Optional[int]] = mapped_column(BigInteger)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    cached_input_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    cache_write_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(db.DateTime(timezone=True))
    settled_at: Mapped[Optional[datetime]] = mapped_column(db.DateTime(timezone=True))
