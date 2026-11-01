import json

import pytest

from wordtools.rules import RulesError, load_rules, rule_key

pytestmark = pytest.mark.tier1

GOOD = {
    "open": "begin",
    "close": "end",
    "allowed": ["[begin sidebar]", "[end sidebar]"],
    "heading_styles": ["Heading2"],
    "tag_font": "Serif Face",
    "default_font": "Serif Face",
    "only_inside": {"Mono Face": ["boxed text, computer font"]},
    "kinds": {
        "Boxed  Text, Computer Font": {"font": "Mono Face", "indent": {"left": 0, "right": 0, "first_line": 0}},
        "block quote": {
            "not_fonts": ["Mono Face"],
            "skip_numbered": True,
            "first_line_after_first": 0.25,
            "indent": {"left": 0.5},
        },
    },
    "skip_boxes_starting": ["Summing Up"],
    "box_exceptions": [{"starts_with": "An odd one", "first_line_after_first": 0.5}],
    "paragraph_exceptions": [
        {"starts_with": "Lay this out by eye", "skip": True},
        {"starts_with": "Set wide", "indent": {"left": 1}},
    ],
}


def load(tmp_path, rules):
    path = tmp_path / "rules.json"
    path.write_text(rules if isinstance(rules, str) else json.dumps(rules), encoding="utf-8")
    return load_rules(str(path))


def refusal(tmp_path, rules):
    with pytest.raises(RulesError) as caught:
        load(tmp_path, rules)
    return str(caught.value).replace(str(tmp_path / "rules.json"), "RULES")


def changed(**keys):
    rules = json.loads(json.dumps(GOOD))
    rules.update(keys)
    return rules


def without(key):
    rules = changed()
    del rules[key]
    return rules


def test_loads_a_complete_rules_file(tmp_path):
    rules = load(tmp_path, GOOD)
    assert rules["open"] == "begin"
    assert rules["allowed"] == ["[begin sidebar]", "[end sidebar]"]
    assert rules["box_exceptions"][0]["starts_with"] == "An odd one"


def test_gives_kind_names_one_spelling_for_comparing(tmp_path):
    rules = load(tmp_path, GOOD)
    assert sorted(rules["kinds"]) == ["block quote", "boxed text, computer font"]
    assert rules["only_inside"]["Mono Face"] == ["boxed text, computer font"]


def test_rule_key_joins_kind_and_variant():
    assert rule_key("boxed text", None) == "boxed text"
    assert rule_key("boxed text", " Computer  Font ") == "boxed text, computer font"


def test_only_open_close_and_allowed_are_required(tmp_path):
    rules = load(tmp_path, {"open": "begin", "close": "end", "allowed": ["[begin x]"]})
    assert rules["kinds"] == {}
    assert rules["heading_styles"] == []
    assert rules["only_inside"] == {}
    assert rules["skip_boxes_starting"] == []
    assert rules["box_exceptions"] == []
    assert rules["paragraph_exceptions"] == []
    assert rules["tag_font"] is None
    assert rules["default_font"] is None


def test_refuses_a_file_that_is_not_there(tmp_path):
    with pytest.raises(RulesError) as caught:
        load_rules(str(tmp_path / "gone.json"))
    assert str(caught.value) == f"{tmp_path / 'gone.json'}: no such file"


def test_refuses_a_file_it_may_not_read(tmp_path):
    with pytest.raises(RulesError) as caught:
        load_rules(str(tmp_path))
    assert str(caught.value) == f"{tmp_path}: cannot be read: Is a directory"


def test_refuses_a_file_that_is_not_utf8(tmp_path):
    path = tmp_path / "rules.json"
    path.write_bytes(b'{"open": "\xff"}')
    with pytest.raises(RulesError) as caught:
        load_rules(str(path))
    assert str(caught.value) == f"{path}: not UTF-8 text"


@pytest.mark.parametrize(
    "rules, said",
    [
        ("{not json", "RULES: not valid JSON (line 1, column 2): Expecting property name enclosed in double quotes"),
        ("[]", "RULES: must be a JSON object"),
        (without("open"), 'RULES: "open" is missing'),
        (without("close"), 'RULES: "close" is missing'),
        (without("allowed"), 'RULES: "allowed" is missing'),
        (changed(colour="red"), 'RULES: unknown key "colour"'),
        (changed(open=""), 'RULES: "open" must be a word'),
        (changed(close=7), 'RULES: "close" must be a word'),
        (changed(open="End"), 'RULES: "open" and "close" must differ'),
        (changed(allowed="[begin x]"), 'RULES: "allowed" must be a list of texts'),
        (changed(allowed=[]), 'RULES: "allowed" must name at least one tag'),
        (changed(allowed=[1]), 'RULES: "allowed" must be a list of texts'),
        (changed(heading_styles=[1]), 'RULES: "heading_styles" must be a list of texts'),
        (changed(tag_font=1), 'RULES: "tag_font" must be a text'),
        (changed(default_font=1), 'RULES: "default_font" must be a text'),
        (changed(only_inside=[]), 'RULES: "only_inside" must map each font to a list of kinds'),
        (changed(only_inside={"F": "x"}), 'RULES: "only_inside" must map each font to a list of kinds'),
        (changed(kinds=[]), 'RULES: "kinds" must map each kind to its rule'),
        (changed(kinds={"x": 1}), 'RULES: kind "x" must be an object'),
        (changed(kinds={"x": {"fnt": "F"}}), 'RULES: kind "x": unknown key "fnt"'),
        (changed(kinds={"x": {"font": 1}}), 'RULES: kind "x": "font" must be a text'),
        (changed(kinds={"x": {"not_fonts": "F"}}), 'RULES: kind "x": "not_fonts" must be a list of texts'),
        (changed(kinds={"x": {"skip_numbered": 1}}), 'RULES: kind "x": "skip_numbered" must be true or false'),
        (changed(kinds={"x": {"first_line_after_first": "0"}}), 'RULES: kind "x": "first_line_after_first" must be a number of inches'),
        (changed(kinds={"x": {"first_line_after_first": True}}), 'RULES: kind "x": "first_line_after_first" must be a number of inches'),
        (changed(kinds={"x": {"indent": 0}}), 'RULES: kind "x": "indent" must be an object'),
        (changed(kinds={"x": {"indent": {"top": 0}}}), 'RULES: kind "x": "indent": unknown key "top"'),
        (changed(kinds={"x": {"indent": {"left": "0"}}}), 'RULES: kind "x": "indent": "left" must be a number of inches'),
        (changed(skip_boxes_starting=[""]), 'RULES: "skip_boxes_starting" must be a list of texts that are not empty'),
        (changed(skip_boxes_starting="x"), 'RULES: "skip_boxes_starting" must be a list of texts that are not empty'),
        (changed(box_exceptions={}), 'RULES: "box_exceptions" must be a list of objects'),
        (changed(box_exceptions=[1]), 'RULES: "box_exceptions" must be a list of objects'),
        (changed(box_exceptions=[{"font": "F"}]), 'RULES: box_exceptions[1]: "starts_with" must be a text that is not empty'),
        (changed(box_exceptions=[{"starts_with": "a", "fnt": "F"}]), 'RULES: box_exceptions[1]: unknown key "fnt"'),
        (changed(box_exceptions=[{"starts_with": "a", "font": 1}]), 'RULES: box_exceptions[1]: "font" must be a text'),
        (changed(paragraph_exceptions=[{"starts_with": ""}]), 'RULES: paragraph_exceptions[1]: "starts_with" must be a text that is not empty'),
        (changed(paragraph_exceptions=[{"starts_with": "a"}]), 'RULES: paragraph_exceptions[1]: needs "indent" or "skip"'),
        (changed(paragraph_exceptions=[{"starts_with": "a", "font": "F"}]), 'RULES: paragraph_exceptions[1]: unknown key "font"'),
        (changed(paragraph_exceptions=[{"starts_with": "a", "skip": 1}]), 'RULES: paragraph_exceptions[1]: "skip" must be true or false'),
        (changed(paragraph_exceptions=[{"starts_with": "a", "indent": {"top": 1}}]), 'RULES: paragraph_exceptions[1]: "indent": unknown key "top"'),
        (without("default_font"), 'RULES: "default_font" is needed by "tag_font" and "font", to judge a run with no font of its own'),
    ],
)
def test_refuses_a_faulty_rules_file_and_names_the_fault(tmp_path, rules, said):
    assert refusal(tmp_path, rules) == said


def test_default_font_is_needed_by_a_font_rule_alone(tmp_path):
    rules = without("default_font")
    del rules["tag_font"], rules["box_exceptions"]
    assert "is needed" in refusal(tmp_path, rules)


def test_default_font_is_needed_by_a_font_in_an_exception(tmp_path):
    rules = {"open": "a", "close": "b", "allowed": ["[a x]"], "box_exceptions": [{"starts_with": "s", "font": "F"}]}
    assert "is needed" in refusal(tmp_path, rules)
