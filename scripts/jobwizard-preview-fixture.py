"""Disposable Jobwizard fixture at localhost:5058. Never uses real jobs/providers.

Accounts: jobs1@example.test and jobs2@example.test / JobwizardPreview123!
POST /fixture/state controls reads/writes/receipts/capture/images (success|failure),
write mode lost drops the response after commit; delay controls write latency.
GET /fixture/results includes provider/status/image counters. Optional artifact
JSON entries may include image_path for a local PNG; no provider is called.
"""
import io
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import email_validator
from flask import jsonify, request, send_file
from PIL import Image, ImageDraw
from project import create_app
from project.database import db
from project.extensions import talisman
from project.models import Gift, Job, JobCapture, JobMutationReceipt, Playlist, User
from project.services import jobwizard_capture
from project.jobwizard.capture_policy import CaptureError


def main():
    email_validator.TEST_ENVIRONMENT = True
    with tempfile.TemporaryDirectory(prefix="jobwizard-preview-") as directory:
        app = create_app(dict(TESTING=True, SECRET_KEY="fixture", JWT_SECRET_KEY="disposable-jobwizard-jwt-secret-only",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{Path(directory) / 'jobs.sqlite'}", SQLALCHEMY_TRACK_MODIFICATIONS=False,
            JWT_ACCESS_TOKEN_EXPIRES=timedelta(seconds=20), JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=1),
            WTF_CSRF_ENABLED=False, SESSION_COOKIE_SECURE=False, RATELIMIT_ENABLED=False))
        talisman.force_https = False
        mode = dict(reads="success", writes="success", receipts="success", capture="success", images="success", delay=0)
        counters = dict(image_reads=0, capture_calls=0, status_reads=0)
        # Optional real readiness artifacts: signed URLs stay outside Git. This
        # fixture reads existing images; it never calls a paid capture provider.
        artifacts_path = os.getenv("JOBWIZARD_PREVIEW_CAPTURE_RESULTS")
        artifacts = json.loads(Path(artifacts_path).read_text()) if artifacts_path else []
        signed_images = {item["artifact"]["object_key"]: item["signed_url"] for item in artifacts}
        local_images = {item["artifact"]["object_key"].split("/")[-1]: Path(item["image_path"])
                        for item in artifacts if item.get("image_path")}
        image = Image.new("RGB", (320, 1600), "#edf2f5"); draw = ImageDraw.Draw(image)
        for y in range(40, 1550, 100): draw.text((25, y), f"Saved listing preview - section {y // 100 + 1}", fill="#163744")
        image_bytes = io.BytesIO(); image.save(image_bytes, "PNG")
        with app.app_context():
            db.create_all()
            for account in (1, 2):
                user = User(id=account, username=f"Jobwizard Preview {account}", email=f"jobs{account}@example.test", email_verified=True)
                user.set_password("JobwizardPreview123!"); db.session.add(user); db.session.flush()
                db.session.add(Gift(user_id=account, title="Jobwizard regression gift", body="Disposable gift."))
                for index in range(320 if account == 1 else 3):
                    job = Job(title=f'{index + 1:03} · {"Senior accessibility engineer with a very long title" if index % 4 == 0 else "Platform engineer"}', company_name=["Acme", "Cedar Labs", "North Star", "東京 Systems"][index % 4], listing_url=f"https://job-boards.greenhouse.io/fixture/jobs/{account * 1000 + index}", user_id=account, posted_date=datetime(2020, 1, 1, tzinfo=timezone.utc))
                    if index % 7:
                        job.saved_at = datetime.now(timezone.utc) - timedelta(days=index)
                    if index % 11 == 0: job.archived_at = datetime.now(timezone.utc)
                    if index == 2: job.listing_url = "javascript:alert(1)"; job.listing_image = "/static/img/job_listings/legacy.jpeg"
                    db.session.add(job)
                if account == 1:
                    for item in artifacts:
                        job = Job(title=f'Browserless readiness · {item["profile"].title()}', company_name="Public capture verification", listing_url=item["source_url"], user_id=account, posted_date=None)
                        job.saved_at = datetime.now(timezone.utc)
                        db.session.add(job); db.session.flush()
                        db.session.add(JobCapture(id=str(uuid4()), job_id=job.id, user_id=account, source_url=job.listing_url, source_revision=0, status="succeeded", started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc), **item["artifact"]))
            db.session.add(Playlist(id="jobwizard-regression", title="Jobwizard regression playlist", description="Disposable Library catalog", published_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc)))
            db.session.commit()
        @app.post("/fixture/state")
        def state():
            payload = request.get_json(); mode.update({key: payload[key] for key in mode if key in payload}); return jsonify(mode)
        @app.get("/fixture/results")
        def results():
            return jsonify(jobs=Job.query.count(), receipts=JobMutationReceipt.query.count(), captures=JobCapture.query.count(), **counters)
        @app.get("/fixture/artifacts/<name>")
        def local_image(name):
            counters["image_reads"] += 1
            if mode["images"] == "failure": return "Unavailable", 403
            path = local_images.get(name)
            if not path: return "Missing", 404
            return send_file(path, mimetype="image/png", max_age=0)
        @app.get("/fixture/screenshot.png")
        def screenshot():
            return send_file(io.BytesIO(image_bytes.getvalue()), mimetype="image/png", max_age=0)
        @app.before_request
        def fail():
            if not request.path.startswith("/api/v1/jobwizard"):
                return None
            if request.method in {"POST", "PATCH"} and not request.path.endswith("/capture"):
                time.sleep(min(20, max(0, float(mode["delay"]))))
                if mode["writes"] == "failure": return jsonify(error="Fixture save unavailable"), 503
            if request.method == "GET":
                if request.path.endswith("/capture"): counters["status_reads"] += 1
                if "/receipts/" in request.path:
                    if mode["receipts"] == "failure": return jsonify(error="Fixture receipt unavailable"), 503
                elif mode["reads"] == "failure": return jsonify(error="Fixture read unavailable"), 503
        @app.after_request
        def lose(response):
            if request.path.startswith("/api/v1/jobwizard/jobs") and request.method in {"POST", "PATCH"} and not request.path.endswith("/capture") and response.status_code in {200, 201} and mode["writes"] == "lost":
                return jsonify(error="Fixture response lost after commit"), 503
            return response
        def artifact(url, key):
            counters["capture_calls"] += 1
            time.sleep(2)
            if mode["capture"] == "failure": raise RuntimeError("Fixture capture unavailable")
            if mode["capture"] not in {"success", "failure"}: raise CaptureError(mode["capture"])
            return dict(object_key=key, width=320, height=1600)
        storage = Mock()
        def signed_image(*args, **kwargs):
            key = kwargs["Params"]["Key"]
            url = signed_images.get(key)
            if key.split("/")[-1] in local_images:
                return f"{url}?version={uuid4()}"
            return url or f"http://127.0.0.1:5058/fixture/screenshot.png?version={uuid4()}"
        storage.generate_presigned_url.side_effect = signed_image
        with patch.object(jobwizard_capture, "configured", return_value=True), patch.object(jobwizard_capture, "bucket", return_value="fixture-private"), patch.object(jobwizard_capture, "s3_client", return_value=storage), patch.object(jobwizard_capture, "_run_capture", side_effect=artifact):
            app.run(host="127.0.0.1", port=5058, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
