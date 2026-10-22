#!/usr/bin/env python3
"""One explicit read per public listing; no app/DB, screenshots, or storage writes.

Local result directories must be new. Never prints keys or provider error bodies.
"""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]


def validate_entry(entry):
    """The evaluation never fetches arbitrary destinations or writes arbitrary IDs."""
    if not re.fullmatch(r"[a-z0-9-]{1,80}", entry.get('id', '')):
        raise ValueError('Invalid sample id')
    parsed = urlsplit(entry['url'])
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port
            or parsed.query or parsed.fragment or len(entry['url']) > 2048):
        raise ValueError('Only reviewed public HTTPS listing URLs are allowed')
    hosts = {'gem': {'jobs.gem.com'}, 'greenhouse': {'job-boards.greenhouse.io'},
             'lever': {'jobs.lever.co'}, 'ashby': {'jobs.ashbyhq.com'}}
    if entry['profile'] == 'workday':
        allowed = re.fullmatch(r'[a-z0-9-]+\.wd[0-9]+\.myworkdayjobs\.com', parsed.hostname or '') and '/job/' in parsed.path
    else:
        allowed = parsed.hostname in hosts.get(entry['profile'], set())
    if not allowed:
        raise ValueError('Unsupported evaluation profile/host')


def recipe():
    common = (ROOT / 'project/jobwizard/browserless_capture.mjs').read_text()
    extract = (ROOT / 'project/jobwizard/browserless_extract.mjs').read_text()
    return common.replace('export default async function capture', 'async function capture') + '\n' + '\n'.join(extract.splitlines()[1:])


def run(entry, token):
    started = time.monotonic()
    result = {'id': entry['id'], 'platform': entry['profile'], 'url': entry['url']}
    def deadline(*_):
        raise TimeoutError()
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(20)
    try:
        with requests.Session() as client:
            client.trust_env = False
            with client.post('https://production-sfo.browserless.io/function',
                    params={'token': token, 'timeout': 16000},
                    json={'code': recipe(), 'context': {'profile': entry['profile'], 'url': entry['url']}},
                    timeout=(2, 17), stream=True, allow_redirects=False) as response:
                result['http_status'] = response.status_code
                if response.status_code != 200:
                    result['error'] = 'provider_http_error'
                    return result
                raw = bytearray()
                for part in response.iter_content(65536):
                    raw.extend(part)
                    if len(raw) > 1_000_000:
                        raise ValueError('too large')
                result['source'] = json.loads(raw)['data']
    except Exception as error:
        result['error'] = type(error).__name__
    finally:
        signal.alarm(0)
        result['seconds'] = round(time.monotonic() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--heroku-token', action='store_true')
    parser.add_argument('--ids', nargs='+')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    entries = json.loads(args.manifest.read_text())['listings']
    if args.ids:
        assert set(args.ids) <= {entry['id'] for entry in entries}
        entries = [entry for entry in entries if entry['id'] in args.ids]
    if len(entries) > 20 or len({entry['id'] for entry in entries}) != len(entries):
        raise SystemExit('Select at most 20 unique public samples')
    for entry in entries:
        validate_entry(entry)
    if not args.run:
        print(json.dumps({'requests': len(entries), 'ids': [entry['id'] for entry in entries]}))
        return
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    token = os.environ.get('BROWSERLESS_API_TOKEN', '')
    if args.heroku_token:
        token = subprocess.run(['heroku', 'config:get', 'BROWSERLESS_API_TOKEN', '-a', 'keithriordan'],
            check=True, capture_output=True, text=True, timeout=30).stdout.strip()
    if not token:
        raise SystemExit('Browserless credential unavailable')
    for entry in entries:
        result = run(entry, token)
        (args.output / (entry['id'] + '.json')).write_text(json.dumps(result, indent=2) + '\n')
        source = result.get('source', {})
        print(json.dumps({'id': entry['id'], 'seconds': result['seconds'], 'error': result.get('error') or source.get('error'),
            'heading': source.get('heading'), 'characters': len(source.get('description', '')),
            'jsonld_count': len(source.get('jsonld', []))}), flush=True)
        if result.get('http_status') in (400, 401, 402, 403, 429):
            break


if __name__ == '__main__':
    main()
