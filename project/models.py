import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import boto3
import requests
from botocore.exceptions import ClientError
from flask_login import UserMixin
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from project.database import db

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


class CustomList(db.Model):
    __tablename__ = "custom_list"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    # Back reference to the owner.
    owner: Mapped["User"] = relationship("User", back_populates="custom_lists")
    # Categories within the list.
    categories: Mapped[list["ListCategory"]] = relationship(
        "ListCategory", back_populates="custom_list", lazy="dynamic"
    )
    # Users with whom this list is shared.
    shared_with: Mapped[list["User"]] = relationship(
        "User", secondary=list_shares, back_populates="shared_lists", lazy="dynamic"
    )


class ListCategory(db.Model):
    __tablename__ = "list_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    ordering: Mapped[int] = mapped_column(Integer, default=0)
    custom_list_id: Mapped[int] = mapped_column(ForeignKey("custom_list.id"))
    # Back reference to the parent list.
    custom_list: Mapped["CustomList"] = relationship(
        "CustomList", back_populates="categories"
    )
    # Items under this category.
    items: Mapped[list["ListItem"]] = relationship(
        "ListItem", back_populates="category", lazy="dynamic"
    )


class ListItem(db.Model):
    __tablename__ = "list_item"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[str] = mapped_column(String(32))
    notes: Mapped[str] = mapped_column(Text)
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    ordering: Mapped[int] = mapped_column(Integer, default=0)
    category_id: Mapped[int] = mapped_column(ForeignKey("list_category.id"))
    # Back reference to the category.
    category: Mapped["ListCategory"] = relationship(
        "ListCategory", back_populates="items"
    )


class Gift(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(140))
    body: Mapped[str] = mapped_column(String(140))
    image_url: Mapped[Optional[str]] = mapped_column(String(140), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc)
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
    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
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
    published_at: Mapped[datetime] = mapped_column(nullable=False, index=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    embed_url: Mapped[str] = mapped_column(String(255), nullable=False)
    watched: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    playlist: Mapped["Playlist"] = relationship("Playlist", back_populates="videos")
