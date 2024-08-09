import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import boto3
import requests
import sqlalchemy as sa
import sqlalchemy.orm as orm
from botocore.exceptions import ClientError
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from project.database import db


class User(UserMixin, db.Model):
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    username: orm.Mapped[str] = orm.mapped_column(
        sa.String(64), index=True, unique=True
    )
    email: orm.Mapped[str] = orm.mapped_column(sa.String(120), index=True, unique=True)
    password_hash: orm.Mapped[Optional[str]] = orm.mapped_column(sa.String(256))

    gifts: orm.WriteOnlyMapped["Gift"] = orm.relationship(
        "Gift", back_populates="author"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Gift(db.Model):
    id: orm.Mapped[int] = orm.mapped_column(primary_key=True)
    title: orm.Mapped[str] = orm.mapped_column(sa.String(140))
    body: orm.Mapped[str] = orm.mapped_column(sa.String(140))
    image_url: orm.Mapped[Optional[str]] = orm.mapped_column(
        sa.String(140), nullable=True
    )
    timestamp: orm.Mapped[datetime] = orm.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc)
    )
    user_id: orm.Mapped[int] = orm.mapped_column(sa.ForeignKey(User.id), index=True)

    author: orm.Mapped[User] = orm.relationship("User", back_populates="gifts")


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    company_name = db.Column(db.String, nullable=False)
    listing_url = db.Column(db.String, nullable=False)
    listing_image = db.Column(db.String, default="")
    posted_date = db.Column(db.DateTime, default=datetime.utcnow())

    def __init__(self, title, company_name, listing_url, posted_date):
        self.title = title
        self.company_name = company_name
        self.listing_url = listing_url
        self.posted_date = posted_date

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
    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    title: orm.Mapped[str] = orm.mapped_column(
        sa.String(255), nullable=False, index=True
    )
    description: orm.Mapped[Optional[str]] = orm.mapped_column(sa.Text, nullable=True)
    published_at: orm.Mapped[datetime] = orm.mapped_column(nullable=False, index=True)
    updated_at: orm.Mapped[datetime] = orm.mapped_column(nullable=False, index=True)
    thumbnail_url: orm.Mapped[Optional[str]] = orm.mapped_column(
        sa.String(255), nullable=True
    )
    created_at: orm.Mapped[datetime] = orm.mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    videos: orm.WriteOnlyMapped["Video"] = orm.relationship(
        "Video", back_populates="playlist"
    )


class Video(db.Model):
    id: orm.Mapped[str] = orm.mapped_column(primary_key=True)
    playlist_id: orm.Mapped[str] = orm.mapped_column(
        sa.ForeignKey("playlist.id"), nullable=False, index=True
    )
    video_url_id: orm.Mapped[str] = orm.mapped_column(sa.String(255), nullable=False)
    title: orm.Mapped[str] = orm.mapped_column(
        sa.String(255), nullable=False, index=True
    )
    description: orm.Mapped[Optional[str]] = orm.mapped_column(sa.Text, nullable=True)
    published_at: orm.Mapped[datetime] = orm.mapped_column(nullable=False, index=True)
    thumbnail_url: orm.Mapped[Optional[str]] = orm.mapped_column(
        sa.String(255), nullable=True
    )
    embed_url: orm.Mapped[str] = orm.mapped_column(sa.String(255), nullable=False)
    watched: orm.Mapped[bool] = orm.mapped_column(default=False)
    created_at: orm.Mapped[datetime] = orm.mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: orm.Mapped[datetime] = orm.mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    playlist: orm.Mapped["Playlist"] = orm.relationship(
        "Playlist", back_populates="videos"
    )
