"""Bounded syntax checks only. No learner code executes and no model is called.

Results contain static messages and source locations, never parser exception text
(which can quote learner content). Persist them with CHECKER_VERSION and exact revisions.
"""
import json

import yaml

CHECKER_VERSION = "syntax-1"
MAX_BYTES = 64 * 1024
MAX_DEPTH = 64
MAX_NODES = 10_000


class CheckLimit(Exception):
    def __init__(self, code):
        self.code = code


MESSAGES = {
    "passed": "Syntax parsed successfully. This does not assess the design or API contract.",
    "empty": "There is no content to check yet.",
    "unsupported": "Automatic syntax checks currently support JSON and YAML only.",
    "size": "This content exceeds the syntax check size limit.",
    "complexity": "This content exceeds the syntax check nesting or node limit.",
    "aliases": "YAML aliases are outside this check's supported subset.",
    "duplicates": "Duplicate mapping keys are outside this check's supported subset.",
    "yaml_subset": "This YAML uses a value, tag, key, or document structure this check does not support.",
    "json_syntax": "Invalid JSON syntax. Check quoting, commas, brackets, and values.",
    "yaml_syntax": "Invalid YAML syntax. Check indentation, delimiters, and quoting.",
}


def _result(status, code, line=None, column=None):
    return {"status": status, "code": code, "message": MESSAGES[code], "line": line, "column": column}


def _json_depth(body):
    depth, quoted, escaped = 0, False, False
    for char in body:
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == '"':
            quoted = True
        elif char in "[{":
            depth += 1
            if depth > MAX_DEPTH:
                raise CheckLimit("complexity")
        elif char in "]}":
            depth -= 1


def _json_pairs(pairs):
    seen = set()
    for key, _value in pairs:
        if key in seen:
            raise CheckLimit("duplicates")
        seen.add(key)
    return None  # We only validate; do not retain a second copy of the document.


def _json_constant(_value):
    # json.loads otherwise accepts NaN and Infinity, which JSON does not.
    raise CheckLimit("json_syntax")


class BoundedSafeLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self.depth = self.nodes = 0

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise CheckLimit("aliases")
        self.nodes += 1
        self.depth += 1
        if self.nodes > MAX_NODES or self.depth > MAX_DEPTH:
            raise CheckLimit("complexity")
        try:
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _value in node.value:
            key = self.construct_object(key_node, deep=deep)
            try:
                if key in seen:
                    raise CheckLimit("duplicates")
                seen.add(key)
            except TypeError:
                raise CheckLimit("yaml_subset") from None
        return super().construct_mapping(node, deep=deep)


def check_artifact(language, body):
    """Return a JSON-safe result. 'not_checked' is a checker limit, not a design failure."""
    if language not in ("json", "yaml"):
        return _result("not_checked", "unsupported")
    if len(body.encode("utf-8")) > MAX_BYTES:
        return _result("not_checked", "size")
    if not body.strip():
        return _result("not_checked", "empty")
    try:
        if language == "json":
            _json_depth(body)
            json.loads(body, parse_int=str, parse_float=str, parse_constant=_json_constant,
                       object_pairs_hook=_json_pairs)
        else:
            loader = BoundedSafeLoader(body)
            try:
                loader.get_single_data()
            finally:
                loader.dispose()
    except CheckLimit as exc:
        return _result("error" if exc.code == "json_syntax" else "not_checked", exc.code)
    except json.JSONDecodeError as exc:
        return _result("error", "json_syntax", exc.lineno, exc.colno)
    except (yaml.scanner.ScannerError, yaml.parser.ParserError) as exc:
        mark = exc.problem_mark
        return _result("error", "yaml_syntax", mark.line + 1 if mark else None, mark.column + 1 if mark else None)
    except (yaml.YAMLError, ValueError, TypeError):
        return _result("not_checked", "yaml_subset")
    except RecursionError:
        return _result("not_checked", "complexity")
    return _result("passed", "passed")
