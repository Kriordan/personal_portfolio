"""
This module defines the data models used in the application.

Classes:
    User: Represents a user in the system.
    Gift: Represents an item in a user's wishlist.

Imports:
    logging: For logging errors and other messages.
    os: For interacting with the operating system.
    uuid: For generating unique identifiers.
    datetime: For working with dates and times.
    timezone: For working with time zones.
    Optional: For optional type hinting.
    urlencode: For encoding URL parameters.
    requests: For making HTTP requests.
    sqlalchemy: For interacting with SQL databases.
    sqlalchemy.orm: For mapping Python classes to database tables.
    botocore.exceptions: For handling exceptions from the botocore library.
    project: The main application package.
    db: The SQLAlchemy database instance.
    s3: The boto3 S3 client instance.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlencode

import requests
import sqlalchemy as sa
import sqlalchemy.orm as orm
from botocore.exceptions import ClientError
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from project import db, login_manager, s3


@login_manager.user_loader
def load_user(id):
    return db.session.get(User, int(id))


class User(UserMixin, db.Model):
    """
    The User model represents a user in the system.

    Attributes:
        id: A unique identifier for the user.
        username: The username of the user.
        email: The email address of the user.
        password_hash: The hashed password of the user.
        gifts: A list of items in the user's wishlist.
    """

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
        """
        Sets the password of the user.

        Args:
            password: The password to set.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """
        Checks if the password is correct.

        Args:
            password: The password to check.

        Returns:
            True if the password is correct, otherwise False.
        """
        return check_password_hash(self.password_hash, password)


class Gift(db.Model):
    """
    The Gift model represents an item in a user's wishlist.

    Attributes:
        id: A unique identifier for the gift.
        body: The body text of the gift.
        timestamp: The time the gift was created.
        user_id: The id of the user who owns the gift.
        author: The user who owns the gift.
    """

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
    """
    The Job model represents a job listing.

    Attributes:
        id: A unique identifier for the job.
        title: The title of the job.
        company_name: The name of the company offering the job.
        listing_url: The URL of the job listing.
        listing_image: The image URL of the job listing.
        posted_date: The date the job was posted.
    """

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
            response = s3.upload_fileobj(
                apileap_image_response_object, bucket, screenshot_filename
            )
        except ClientError as e:
            logging.error(e)
            return False
        return True
