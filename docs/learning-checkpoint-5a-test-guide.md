# Checkpoint 5a: inspect the feedback foundation in a REPL

This checkpoint adds content contracts, not a feedback button. The running
preview still uses v1. These exercises load local files and change in-memory
copies; they need no database or AI credentials.

From the repository root:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

## Follow one misconception to its review question

```python
from pprint import pprint
from project.learning.content_schema import load_catalog, evaluator_view, learner_view, interviewer_view, validate_catalog

catalog = load_catalog("curriculum/idempotency/catalog-v2.json")
by_id = {item["id"]: item for item in catalog["items"]}
exercise = by_id["idempotent-order-api"]
mapping = evaluator_view(exercise)["misconceptions"][0]
pprint(mapping)
pprint(by_id[mapping["review_question_ids"][0]]["content"])
```

Identify the mistaken belief, the evidence needed to support a finding, and the
linked explanation. Notice the guidance about missing evidence and alternatives.
These are authoring rules for future feedback, not a score assigned to a learner.

## Inspect the audience boundary

```python
learner_view(exercise)["content"].keys()
interviewer_view(exercise).keys()
evaluator_view(exercise).keys()
old = load_catalog("curriculum/idempotency/catalog.json")["items"][-1]
evaluator_view(old).keys()
```

Only the v2 evaluator packet contains `misconceptions`. The v1 packet keeps its
old shape. In the live preview's Network panel, inspect a practice document or
reply response: no evaluator packet is returned. Opening
`http://127.0.0.1:5057/static/curriculum/idempotency/catalog-v2.json` returns 404;
source is not a web asset, though it remains readable in the public repository.

## Break a reference, then step through validation

```python
from copy import deepcopy
changed = deepcopy(catalog)
changed["items"][-1]["content"]["assessment"]["misconceptions"][0]["review_question_ids"] = ["idempotency:missing"]
validate_catalog(changed)  # ValidationError; the original catalog is unchanged
```

Try an unknown `dimension_id` or a duplicate mapping ID next. Then:

```python
import pdb
pdb.runcall(validate_catalog, catalog)
```

Use `n` to step, `p result["schema_version"]` after that variable is assigned, `l`
to see code, and `c` to finish. The validator checks a complete reference closure
without looking up mutable database state. Use `exit()` to leave Python.

The [curriculum contract](../curriculum/README.md) explains why all six item
versions advance while stable question IDs retain progress. PostgreSQL tests
cover publication/replay, conflicting imports, existing sessions, and an old
review attempt finishing after publication; they are separate from these REPL
experiments. Content still requires human review before publication.
