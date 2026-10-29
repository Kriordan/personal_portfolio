"""Interviewer evaluation: reviewed cases run through the interviewer's real request builders.

Each case (tests/fixtures/interviewer/cases.json) sends one learner message to the selector
and then the reply, as a session would, and checks:

- the selector's answer against what the case expects;
- that each request carries only what its call may see: cues for the selector; revealed
  facts, and a hint only when asked, for the reply; evaluation material for neither;
- that the reply is valid and repeats no unrevealed fact and no reference reasoning.

`flask learning-eval` runs every case against the scripted fake provider, which answers as
each case expects (so CI tests the plumbing and the request checks), or against OpenAI with
Learning's key (so activation tests the model). Live results go to docs/evaluations/ with
the outputs, latency, tokens, and cost.
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from flask import current_app
from flask.cli import with_appcontext

from project.curriculum_terms import CURRENT_PROFILES, FORMAT_LANGUAGES
from project.learning import interviewer
from project.learning.content_schema import evaluator_view, learner_view, load_catalog, selector_view

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests/fixtures/interviewer/cases.json"
CATALOG = ROOT / "curriculum/idempotency/catalog.json"
FAKE_REPLY = "What would you check first, and why?"


def load_cases(path=CASES):
    data = json.loads(Path(path).read_text())
    ids = [case["id"] for case in data["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case IDs must be unique.")
    return data


def exercise(exercise_id, catalog=CATALOG):
    return next(item for item in load_catalog(catalog)["items"] if item["id"] == exercise_id)


def case_context(item, case, settings, *, profile_version):
    """The same inputs a session would pin for this case's message."""
    brief = learner_view(item)["content"]["brief"]
    facilitator = item["content"]["facilitator"]
    specs = {spec["id"]: spec for spec in brief["expected_artifacts"]}
    revealed_before, hints_given = list(case.get("revealed_before", [])), case.get("hints_given", 0)
    transcript = [{"sequence": 1, "role": "interviewer", "body": facilitator["opening_prompt"]}]
    for turn in [*case.get("transcript", []), {"role": "learner", "body": case["message"]}]:
        transcript.append({"sequence": len(transcript) + 1, "role": turn["role"], "body": turn["body"]})
    return {
        "session_id": None, "profile_version": profile_version, "model": settings["model"],
        "selector_model": settings["selector_model"], "context_from_sequence": 1,
        "exercise": {"title": item["title"], "brief": brief},
        "selector": {"message": case["message"], "hidden": selector_view(item, revealed_constraint_ids=revealed_before),
                     "hints_left": hints_given < len(facilitator["permitted_hints"])},
        "revealed_before": revealed_before, "hints_given": hints_given,
        "brief": {"revision": 1 if case.get("brief") else 0, "entries": case.get("brief", [])},
        "artifacts": [{"artifact_id": artifact_id, "title": specs[artifact_id]["title"], "revision": 1,
                       "language": FORMAT_LANGUAGES[specs[artifact_id]["format"]][0], "body": body}
                      for artifact_id, body in sorted(case.get("artifacts", {}).items())],
        "transcript": transcript,
    }


def _strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for inner in value.values():
            yield from _strings(inner)
    elif isinstance(value, list):
        for inner in value:
            yield from _strings(inner)


def _private(item):
    """Everything no call may see, and what each call may see only under conditions."""
    facilitator = item["content"]["facilitator"]
    return {
        "facts": {entry["id"]: entry["fact"] for entry in facilitator["hidden_constraints"]},
        "cues": [cue for entry in facilitator["hidden_constraints"] for cue in entry["clarification_cues"]],
        "hints": list(facilitator["permitted_hints"]),
        "instructions": list(facilitator["instructions"]),
        "evaluation": [text for text in _strings(evaluator_view(item)) if len(text) >= 20],
    }


def _words(text):
    return re.findall(r"[a-z0-9,]+", text.lower())


def _overlap(text, source, size):
    """Whether `text` repeats any run of `size` words from `source`."""
    words, runs = _words(text or ""), _words(source)
    shingles = {tuple(runs[index:index + size]) for index in range(len(runs) - size + 1)}
    return any(tuple(words[index:index + size]) in shingles for index in range(len(words) - size + 1))


def _numbers(text):
    """The numbers in `text`, written without separators: "2,000," and "2000" are the same number."""
    return {number.rstrip(",").replace(",", "") for number in re.findall(r"\d[\d,]*", text or "")}


def _visible(body):
    """What a model reads from a request: its instructions and every string in its input, decoded,
    so text with quotes or line breaks is matched as written rather than as escaped JSON."""
    return "\n".join([body["instructions"], *_strings(json.loads(body["input"]))])


def _call(provider, body, settings):
    """One provider call: its output (or None), and what it cost in time and tokens."""
    from project.services import practice_budget
    from project.services.practice_worker import ProviderError
    started = time.monotonic()
    record = {"schema": body["text"]["format"]["name"], "model": body["model"]}
    try:
        result = provider.call(body, deadline=settings["call_seconds"])
    except ProviderError as error:
        record.update(error=error.code, seconds=round(time.monotonic() - started, 3), usage=error.usage)
        return None, record
    usage = result.get("usage")
    rates, _ = practice_budget._rates(settings["provider"], body["model"], settings["tier"])
    tokens = practice_budget._tokens(usage)
    record.update(seconds=round(time.monotonic() - started, 3), usage=usage,
                  spawn_seconds=result.get("spawn_seconds"),
                  cost_microusd=practice_budget.cost(rates, **tokens) if rates and tokens else None)
    return result.get("output"), record


def run_case(provider, item, case, settings, *, profile_version):
    """One case: the selector, then the reply. Every expectation comes from the case and the
    exercise, never from the builders being checked."""
    private, context = _private(item), case_context(item, case, settings, profile_version=profile_version)
    learner_text = " ".join([case["message"], *case.get("artifacts", {}).values(),
                             *(entry.get("text", "") for entry in case.get("brief", []))])
    record = {"id": case["id"], "message": case["message"], "expect": case["expect"], "checks": {}, "calls": []}
    checks = record["checks"]
    revealed_before, hints_given = set(case.get("revealed_before", [])), case.get("hints_given", 0)
    hidden = [constraint_id for constraint_id in private["facts"] if constraint_id not in revealed_before]
    hints_left = hints_given < len(private["hints"])
    selection = {"constraint_ids": [], "hint_requested": False}
    selector = interviewer.selector_request(context, settings)
    if selector is None:
        checks["selector_offers_what_is_hidden"] = not hidden and not hints_left
    else:
        properties = selector["text"]["format"]["schema"]["properties"]
        checks["selector_offers_what_is_hidden"] = (
            properties.get("constraint_ids", {}).get("items", {}).get("enum", []) == hidden
            and ("hint_requested" in properties) == hints_left)
        revealed_cues = [cue for entry in item["content"]["facilitator"]["hidden_constraints"]
                         if entry["id"] in revealed_before for cue in entry["clarification_cues"]
                         if cue not in learner_text]
        shown = _visible(selector)
        checks["selector_sees_cues_only"] = not any(
            text in shown for text in [*private["facts"].values(), *private["hints"], *private["instructions"],
                                       *private["evaluation"], *revealed_cues])
        output, call = _call(provider, selector, settings)
        record["calls"].append(call)
        try:
            selection = interviewer.parse_selection(output, context)
            checks["selector_valid"] = True
        except interviewer.InvalidOutput:
            checks["selector_valid"] = False
            return record
    record["selection"] = selection
    checks["selector_matches"] = (sorted(selection["constraint_ids"]) == sorted(case["expect"]["constraint_ids"])
                                  and selection["hint_requested"] == case["expect"]["hint_requested"])
    newly = set(selection["constraint_ids"]) - revealed_before
    hint_index = hints_given if selection["hint_requested"] and hints_left else None
    body = interviewer.reply_request(context, interviewer.facilitator(item, context, selection), settings)
    shown, material = _visible(body), json.loads(body["input"])
    allowed = revealed_before | newly
    unrevealed = [fact for constraint_id, fact in private["facts"].items() if constraint_id not in allowed]
    other_hints = [hint for index, hint in enumerate(private["hints"]) if index != hint_index]
    checks["reply_sees_only_what_it_may"] = not any(
        text in shown for text in [*unrevealed, *other_hints, *private["evaluation"],
                                   *(cue for cue in private["cues"] if cue not in learner_text)])
    checks["reply_carries_what_was_earned"] = (
        set(material.get("revealed_facts", [])) == {private["facts"][item_id] for item_id in revealed_before}
        and set(material.get("newly_revealed_facts", [])) == {private["facts"][item_id] for item_id in newly}
        and material.get("hint") == (private["hints"][hint_index] if hint_index is not None else None))
    output, call = _call(provider, body, settings)
    record["calls"].append(call)
    reply = output.get("reply") if isinstance(output, dict) else None
    record["reply"] = reply
    checks["reply_valid"] = isinstance(reply, str) and 0 < len(reply.strip()) <= interviewer.REPLY_MAX_CHARS
    known = " ".join([learner_text, json.dumps(context["exercise"], ensure_ascii=False),
                      *(private["facts"][item_id] for item_id in allowed)])
    checks["reply_reveals_nothing_unearned"] = not any(
        _overlap(reply, fact, 5) or (_numbers(fact) - _numbers(known)) & _numbers(reply) for fact in unrevealed)
    checks["reply_shares_no_reference_reasoning"] = not any(_overlap(reply, text, 8) for text in private["evaluation"])
    return record


def run(provider_for_case, cases, item, settings, *, profile_version=CURRENT_PROFILES["interviewer"]):
    """Run each case with the provider `provider_for_case(case)` returns. Returns the full results."""
    results = [run_case(provider_for_case(case), item, case, settings, profile_version=profile_version)
               for case in cases]
    names = sorted({name for result in results for name in result["checks"]})
    summary = {name: {"passed": sum(1 for result in results if result["checks"].get(name) is True),
                      "of": sum(1 for result in results if name in result["checks"])} for name in names}
    calls = [call for result in results for call in result["calls"]]
    return {"profile_version": profile_version, "provider": settings["provider"], "model": settings["model"],
            "selector_model": settings["selector_model"], "service_tier": settings["tier"],
            "run_at": datetime.now(timezone.utc).isoformat(), "summary": summary,
            "passed": all(all(result["checks"].values()) for result in results),
            "cost_microusd": sum(call.get("cost_microusd") or 0 for call in calls),
            "tokens": {key: sum((call.get("usage") or {}).get(key) or 0 for call in calls)
                       for key in ("input_tokens", "cached_input_tokens", "output_tokens")},
            "cases": results}


def scripted_provider(case):
    """The fake provider, answering as the case expects."""
    from project.services.practice_worker import FakeProvider
    return FakeProvider(selections=[case["expect"]], replies=[FAKE_REPLY])


@click.command("learning-eval")
@click.option("--provider", "provider_name", type=click.Choice(["fake", "openai"]), default="fake",
              help="fake checks the plumbing; openai calls the live model with LEARNING_OPENAI_API_KEY.")
@click.option("--case", "case_ids", multiple=True, help="Run only these case IDs.")
@click.option("--output", type=click.Path(dir_okay=False), help="Where to write the JSON results.")
@with_appcontext
def learning_eval_command(provider_name, case_ids, output):
    """Run the interviewer's evaluation cases. Exits with an error if any check fails."""
    from project.services import practice_service
    data = load_cases()
    unknown = set(case_ids) - {case["id"] for case in data["cases"]}
    if unknown:
        raise click.ClickException(f"No such case: {', '.join(sorted(unknown))}.")
    cases = [case for case in data["cases"] if not case_ids or case["id"] in case_ids]
    settings = dict(practice_service.ai_settings(), provider=provider_name)
    if provider_name == "fake":
        settings.update(model="fake-interviewer", selector_model="fake-interviewer")
        provider_for_case = scripted_provider
    else:
        from project.services.learning_ai_provider import OpenAIProvider
        if not settings["model"]:
            raise click.ClickException("Set LEARNING_AI_MODEL (and optionally LEARNING_AI_SELECTOR_MODEL) first.")
        provider = OpenAIProvider(base_url=settings["base_url"])
        provider_for_case = lambda case: provider  # noqa: E731
    results = run(provider_for_case, cases, exercise(data["exercise_id"]), settings)
    if provider_name == "openai" and not output:
        output = ROOT / "docs/evaluations" / f"learning-interviewer-{datetime.now(timezone.utc):%Y-%m-%d}.json"
    if output:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        Path(output).write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
        click.echo(f"Results: {output}")
    for name, count in results["summary"].items():
        click.echo(f"{name}: {count['passed']} of {count['of']}")
    if not results["passed"]:
        current_app.logger.warning("Learning evaluation found failing checks.")
        sys.exit(1)
