"""Disposable v2 snapshots for audience-boundary tests; never production publication."""
from datetime import datetime, timezone
from pathlib import Path

from project.database import db
from project.learning.content_schema import load_catalog
from project.models import ContentRevision
from project.services.curriculum_service import content_checksum

CATALOG_V2 = Path(__file__).resolve().parents[1] / "curriculum/idempotency/catalog-v2.json"
PRIVATE_V2 = ("misconception-evaluator-only", "MISCONCEPTION_DESCRIPTION_SENTINEL",
              "MISCONCEPTION_EVIDENCE_SENTINEL", "MISCONCEPTION_SUGGESTION_SENTINEL", "V2_REFERENCE_SENTINEL")


def feedback_catalog():
    catalog = load_catalog(CATALOG_V2)
    assessment = catalog["items"][-1]["content"]["assessment"]
    assessment["misconceptions"][0].update(id=PRIVATE_V2[0], description=PRIVATE_V2[1],
        evidence_guidance=PRIVATE_V2[2], suggestion=PRIVATE_V2[3])
    assessment["reference_reasoning"] = [PRIVATE_V2[4]]
    return catalog


def publish_feedback_catalog():
    """Add v2 to a SQLite fixture already containing the v1 identities."""
    catalog = feedback_catalog()
    now = datetime.now(timezone.utc)
    for item in catalog["items"]:
        db.session.add(ContentRevision(item_id=item["id"], version=item["version"], schema_version=2,
            payload=item, checksum=content_checksum(item, 2), imported_at=now, published_at=now,
            reviewed_by="Disposable test fixture", reviewed_on=now.date()))
    db.session.commit()
    return catalog
