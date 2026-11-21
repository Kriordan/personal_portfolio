"""Deterministic evaluation contract cases; these test plumbing, not live model quality."""
import json

RACE = "Check for an existing receipt, then insert the order. No constraint or lock is needed."
ALTERNATIVE = "Use a durable processing claim with a fencing token; expired owners cannot complete."
DISCOVERY = "I will scope the key to the authenticated tenant and operation."


def scripted_feedback(body):
    material = json.loads(body["input"])
    sources = [a for a in material["artifacts"] if a.get("source_id")]
    sources += [{"source_id": t["source_id"], "body": t["body"]} for t in material["transcript"] if "source_id" in t]
    sources += [{"source_id": n["source_id"], "body": n["text"]} for n in material["brief"]["entries"]]
    def evidence(text):
        return [{"source_id": s["source_id"], "quote": text} for s in sources if text in s["body"]][:1]
    findings = [{"kind": "not_observed", "dimension_id": d["id"], "title": "Explain this part of the design",
                 "explanation": "The saved work does not yet demonstrate this dimension.",
                 "next_step": "State your assumption and trace a concrete request through the design.",
                 "evidence": [], "misconception_ids": []}
                for d in material["exercise"]["brief"]["assessment_dimensions"]]
    by_dimension = {f["dimension_id"]: f for f in findings}
    if evidence(DISCOVERY):
        by_dimension["discovery"].update(kind="strength", title="Explicit request scope", evidence=evidence(DISCOVERY),
            explanation="You have identified who owns the request identity.", next_step="Explain how a conflicting payload is handled.")
    if evidence(RACE):
        by_dimension["correctness"].update(kind="concern", title="Two first attempts can both pass the check",
            explanation="Both requests can observe no receipt before either inserts an order. The stated absence of coordination leaves a race.",
            next_step="Interleave two first attempts and identify a database-enforced conflict boundary.", evidence=evidence(RACE),
            misconception_ids=["check-then-insert-is-safe"] if material["assessment"].get("misconceptions") else [])
    elif evidence(ALTERNATIVE):
        by_dimension["correctness"].update(kind="strength", title="Explicit stale-owner protection", evidence=evidence(ALTERNATIVE),
            explanation="Your alternative addresses an old owner completing after recovery.", next_step="Show how the fencing check and completion are committed together.")
        by_dimension["judgment"].update(kind="tradeoff", title="Recovery requires ownership machinery", evidence=evidence(ALTERNATIVE),
            explanation="A durable claim can span longer work, with extra recovery state to operate.", next_step="Compare that cost with the expected duration of the operation.")
    return {"summary": "Review the evidence and use the next steps to revise your design.", "findings": findings}
