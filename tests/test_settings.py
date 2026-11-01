import json

import pytest

from wordtools.rules import RulesError
from wordtools.settings import load_settings

pytestmark = pytest.mark.tier1

FIGURES = {"callout": r"\[Figure (\d+\.\d+)\]", "caption": r"\[([^\]]+)\]", "credit": r"\[Credit: ([^\]]*)\]"}
GOOD = {
    "notes": 12,
    "multi_paragraph_notes": 2,
    "no_links_in_notes": True,
    "margins_inches": 1,
    "page_size": "letter",
    "headers_footers_empty": "note",
    "max_embedded_images": 1,
    "word_count": [100, 200],
    "title": "A Ledger",
    "old_titles": ["A Log"],
    "placeholders": ["XXX"],
    "line_spacing": 360,
    "tag_pairs": {"open": "begin", "close": "end", "kinds": ["sidebar"], "required": ["sidebar"]},
    "counts": [{"name": "maps", "pattern": r"Map \d", "expect": 3}],
    "figures": {**FIGURES, "expect": 2, "caption_no_full_stop": True},
    "tables": ["1.1"],
    "list_of_figures": {"from": "List of Figures", "to": "Dedication"},
}


@pytest.fixture
def write(tmp_path):
    def write(content, name="settings.json"):
        path = tmp_path / name
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return str(path)

    return write


def refusal(path):
    with pytest.raises(RulesError) as caught:
        load_settings([path])
    return str(caught.value).replace(path, "FILE")


def test_no_settings_at_all_is_allowed():
    assert load_settings([]) == {}


def test_a_complete_settings_file_is_accepted(write):
    assert load_settings([write(GOOD)]) == GOOD


def test_a_later_file_wins_key_by_key(write):
    first = write({"notes": 1, "title": "Kept"}, "first.json")
    second = write({"notes": 2}, "second.json")
    assert load_settings([first, second]) == {"notes": 2, "title": "Kept"}


def test_a_later_file_can_switch_a_check_off_with_null(write):
    first = write({"notes": 1, "title": "Kept"}, "first.json")
    second = write({"notes": None}, "second.json")
    assert load_settings([first, second]) == {"title": "Kept"}


def test_page_size_may_be_a4_or_two_numbers(write):
    assert load_settings([write({"page_size": "a4"})]) == {"page_size": "a4"}
    assert load_settings([write({"page_size": [6, 9.5]})]) == {"page_size": [6, 9.5]}


def test_headers_footers_empty_may_be_true_or_false(write):
    assert load_settings([write({"headers_footers_empty": True})]) == {"headers_footers_empty": True}
    assert load_settings([write({"headers_footers_empty": False})]) == {"headers_footers_empty": False}


def test_a_count_may_have_a_minimum_a_maximum_and_a_placeholder_mark(write):
    counts = [{"name": "a", "pattern": "x", "min": 1, "max": 3, "placeholder": True}]
    assert load_settings([write({"counts": counts})]) == {"counts": counts}


def test_list_of_figures_may_say_how_an_entry_reads(write):
    settings = {"figures": FIGURES, "list_of_figures": {"from": "a", "to": "b", "entry": "Fig. {number}: {caption}"}}
    assert load_settings([write(settings)]) == settings


def test_a_missing_file_is_refused(tmp_path):
    with pytest.raises(RulesError) as caught:
        load_settings([str(tmp_path / "gone.json")])
    assert str(caught.value) == f"{tmp_path / 'gone.json'}: no such file"


def test_list_of_figures_without_figures_is_refused_across_all_the_files(write):
    with pytest.raises(RulesError) as caught:
        load_settings([write({"list_of_figures": {"from": "a", "to": "b"}})])
    assert str(caught.value) == 'the settings give "list_of_figures" but not "figures", which it needs'


@pytest.mark.parametrize(
    "settings, said",
    [
        ({"notez": 1}, 'FILE: unknown key "notez"'),
        ({"notez": None}, 'FILE: unknown key "notez"'),
        ({"notes": "1"}, 'FILE: "notes" must be a whole number'),
        ({"notes": True}, 'FILE: "notes" must be a whole number'),
        ({"notes": -1}, 'FILE: "notes" must be a whole number'),
        ({"multi_paragraph_notes": 1.5}, 'FILE: "multi_paragraph_notes" must be a whole number'),
        ({"max_embedded_images": "x"}, 'FILE: "max_embedded_images" must be a whole number'),
        ({"line_spacing": 0}, 'FILE: "line_spacing" must be a whole number of 240ths of a line'),
        ({"no_links_in_notes": 1}, 'FILE: "no_links_in_notes" must be true or false'),
        ({"margins_inches": "1"}, 'FILE: "margins_inches" must be a number of inches'),
        ({"page_size": "legal"}, 'FILE: "page_size" must be "letter", "a4" or [width, height] in inches'),
        ({"page_size": [1]}, 'FILE: "page_size" must be "letter", "a4" or [width, height] in inches'),
        ({"page_size": [1, "2"]}, 'FILE: "page_size" must be "letter", "a4" or [width, height] in inches'),
        ({"headers_footers_empty": "yes"}, 'FILE: "headers_footers_empty" must be true, false or "note"'),
        ({"word_count": 5}, 'FILE: "word_count" must be [lowest, highest]'),
        ({"word_count": [5]}, 'FILE: "word_count" must be [lowest, highest]'),
        ({"word_count": [9, 5]}, 'FILE: "word_count" must be [lowest, highest]'),
        ({"word_count": [1, "9"]}, 'FILE: "word_count" must be [lowest, highest]'),
        ({"title": 1}, 'FILE: "title" must be a text'),
        ({"title": ""}, 'FILE: "title" must be a text'),
        ({"old_titles": "x"}, 'FILE: "old_titles" must be a list of texts'),
        ({"old_titles": [""]}, 'FILE: "old_titles" must be a list of texts'),
        ({"placeholders": [""]}, 'FILE: "placeholders" must be a list of texts'),
        ({"tables": [1.1]}, 'FILE: "tables" must be a list of texts'),
        ({"tag_pairs": []}, 'FILE: "tag_pairs" must be an object'),
        ({"tag_pairs": {"open": "a", "close": "b"}}, 'FILE: tag_pairs: "kinds" is missing'),
        ({"tag_pairs": {"open": "a", "kinds": []}}, 'FILE: tag_pairs: "close" is missing'),
        ({"tag_pairs": {"open": "a", "close": "b", "kinds": [], "x": 1}}, 'FILE: tag_pairs: unknown key "x"'),
        ({"tag_pairs": {"open": "a", "close": "A", "kinds": []}}, 'FILE: tag_pairs: "open" and "close" must differ'),
        ({"tag_pairs": {"open": 1, "close": "b", "kinds": []}}, 'FILE: tag_pairs: "open" must be a text'),
        ({"tag_pairs": {"open": "a", "close": "b", "kinds": "x"}}, 'FILE: tag_pairs: "kinds" must be a list of texts'),
        ({"counts": {}}, 'FILE: "counts" must be a list of objects'),
        ({"counts": [1]}, 'FILE: "counts" must be a list of objects'),
        ({"counts": [{"pattern": "x", "expect": 1}]}, 'FILE: counts[1]: "name" is missing'),
        ({"counts": [{"name": "a", "expect": 1}]}, 'FILE: counts "a": "pattern" is missing'),
        ({"counts": [{"name": "a", "pattern": "x"}]}, 'FILE: counts "a": needs "expect", "min" or "max"'),
        ({"counts": [{"name": "a", "pattern": "(", "expect": 1}]}, 'FILE: counts "a": "pattern" is a bad regular expression: missing ), unterminated subpattern at position 0'),
        ({"counts": [{"name": "a", "pattern": "x", "expect": "1"}]}, 'FILE: counts "a": "expect" must be a whole number'),
        ({"counts": [{"name": "a", "pattern": "x", "min": -1}]}, 'FILE: counts "a": "min" must be a whole number'),
        ({"counts": [{"name": "a", "pattern": "x", "expect": 1, "y": 2}]}, 'FILE: counts "a": unknown key "y"'),
        ({"counts": [{"name": "a", "pattern": "x", "expect": 1, "placeholder": 1}]}, 'FILE: counts "a": "placeholder" must be true or false'),
        ({"figures": 1}, 'FILE: "figures" must be an object'),
        ({"figures": {"callout": "a", "caption": "b"}}, 'FILE: figures: "credit" is missing'),
        ({"figures": {**FIGURES, "credit": "["}}, 'FILE: figures: "credit" is a bad regular expression: unterminated character set at position 0'),
        ({"figures": {**FIGURES, "credit": 1}}, 'FILE: figures: "credit" must be a text'),
        ({"figures": {**FIGURES, "expect": "2"}}, 'FILE: figures: "expect" must be a whole number'),
        ({"figures": {**FIGURES, "caption_no_full_stop": 1}}, 'FILE: figures: "caption_no_full_stop" must be true or false'),
        ({"figures": {**FIGURES, "y": 1}}, 'FILE: figures: unknown key "y"'),
        ({"figures": FIGURES, "list_of_figures": 1}, 'FILE: "list_of_figures" must be an object'),
        ({"figures": FIGURES, "list_of_figures": {"from": "a"}}, 'FILE: list_of_figures: "to" is missing'),
        ({"figures": FIGURES, "list_of_figures": {"from": 1, "to": "b"}}, 'FILE: list_of_figures: "from" must be a text'),
        ({"figures": FIGURES, "list_of_figures": {"from": "a", "to": "b", "entry": 1}}, 'FILE: list_of_figures: "entry" must be a text'),
        ({"figures": FIGURES, "list_of_figures": {"from": "a", "to": "b", "y": 1}}, 'FILE: list_of_figures: unknown key "y"'),
    ],
)
def test_refuses_a_faulty_setting_and_names_it(write, settings, said):
    assert refusal(write(settings)) == said


def test_refuses_a_file_that_is_not_json(write):
    assert refusal(write("[")).startswith("FILE: not valid JSON")
