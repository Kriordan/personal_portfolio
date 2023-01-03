import logging
import os
import uuid
import datetime
import requests
from urllib.parse import urlencode

from flask_login import UserMixin
from botocore.exceptions import ClientError

from project import db, s3, login_manager, bcrypt


users = {"foo@bar.tld": {"password": "secret"}}


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    company_name = db.Column(db.String, nullable=False)
    listing_url = db.Column(db.String, nullable=False)
    listing_image = db.Column(db.String, default="")
    posted_date = db.Column(db.DateTime, default=datetime.datetime.utcnow())

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


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    first_name = db.Column(db.String(120))
    last_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(128))

    @property
    def password(self):
        raise AttributeError("`password` is not a readable attribute")

    @password.setter
    def password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode("utf-8")

    def verify_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).filter_by(id=user_id)).scalar()


@login_manager.request_loader
def request_loader(request):
    email = request.form.get("email")
    if email not in users:
        return

    user = User()
    user.id = email
    return user


class Contact(db.Model):
    __tablename__ = "contact"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120))
    last_name = db.Column(db.String(120))
    last_contact = db.Column(db.DateTime)

    def __init__(self, first_name, last_name):
        self.first_name = first_name
        self.last_name = last_name
