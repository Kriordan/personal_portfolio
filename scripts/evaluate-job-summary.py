#!/usr/bin/env python3
"""Explicit local evaluation: public text only, bounded calls, no paid retries.

Run normalization without --run first. Output must be a new directory. Credentials
are loaded into memory from the ignored .env; provider errors never print bodies.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import time

from dotenv import dotenv_values
import requests

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("job_extraction", ROOT / "project/jobwizard/extraction.py")
extraction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extraction)


def request_summary(source, key, model, deadline_seconds):
    started = time.monotonic()
    result = {"requested_model": model, "prompt_version": extraction.PROMPT_VERSION,
              "parser_version": extraction.PARSER_VERSION, "source_hash": source["source_hash"],
              "prompt_sha256": hashlib.sha256(extraction.SUMMARY_PROMPT.encode()).hexdigest(),
              "schema_sha256": hashlib.sha256(json.dumps(extraction.SUMMARY_SCHEMA, sort_keys=True).encode()).hexdigest()}

    def deadline(*_):
        raise TimeoutError()
    old_handler = signal.signal(signal.SIGALRM, deadline)
    signal.alarm(deadline_seconds)
    try:
        with requests.Session() as client:
            client.trust_env = False
            with client.post("https://api.openai.com/v1/responses",
                    headers={"Authorization": "Bearer " + key},
                    json=extraction.summary_request(source, model), timeout=(2, deadline_seconds - 1),
                    stream=True, allow_redirects=False) as response:
                result["http_status"] = response.status_code
                raw = bytearray()
                for part in response.iter_content(65536):
                    raw.extend(part)
                    if len(raw) > 250_000:
                        raise ValueError("response_too_large")
                data = json.loads(raw)
                if response.status_code != 200:
                    error = data.get("error", {})
                    # Only machine codes; no arbitrary provider message/request data.
                    result["error"] = "provider_http_error"
                    result["error_code"] = error.get("code")
                    result["error_type"] = error.get("type")
                    return result
                result.update({key: data.get(key) for key in ("model", "status", "usage", "incomplete_details")})
                content = [part for item in data.get("output", []) if item.get("type") == "message" for part in item.get("content", [])]
                if any(part.get("type") == "refusal" for part in content):
                    result["error"] = "refused"
                    return result
                text = "".join(part.get("text", "") for part in content if part.get("type") == "output_text")
                if data.get("status") != "completed":
                    result["error"] = "incomplete"
                    return result
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    # Only generated output from public/synthetic input, never
                    # credentials or arbitrary HTTP error bodies. Keep failures
                    # inspectable without silently repairing malformed JSON.
                    result["invalid_output_text"] = text
                    raise
                result["raw_summary"] = value
                result["validated"] = extraction.validate_summary(value, source)
    except Exception as error:
        result["error"] = type(error).__name__
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)
        result["seconds"] = round(time.monotonic() - started, 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ids", nargs="+")
    parser.add_argument("--model", default="gpt-6-luna")
    parser.add_argument("--deadline", type=int, default=12, choices=range(5, 31))
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()
    records = []
    for path in sorted(args.sources.glob("*.json")):
        record = json.loads(path.read_text())
        if args.ids and record["id"] not in args.ids:
            continue
        if record.get("error") or record.get("source", {}).get("error"):
            continue
        source = extraction.normalize_source(record["source"], record["url"], record["platform"])
        records.append((record, source))
    if len(records) > 20:
        raise SystemExit("At most 20 explicitly selected samples per run")
    if not args.run:
        for record, source in records:
            print(json.dumps({"id": record["id"], "fields": source["fields"], "warnings": source["warnings"],
                              "characters": sum(len(b["text"]) for b in source["blocks"])}))
        return
    key = os.environ.get("OPENAI_API_KEY") or dotenv_values(ROOT / ".env").get("OPENAI_API_KEY")
    if not key:
        raise SystemExit("OpenAI credential unavailable")
    args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
    for record, source in records:
        result = request_summary(source, key, args.model, args.deadline)
        result.update({"id": record["id"], "url": record["url"], "source": source})
        (args.output / (record["id"] + ".json")).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({key: result.get(key) for key in ("id", "model", "seconds", "http_status", "error", "error_code", "error_type", "usage")}), flush=True)
        if result.get("http_status") in (400, 401, 402, 403, 404, 429):
            break


if __name__ == "__main__":
    main()
