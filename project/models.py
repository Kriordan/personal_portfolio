import logging
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlencode

import boto3
import requests
from botocore.exceptions import ClientError
from flask_login import UserMixin
from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from project.database import db

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

    gifts: Mapped["Gift"] = relationship("Gift", back_populates="author")
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
        "ListCategory", back_populates="custom_list", lazy="dynamic"
    )
    shared_with: Mapped[list["User"]] = relationship(
        "User", secondary=list_shares, back_populates="shared_lists", lazy="dynamic"
    )
    invitations: Mapped[list["ListInvitation"]] = relationship(
        "ListInvitation", back_populates="custom_list", lazy="dynamic"
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
        "ListItem", back_populates="category", lazy="dynamic"
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
        if os.getenv("ENV") == "development":
            session = boto3.Session(profile_name="personalportfolio")
            s3 = session.client("s3")
        else:
            s3 = boto3.client("s3")

        apileap_url = "https://apileap.com/api/screenshot/v1/urltoimage?"
        params = urlencode(
            {
                "url": self.listing_url,
                "access_key": os.getenv("APILEAP_ACCESS_KEY"),
                "full_page": "true",
            }
        )
        apileap_image_response = requests.get(apileap_url + params, stream=True)
        apileap_image_response_object = apileap_image_response.raw

        unique_filename_hex = uuid.uuid4().hex
        screenshot_filename = f"{unique_filename_hex}.jpeg"
        self.listing_image = screenshot_filename

        bucket = os.getenv("JOBWIZARD_S3_BUCKET")

        try:
            s3.upload_fileobj(
                apileap_image_response_object, bucket, screenshot_filename
            )
        except ClientError as e:
            logging.error(e)
            return False
        return True


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

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    card_id: Mapped[str] = mapped_column(String(128), index=True)
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


class ReviewLog(db.Model):
    __tablename__ = "review_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True)
    card_id: Mapped[str] = mapped_column(String(128), index=True)
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
