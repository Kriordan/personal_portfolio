import os
import uuid
import datetime
import requests
from urllib.parse import urlencode
from flask import current_app

from project import db, s3


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, nullable=False)
    company_name = db.Column(db.String, nullable=False)
    listing_url = db.Column(db.String, nullable=False)
    listing_image = db.Column(db.String, default='')
    posted_date = db.Column(db.DateTime, default=datetime.datetime.utcnow())

    def __init__(self, title, company_name, listing_url, posted_date):
        self.title = title
        self.company_name = company_name
        self.listing_url = listing_url
        self.posted_date = posted_date

    def __repr__(self):
        return '<Job %r>' % self.company_name

    def render_screenshot(self):
        apileap_url = "https://apileap.com/api/screenshot/v1/urltoimage?"
        params = urlencode({
            "url": self.listing_url,
            "access_key": os.getenv('APILEAP_ACCESS_KEY'),
            "full_page": "true"
        })
        apileap_image_response = requests.get(apileap_url + params, stream=True)
        apileap_image_response_object = apileap_image_response.raw
        apileap_image_response_data = apileap_image_response_object.read()

        unique_filename_hex = uuid.uuid4().hex
        screenshot_filename = f'{unique_filename_hex}.jpeg'
        self.listing_image = screenshot_filename

        s3.Bucket(os.getenv('JOBS_S3_BUCKET')).put_object(
            Key=screenshot_filename,
            Body=apileap_image_response_data,
            ContentType='image/jpeg',
            ACL='public-read'
        )


class Image(db.Model):
    __tablename__ = 'images'

    id = db.Column(db.Integer, primary_key=True)
    image_filename = db.Column(db.String, nullable=False)
    posted_date = db.Column(db.DateTime, default=datetime.datetime.utcnow())

    def __init__(self, posted_date):
        self.posted_date = posted_date

    def store_image(self, image_data):
        unique_filename_hex = uuid.uuid4().hex
        full_filename = f'{unique_filename_hex}.jpg'
        self.image_filename = full_filename

        s3.Bucket(os.getenv('IMAGES_S3_BUCKET')).put_object(
            Key=full_filename,
            Body=image_data,
            ContentType='image/jpg',
            ACL='public-read'
        )

