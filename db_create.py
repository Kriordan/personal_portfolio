from datetime import datetime, timezone

from project import db
from project.models import Job


# db.create_all()


new_job = Job(
    'Full Stack Engineer',
    'Privacy',
    'https://angel.co/privacy-com/jobs/307492-full-stack-engineer',
    datetime(2018, 3, 10, tzinfo=timezone.utc)
)
new_job.listing_image = '/static/img/job_listings/privacy.jpeg'

db.session.add(new_job)

db.session.commit()
