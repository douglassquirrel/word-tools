"""The settings files of check-manuscript: read them, later files winning key by key, and
refuse anything in them that is not understood."""

import re

from wordtools.rules import RulesError, read_json_object


def _is_text(value, key, where):
    if not (isinstance(value, str) and value):
        raise RulesError(f'{where}"{key}" must be a text')


def _is_texts(value, key, where):
    if not (isinstance(value, list) and all(isinstance(item, str) and item for item in value)):
        raise RulesError(f'{where}"{key}" must be a list of texts')


def _is_whole(value, key, where):
    if type(value) is not int or value < 0:
        raise RulesError(f'{where}"{key}" must be a whole number')


def _is_flag(value, key, where):
    if not isinstance(value, bool):
        raise RulesError(f'{where}"{key}" must be true or false')


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_inches(value, key, where):
    if not _is_number(value):
        raise RulesError(f'{where}"{key}" must be a number of inches')


def _is_regex(value, key, where):
    _is_text(value, key, where)
    try:
        re.compile(value)
    except re.error as error:
        raise RulesError(f'{where}"{key}" is a bad regular expression: {error}') from None


def _is_spacing(value, key, where):
    if type(value) is not int or value <= 0:
        raise RulesError(f'{where}"{key}" must be a whole number of 240ths of a line')


def _is_page(value, key, where):
    named = value in ("letter", "a4")
    sized = isinstance(value, list) and len(value) == 2 and all(_is_number(v) for v in value)
    if not (named or sized):
        raise RulesError(f'{where}"{key}" must be "letter", "a4" or [width, height] in inches')


def _is_empty_setting(value, key, where):
    if value not in (True, False, "note"):
        raise RulesError(f'{where}"{key}" must be true, false or "note"')


def _is_range(value, key, where):
    ordered = (
        isinstance(value, list)
        and len(value) == 2
        and all(type(item) is int for item in value)
        and value[0] <= value[1]
    )
    if not ordered:
        raise RulesError(f'{where}"{key}" must be [lowest, highest]')


def _has(given, keys, required, where):
    """Check an object's keys: `keys` maps each to its check; `required` must be there."""
    for key in given:
        if key not in keys:
            raise RulesError(f'{where}unknown key "{key}"')
    for key in required:
        if key not in given:
            raise RulesError(f'{where}"{key}" is missing')
    for key, value in given.items():
        keys[key](value, key, where)


def _is_object(value, key, where):
    if not isinstance(value, dict):
        raise RulesError(f'{where}"{key}" must be an object')


def _is_tag_pairs(value, key, where):
    _is_object(value, key, where)
    keys = {"open": _is_text, "close": _is_text, "kinds": _is_texts, "required": _is_texts}
    _has(value, keys, ("open", "close", "kinds"), f"{where}tag_pairs: ")
    if value["open"].lower() == value["close"].lower():
        raise RulesError(f'{where}tag_pairs: "open" and "close" must differ')


def _is_figures(value, key, where):
    _is_object(value, key, where)
    keys = {"callout": _is_regex, "caption": _is_regex, "credit": _is_regex}
    keys.update(expect=_is_whole, caption_no_full_stop=_is_flag)
    _has(value, keys, ("callout", "caption", "credit"), f"{where}figures: ")


def _is_list_of_figures(value, key, where):
    _is_object(value, key, where)
    keys = {"from": _is_text, "to": _is_text, "entry": _is_text}
    _has(value, keys, ("from", "to"), f"{where}list_of_figures: ")


def _is_counts(value, key, where):
    if not (isinstance(value, list) and all(isinstance(item, dict) for item in value)):
        raise RulesError(f'{where}"{key}" must be a list of objects')
    keys = {"name": _is_text, "pattern": _is_regex, "expect": _is_whole}
    keys.update({"min": _is_whole, "max": _is_whole, "placeholder": _is_flag})
    for number, entry in enumerate(value, 1):
        if "name" not in entry:
            raise RulesError(f'{where}counts[{number}]: "name" is missing')
        inner = f'{where}counts "{entry["name"]}": '
        _has(entry, keys, ("name", "pattern"), inner)
        if not {"expect", "min", "max"} & set(entry):
            raise RulesError(f'{inner}needs "expect", "min" or "max"')


CHECKS = {
    "notes": _is_whole,
    "multi_paragraph_notes": _is_whole,
    "no_links_in_notes": _is_flag,
    "margins_inches": _is_inches,
    "page_size": _is_page,
    "headers_footers_empty": _is_empty_setting,
    "max_embedded_images": _is_whole,
    "word_count": _is_range,
    "title": _is_text,
    "old_titles": _is_texts,
    "placeholders": _is_texts,
    "line_spacing": _is_spacing,
    "tag_pairs": _is_tag_pairs,
    "counts": _is_counts,
    "figures": _is_figures,
    "tables": _is_texts,
    "list_of_figures": _is_list_of_figures,
}


def load_settings(paths):
    """The settings in the files at `paths`, later files winning key by key. A key set to
    null in a later file switches that check off. A RulesError if anything is faulty."""
    settings = {}
    for path in paths:
        given = read_json_object(path)
        chosen = {key: value for key, value in given.items() if value is not None}
        _has(chosen, CHECKS, (), f"{path}: ")
        for key in given:
            if key not in CHECKS:
                raise RulesError(f'{path}: unknown key "{key}"')
        settings.update(given)
    settings = {key: value for key, value in settings.items() if value is not None}
    if "list_of_figures" in settings and "figures" not in settings:
        raise RulesError('the settings give "list_of_figures" but not "figures", which it needs')
    return settings
