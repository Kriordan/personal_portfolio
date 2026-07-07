from datetime import datetime, timezone

from project import db
from project.models import Job, User


# db.create_all()


owner = db.session.execute(
    db.select(User).order_by(User.is_admin.desc(), User.id.asc())
).scalars().first()
if owner is None:
    raise SystemExit("Create a user before seeding jobs; jobs are user-owned.")

new_job = Job(
    'Full Stack Engineer',
    'Privacy',
    'https://angel.co/privacy-com/jobs/307492-full-stack-engineer',
    datetime(2018, 3, 10, tzinfo=timezone.utc),
    owner.id,
)
new_job.listing_image = '/static/img/job_listings/privacy.jpeg'

db.session.add(new_job)

db.session.commit()
