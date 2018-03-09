import hashlib
import os
import datetime
from urllib.parse import urlencode
from urllib.request import urlretrieve

from project import db


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
            "access_key": APILEAP_API_KEY,
            "full_page": "true"
        })
        url_hash = hashlib.md5(self.listing_url).hexdigest()
        image_dir = os.path.join(app.config['BASEDIR'],
                                 'static/img/job_listings')
        filename = f'listing-screenshot-{url_hash}.jpeg'
        file_destination = os.path.join(image_dir, filename)

        urlretrieve(apileap_url + params, file_destination)
        self.listing_image = "img/job_listings/" + filename
