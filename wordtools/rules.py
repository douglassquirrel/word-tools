"""The rules file of check-tags: read it, and refuse anything in it that is not understood."""

import json

from wordtools.content import tag_kind


class RulesError(Exception):
    """A JSON file of rules or settings cannot be used. The message says why."""


def read_json_object(path):
    """The JSON object in the file at `path`."""
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        raise RulesError(f"{path}: no such file") from None
    except OSError as error:
        raise RulesError(f"{path}: cannot be read: {error.strerror}") from None
    except UnicodeDecodeError:
        raise RulesError(f"{path}: not UTF-8 text") from None
    except json.JSONDecodeError as error:
        raise RulesError(
            f"{path}: not valid JSON (line {error.lineno}, column {error.colno}): {error.msg}"
        ) from None
    if not isinstance(data, dict):
        raise RulesError(f"{path}: must be a JSON object")
    return data


def rule_key(kind, variant):
    """The name a rule for this kind and variant goes by: one spelling, for comparing."""
    key = tag_kind(kind)
    return f"{key}, {tag_kind(variant)}" if variant and variant.strip() else key


def _spelled(name):
    kind, _, variant = name.partition(",")
    return rule_key(kind, variant)


def _is_text(value, key, where):
    if not isinstance(value, str):
        raise RulesError(f'{where}"{key}" must be a text')


def _is_texts(value, key, where):
    if not (isinstance(value, list) and all(isinstance(item, str) for item in value)):
        raise RulesError(f'{where}"{key}" must be a list of texts')


def _is_flag(value, key, where):
    if not isinstance(value, bool):
        raise RulesError(f'{where}"{key}" must be true or false')


def _is_inches(value, key, where):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RulesError(f'{where}"{key}" must be a number of inches')


def _is_indent(value, key, where):
    if not isinstance(value, dict):
        raise RulesError(f'{where}"{key}" must be an object')
    for side, inches in value.items():
        if side not in ("left", "right", "first_line"):
            raise RulesError(f'{where}"{key}": unknown key "{side}"')
        _is_inches(inches, side, f'{where}"{key}": ')


KIND_KEYS = {
    "font": _is_text,
    "not_fonts": _is_texts,
    "indent": _is_indent,
    "skip_numbered": _is_flag,
    "first_line_after_first": _is_inches,
}
PARAGRAPH_KEYS = {"indent": _is_indent, "skip": _is_flag}


def _is_rule(rule, keys, where):
    for key, value in rule.items():
        if key not in keys:
            raise RulesError(f'{where}unknown key "{key}"')
        keys[key](value, key, where)


def _exceptions(name, entries, keys, path):
    if not (isinstance(entries, list) and all(isinstance(entry, dict) for entry in entries)):
        raise RulesError(f'{path}: "{name}" must be a list of objects')
    for number, entry in enumerate(entries, 1):
        where = f"{path}: {name}[{number}]: "
        start = entry.get("starts_with")
        if not (isinstance(start, str) and start):
            raise RulesError(f'{where}"starts_with" must be a text that is not empty')
        others = {key: value for key, value in entry.items() if key != "starts_with"}
        if keys is PARAGRAPH_KEYS and not others:
            raise RulesError(f'{where}needs "indent" or "skip"')
        _is_rule(others, keys, where)


def _kinds(kinds, path):
    if not isinstance(kinds, dict):
        raise RulesError(f'{path}: "kinds" must map each kind to its rule')
    for name, rule in kinds.items():
        if not isinstance(rule, dict):
            raise RulesError(f'{path}: kind "{name}" must be an object')
        _is_rule(rule, KIND_KEYS, f'{path}: kind "{name}": ')
    return {_spelled(name): rule for name, rule in kinds.items()}


def _only_inside(only_inside, path):
    said = f'{path}: "only_inside" must map each font to a list of kinds'
    if not isinstance(only_inside, dict):
        raise RulesError(said)
    for kinds in only_inside.values():
        if not (isinstance(kinds, list) and all(isinstance(kind, str) for kind in kinds)):
            raise RulesError(said)
    return {font: [_spelled(kind) for kind in kinds] for font, kinds in only_inside.items()}


def load_rules(path):
    """The rules in the file at `path`, every key present; a RulesError if any is faulty."""
    given = read_json_object(path)
    where = f"{path}: "
    known = {
        "open", "close", "allowed", "heading_styles", "tag_font", "default_font", "only_inside",
        "kinds", "skip_boxes_starting", "box_exceptions", "paragraph_exceptions",
    }  # fmt: skip
    for key in given:
        if key not in known:
            raise RulesError(f'{where}unknown key "{key}"')
    for key in ("open", "close", "allowed"):
        if key not in given:
            raise RulesError(f'{where}"{key}" is missing')
    for key in ("open", "close"):
        if not (isinstance(given[key], str) and given[key].strip()):
            raise RulesError(f'{where}"{key}" must be a word')
    if given["open"].lower() == given["close"].lower():
        raise RulesError(f'{where}"open" and "close" must differ')
    _is_texts(given["allowed"], "allowed", where)
    if not given["allowed"]:
        raise RulesError(f'{where}"allowed" must name at least one tag')
    _is_texts(given.get("heading_styles", []), "heading_styles", where)
    for key in ("tag_font", "default_font"):
        if given.get(key) is not None:
            _is_text(given[key], key, where)
    starts = given.get("skip_boxes_starting", [])
    if not (isinstance(starts, list) and all(isinstance(s, str) and s for s in starts)):
        raise RulesError(f'{where}"skip_boxes_starting" must be a list of texts that are not empty')
    kinds = _kinds(given.get("kinds", {}), path)
    only_inside = _only_inside(given.get("only_inside", {}), path)
    boxes = given.get("box_exceptions", [])
    paragraphs = given.get("paragraph_exceptions", [])
    _exceptions("box_exceptions", boxes, KIND_KEYS, path)
    _exceptions("paragraph_exceptions", paragraphs, PARAGRAPH_KEYS, path)
    fonts_wanted = [rule for rule in [*kinds.values(), *boxes] if "font" in rule]
    if (given.get("tag_font") or fonts_wanted) and not given.get("default_font"):
        raise RulesError(
            f'{where}"default_font" is needed by "tag_font" and "font",'
            " to judge a run with no font of its own"
        )
    return {
        "open": given["open"],
        "close": given["close"],
        "allowed": given["allowed"],
        "heading_styles": given.get("heading_styles", []),
        "tag_font": given.get("tag_font"),
        "default_font": given.get("default_font"),
        "only_inside": only_inside,
        "kinds": kinds,
        "skip_boxes_starting": starts,
        "box_exceptions": boxes,
        "paragraph_exceptions": paragraphs,
    }
