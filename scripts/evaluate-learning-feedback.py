"""Run synthetic feedback cases through a named disposable PostgreSQL database.

Keep the same DB across rounds so the $2 cap includes earlier/uncertain calls.
Only --provider openai reads Learning's key; no production data or endpoints are used.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

os.environ["PYTHON_DOTENV_DISABLED"] = "1"
os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from project import create_app
from project.database import db
from project.learning import evaluator, feedback_eval as review
from project.services import feedback_service
from project.services.learning_ai_provider import OpenAIProvider
from project.services.practice_worker import FakeProvider
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database-url', required=True)
    parser.add_argument('--provider', choices=('fake', 'openai'), default='fake')
    parser.add_argument('--case', action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    review.guard_url(args.database_url, args.provider)
    document = review.load_cases()
    selected = [c for c in document['cases'] if not args.case or c['id'] in args.case]
    if set(args.case) - {c['id'] for c in document['cases']}:
        parser.error('Unknown case ID')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite results or implicitly repeat a paid run after losing confirmation.
    with args.output.open('x') as handle:
        handle.write('{}\n')
    if args.provider == 'openai':
        from dotenv import dotenv_values
        key = os.environ.get('LEARNING_OPENAI_API_KEY') or dotenv_values(ROOT / '.env').get('LEARNING_OPENAI_API_KEY')
        if not key:
            parser.error('Set LEARNING_OPENAI_API_KEY')
        os.environ['LEARNING_OPENAI_API_KEY'] = key
    app = create_app(dict(TESTING=True, SECRET_KEY='synthetic-feedback-evaluation', SQLALCHEMY_DATABASE_URI=args.database_url,
        LEARNING_AI_ENABLED=True, LEARNING_AI_OWNER_EMAIL=review.OWNER, LEARNING_AI_PROVIDER=args.provider,
        LEARNING_AI_MODEL='gpt-6.1-sol' if args.provider == 'openai' else 'fake-interviewer',
        LEARNING_AI_FEEDBACK_MODEL='gpt-6.1-sol' if args.provider == 'openai' else 'fake-interviewer',
        LEARNING_AI_FEEDBACK_REASONING_EFFORT='medium', LEARNING_AI_FEEDBACK_MAX_OUTPUT_TOKENS=4000,
        LEARNING_AI_MONTHLY_CAP_USD=2, LEARNING_AI_WARN_USD=1.5, LEARNING_AI_CONTEXT_BYTES=524288,
        LEARNING_AI_CALL_SECONDS=60, LEARNING_AI_SERVICE_TIER='default'))
    provider = OpenAIProvider() if args.provider == 'openai' else FakeProvider()
    with app.app_context(), db.engine.connect() as lock:
        if not lock.execute(text('SELECT pg_try_advisory_lock(:a, :b)'), dict(a=review.LOCK[0], b=review.LOCK[1])).scalar():
            raise RuntimeError('Another evaluation is using this database; do not overlap runs.')
        try:
            review.seed()
            if db.session.execute(text("SELECT count(*) FROM ai_request WHERE status IN ('pending','running')")).scalar():
                raise RuntimeError('An earlier attempt is unresolved; inspect it before making more calls.')
            result = dict(run_at=datetime.now(timezone.utc).isoformat(), profile_version=evaluator.PROFILE,
                git_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                fixtures_sha256=hashlib.sha256(review.CASES.read_bytes()).hexdigest(),
                profile_sha256=hashlib.sha256(json.dumps(evaluator.PROFILES[evaluator.PROFILE]).encode()).hexdigest(),
                settings=feedback_service.settings(), total_cap_microusd=review.CAP_MICROUSD,
                spent_before_microusd=review.total_committed(), cases=[], in_progress=None)
            def save():
                temp = args.output.with_suffix('.tmp')
                temp.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
                temp.replace(args.output)
            def started(record):
                result['in_progress'] = record
                save()
            for case in selected:
                record = review.run_case(document, case, provider, before_call=started)
                result['cases'].append(record)
                result['in_progress'] = None
                result['all_review_charges'] = review.charges()
                result['total_committed_microusd'] = review.total_committed()
                save()
                print(case['id'], record['result']['request']['status'], record['result']['request']['reason'],
                      f"total=${result['total_committed_microusd']/1_000_000:.6f}", flush=True)
                if not record['checks']['one_call'] or record['result']['request']['reason'] in ('provider_auth', 'provider_quota'):
                    break
            print('Results:', args.output, flush=True)
        finally:
            db.session.remove()
            lock.execute(text('SELECT pg_advisory_unlock(:a, :b)'), dict(a=review.LOCK[0], b=review.LOCK[1]))


if __name__ == '__main__':
    main()
