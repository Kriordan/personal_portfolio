# Checkpoint 1: explore it in the Python REPL

Pick one five-minute experiment. Predict the result, inspect it, then explain any surprise. These examples read the catalog and change in-memory copies; they need no database or AI credentials.

From the repository root:

```sh
PYTHON_DOTENV_DISABLED=1 AWS_EC2_METADATA_DISABLED=true poetry run python
```

## Inspect real objects

```python
from pprint import pprint
from copy import deepcopy
from project.learning.content_schema import load_catalog, validate_catalog, learner_view, facilitator_view

catalog = load_catalog("curriculum/idempotency/catalog.json")
[(item["id"], item["kind"], item["version"]) for item in catalog["items"]]
exercise = next(item for item in catalog["items"] if item["kind"] == "exercise")
pprint(exercise["content"].keys())
pprint(learner_view(exercise)["content"].keys())
```

Which fields disappeared? Inspect `exercise["content"]["brief"]`. The learner projection includes the exercise brief; hidden constraints and evaluation material stay out of it.

## Change one input

```python
facilitator_view(exercise)["revealed_constraints"]
facilitator_view(exercise, revealed_constraint_ids=["scope"])["revealed_constraints"]
facilitator_view(exercise, revealed_constraint_ids=["invented"])
```

Expect an empty list, one approved fact, then a `ValidationError`. Read the traceback to find the rejecting function; the REPL remains usable after the exception.

```python
changed = deepcopy(catalog)
changed["items"][0]["version"] = True
validate_catalog(changed)
```

Why reject `True` even though `isinstance(True, int)` is true? Find `PositiveInteger` in `project/learning/content_schema.py`.

## Step through a function

```python
import inspect, pdb
print(inspect.signature(learner_view))
pdb.runcall(learner_view, exercise)
```

At `(Pdb)`, try `l` to list code, `p item["kind"]` to inspect a value, `n` to step over, and `c` to continue. Use `q` to quit the debugger; `exit()` leaves Python.

Optional: import `content_checksum` from `project.services.curriculum_service`. Compare the checksum of `exercise` with a deep copy, then change the copy's title and compare again. Explain why an unchanged ID/version does not guarantee unchanged content.
