import json

import pytest

from tests.samples import W
from wordtools.layout import Styles, blocks
from wordtools.rules import load_rules
from wordtools.tagcheck import check, report_lines

pytestmark = pytest.mark.tier1

SERIF, MONO = "Serif Face", "Mono Face"
RULES = {
    "open": "begin",
    "close": "end",
    "allowed": [
        "[begin boxed text]", "[begin boxed text, centered]", "[begin boxed text, computer font]",
        "[end boxed text]", "[begin block quote]", "[end block quote]", "[begin sidebar]", "[end sidebar]",
    ],
    "heading_styles": ["Heading2", "Heading3"],
    "tag_font": SERIF,
    "default_font": SERIF,
    "only_inside": {MONO: ["boxed text, computer font"]},
    "kinds": {
        "boxed text, computer font": {"font": MONO, "indent": {"left": 0, "right": 0, "first_line": 0}},
        "boxed text": {"not_fonts": ["Odd Face"]},
        "block quote": {
            "not_fonts": [MONO, "Odd Face"],
            "skip_numbered": True,
            "indent": {"left": 0.5, "right": 0, "first_line": 0},
        },
        "sidebar": {"indent": {"left": 0, "right": 0, "first_line": 0.5}},
    },
    "skip_boxes_starting": ["Summing Up"],
}  # fmt: skip


def para(text, font=None, ind="", numbered=False):
    run = f'<w:rPr><w:rFonts w:ascii="{font}"/></w:rPr>' if font else ""
    props = (f"<w:ind {ind}/>" if ind else "") + (
        '<w:numPr><w:numId w:val="4"/></w:numPr>' if numbered else ""
    )
    props = f"<w:pPr>{props}</w:pPr>" if props else ""
    return f"<w:p>{props}<w:r>{run}<w:t>{text}</w:t></w:r></w:p>"


def heading(level, text):
    return f'<w:p><w:pPr><w:pStyle w:val="Heading{level}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


LEFT, FIRST = 'w:left="720"', 'w:firstLine="720"'
QUOTE = ["[begin block quote]", ("Quoted words.", None, LEFT), "[end block quote]"]


def document(*items):
    made = []
    for item in items:
        if isinstance(item, str) and not item.startswith("<"):
            made.append(para(item))
        elif isinstance(item, tuple):
            made.append(para(*item))
        else:
            made.append(item)
    return f"<w:document {W}><w:body>{''.join(made)}</w:body></w:document>"


@pytest.fixture
def run(tmp_path):
    def run(*items, **changes):
        path = tmp_path / "rules.json"
        path.write_text(json.dumps({**RULES, **changes}), encoding="utf-8")
        rules = load_rules(str(path))
        found = blocks(document(*items), Styles(f"<w:styles {W}/>"), rules["default_font"])
        return check(found, rules)

    return run


def test_a_correct_box_of_each_kind_has_no_problems(run):
    result = run(
        heading(2, "Chapter One"),
        "[begin boxed text]", "Plain box.", "[end boxed text]",
        "[begin boxed text, centered]", "Centred box.", "[end boxed text]",
        "[begin boxed text, computer font]", ("Mono box.", MONO), "[end boxed text]",
        *QUOTE,
        "[begin sidebar]", ("Side words.", None, FIRST), "[end sidebar]",
    )  # fmt: skip
    assert result.problems == []
    assert result.tags == 10
    assert len(result.pairs) == 5


@pytest.mark.parametrize("tag", ["[Begin Sidebar]", "[begin sidebar ]", "[ begin sidebar]"])
def test_wrong_wording_is_one_problem(run, tag):
    result = run(tag, ("Side words.", None, FIRST), "[end sidebar]")
    assert result.problems == [f'(start) ("Side words."): tag wording "{tag}"']


def test_a_misspelt_kind_is_one_problem_not_a_pairing_one_as_well(run):
    result = run("[begin block-quote]", "Words.", "[end block quote]")
    assert result.problems == ['(start) ("Words."): tag wording "[begin block-quote]"']


def test_a_tag_with_more_text_after_it_is_a_wording_problem_and_still_opens_its_box(run):
    result = run("[begin sidebar] Some words", ("Side words.", None, FIRST), "[end sidebar]")
    assert result.problems == ['(start) ("Side words."): tag wording "[begin sidebar] Some words"']
    assert len(result.pairs) == 1


def test_a_second_opening_tag_is_one_pairing_problem_and_the_check_goes_on(run):
    result = run(
        "[begin sidebar]", "Lost.",
        "[begin sidebar]", ("Found.", None, FIRST), "[end sidebar]",
        "[begin block quote]", ("Bad indent.", None, FIRST), "[end block quote]",
    )  # fmt: skip
    assert result.problems == [
        '(start) ("Lost."): "[begin sidebar]" was not closed before the next tag opened',
        '(start) ("Bad indent."): indent left 0.00 right 0.00 first 0.50 (want left 0.50 right 0.00 first 0.00)',
    ]


def test_a_closing_tag_with_nothing_open_is_one_pairing_problem(run):
    result = run("Plain.", "[end block quote]", *QUOTE)
    assert result.problems == ['(start) ("[end block quote]"): "[end block quote]" closes nothing']
    assert len(result.pairs) == 1


def test_a_box_left_open_is_one_pairing_problem_and_its_contents_are_not_judged(run):
    result = run("[begin block quote]", "Unindented.", ("Mono.", MONO))
    assert result.problems == ['(start) ("Unindented."): "[begin block quote]" is never closed']
    assert result.pairs == []


def test_a_closing_tag_of_another_kind_is_one_pairing_problem(run):
    result = run("[begin sidebar]", ("Side words.", None, FIRST), "[end block quote]")
    assert result.problems == [
        '(start) ("Side words."): "[end block quote]" closes a box opened by "[begin sidebar]"'
    ]


def test_a_tag_line_partly_in_another_font_is_one_problem(run):
    tag = f'<w:p><w:r><w:t>[begin </w:t></w:r><w:r><w:rPr><w:rFonts w:ascii="{MONO}"/></w:rPr><w:t>sidebar]</w:t></w:r></w:p>'
    result = run(heading(3, "A Section"), tag, ("Side words.", None, FIRST), "[end sidebar]")
    assert result.problems == [
        f'A Section ("Side words."): tag "[begin sidebar]" in {MONO}, {SERIF} (want {SERIF})'
    ]


def test_a_tag_split_across_runs_is_read_as_one_tag(run):
    tag = "<w:p><w:r><w:t>[begin </w:t></w:r><w:r><w:t>sidebar]</w:t></w:r></w:p>"
    assert run(tag, ("Side words.", None, FIRST), "[end sidebar]").problems == []


def test_a_box_with_a_run_in_the_wrong_font_is_one_problem_with_heading_and_first_words(run):
    result = run(
        heading(2, "Chapter One"), heading(3, "A Section"),
        "[begin boxed text, computer font]", "A box whose first paragraph runs on past thirty-five characters", "[end boxed text]",
    )  # fmt: skip
    assert result.problems == [
        f'A Section ("A box whose first paragraph runs on"): font {SERIF} (want {MONO})'
    ]


def test_a_forbidden_font_in_a_box_is_one_problem(run):
    result = run("[begin boxed text]", ("Odd.", "Odd Face"), "[end boxed text]")
    assert result.problems == ['(start) ("Odd."): font Odd Face (not allowed here)']


def test_a_block_quote_with_a_first_line_indent_is_one_problem(run):
    result = run("[begin block quote]", ("Words.", None, f"{LEFT} {FIRST}"), "[end block quote]")
    assert result.problems == [
        '(start) ("Words."): indent left 0.50 right 0.00 first 0.50 (want left 0.50 right 0.00 first 0.00)'
    ]


def test_a_sidebar_with_a_left_indent_is_one_problem(run):
    result = run("[begin sidebar]", ("Words.", None, f"{LEFT} {FIRST}"), "[end sidebar]")
    assert result.problems == [
        '(start) ("Words."): indent left 0.50 right 0.00 first 0.50 (want left 0.00 right 0.00 first 0.50)'
    ]


def test_only_the_sides_a_rule_names_are_checked(run):
    kinds = {"sidebar": {"indent": {"left": 0.25}}}
    result = run("[begin sidebar]", ("Words.", None, 'w:left="360" w:firstLine="99"'), "[end sidebar]", kinds=kinds)
    assert result.problems == []


def test_empty_paragraphs_in_a_box_are_passed_over(run):
    assert run("[begin sidebar]", "", ("Words.", None, FIRST), "", "[end sidebar]").problems == []


def test_an_empty_box_names_no_first_words(run):
    result = run("[begin sidebar]", "[end sidebar ]")
    assert result.problems == ['(start) (""): tag wording "[end sidebar ]"']


def test_a_rule_for_kind_and_variant_wins_over_the_rule_for_the_kind(run):
    kinds = {"boxed text": {"font": "Other Face"}, "boxed text, centered": {"font": SERIF}}
    assert run("[begin boxed text, centered]", "Words.", "[end boxed text]", kinds=kinds).problems == []


def test_a_kind_with_no_rule_is_not_judged_for_content(run):
    allowed = [*RULES["allowed"], "[begin note]", "[end note]"]
    assert run("[begin note]", ("Words.", None, FIRST), "[end note]", allowed=allowed).problems == []


def test_first_line_after_first_applies_from_the_second_paragraph_of_a_box(run):
    kinds = {"block quote": {"indent": {"left": 0.5, "first_line": 0}, "first_line_after_first": 0.5}}
    good = ["[begin block quote]", ("One.", None, LEFT), "", ("Two.", None, f"{LEFT} {FIRST}"), "[end block quote]"]
    bad = ["[begin block quote]", ("One.", None, LEFT), ("Two.", None, LEFT), "[end block quote]"]
    assert run(*good, kinds=kinds).problems == []
    assert run(*bad, kinds=kinds).problems == [
        '(start) ("One."): indent left 0.50 right 0.00 first 0.00 (want left 0.50 first 0.50)'
    ]


def test_first_line_after_first_works_with_no_indent_rule(run):
    kinds = {"block quote": {"first_line_after_first": 0.5}}
    result = run("[begin block quote]", "One.", ("Two.", None, FIRST), "[end block quote]", kinds=kinds)
    assert result.problems == []


def test_a_numbered_paragraph_in_a_block_quote_passes_the_indent_check(run):
    assert run("[begin block quote]", ("Item.", None, "", True), "[end block quote]").problems == []


def test_a_hanging_paragraph_in_a_block_quote_passes_the_indent_check(run):
    assert run("[begin block quote]", ("Item.", None, 'w:hanging="360"'), "[end block quote]").problems == []


@pytest.mark.parametrize("mark", ["- ", "– ", "— ", "• "])
def test_a_typed_dash_or_bullet_counts_as_a_list_paragraph(run, mark):
    assert run("[begin block quote]", f"{mark}Item.", "[end block quote]").problems == []


def test_skip_numbered_still_checks_the_font(run):
    result = run("[begin block quote]", ("Item.", MONO, "", True), "[end block quote]")
    assert result.problems == [f'(start) ("Item."): font {MONO} (not allowed here)']


def test_a_font_reported_in_a_box_is_not_reported_again_as_outside_its_box(run):
    result = run("[begin block quote]", ("Words.", MONO, LEFT), "[end block quote]")
    assert result.problems == [f'(start) ("Words."): font {MONO} (not allowed here)']


def test_without_skip_numbered_a_list_paragraph_is_checked(run):
    result = run("[begin sidebar]", ("Item.", None, "", True), "[end sidebar]")
    assert len(result.problems) == 1


def test_a_listed_font_in_an_ordinary_paragraph_is_one_problem(run):
    result = run(heading(2, "Chapter One"), "Plain.", ("Mono words here.", MONO))
    assert result.problems == [f'Chapter One ("Mono words here."): {MONO} outside a box that allows it']


def test_a_listed_font_in_a_box_that_does_not_allow_it_is_one_problem(run):
    result = run("[begin boxed text]", ("Mono.", MONO), "[end boxed text]")
    assert result.problems == [f'(start) ("Mono."): {MONO} outside a box that allows it']


def test_a_listed_font_is_allowed_in_every_variant_when_the_kind_is_named(run):
    only = {MONO: ["boxed text"]}
    assert run("[begin boxed text, centered]", ("Mono.", MONO), "[end boxed text]", only_inside=only).problems == []


def test_a_box_skipped_by_its_opening_words_may_have_any_layout(run):
    result = run("[begin block quote]", "Summing Up", ("Mono.", MONO, FIRST), "[end block quote]")
    assert result.problems == []


def test_a_box_exception_changes_the_rule_for_exactly_the_box_it_names(run):
    exception = [{"starts_with": "An odd", "first_line_after_first": 0.5}]
    odd = ["[begin block quote]", ("An odd quote.", None, LEFT), ("More.", None, f"{LEFT} {FIRST}"), "[end block quote]"]
    usual = ["[begin block quote]", ("A usual quote.", None, LEFT), ("More.", None, f"{LEFT} {FIRST}"), "[end block quote]"]
    assert run(*odd, box_exceptions=exception).problems == []
    assert run(*usual, box_exceptions=exception).problems == [
        '(start) ("A usual quote."): indent left 0.50 right 0.00 first 0.50 (want left 0.50 right 0.00 first 0.00)'
    ]


def test_a_box_exception_font_allows_that_font_in_that_box(run):
    exception = [{"starts_with": "Code", "font": MONO, "not_fonts": []}]
    result = run("[begin block quote]", ("Code here.", MONO, LEFT), "[end block quote]", box_exceptions=exception)
    assert result.problems == []


def test_a_paragraph_exception_changes_the_indent_for_exactly_its_paragraph(run):
    exception = [{"starts_with": "Set wide", "indent": {"left": 1}}]
    good = ["[begin sidebar]", ("Set wide here.", None, 'w:left="1440"'), ("Usual.", None, FIRST), "[end sidebar]"]
    bad = ["[begin sidebar]", ("Usual.", None, 'w:left="1440"'), "[end sidebar]"]
    assert run(*good, paragraph_exceptions=exception).problems == []
    assert len(run(*bad, paragraph_exceptions=exception).problems) == 1


def test_a_paragraph_exception_indent_is_not_overridden_by_first_line_after_first(run):
    kinds = {"block quote": {"indent": {"first_line": 0}, "first_line_after_first": 0.5}}
    exception = [{"starts_with": "Flush", "indent": {"first_line": 0}}]
    result = run("[begin block quote]", "One.", "Flush again.", "[end block quote]", kinds=kinds, paragraph_exceptions=exception)
    assert result.problems == []


def test_a_paragraph_exception_can_skip_a_paragraph_in_a_box_and_outside_one(run):
    exception = [{"starts_with": "By eye", "skip": True}]
    result = run(
        "[begin sidebar]", ("By eye.", MONO, LEFT), ("Usual.", None, FIRST), "[end sidebar]",
        ("By eye outside.", MONO),
        paragraph_exceptions=exception,
    )  # fmt: skip
    assert result.problems == []


def test_exceptions_match_whatever_the_unicode_spelling(run):
    exception = [{"starts_with": "Café", "skip": True}]
    assert run(("Café notes.", MONO), paragraph_exceptions=exception).problems == []


def test_problems_come_in_document_order(run):
    result = run(
        ("Mono first.", MONO),
        "[Begin Sidebar]", ("Side.", None, FIRST), "[end sidebar]",
        ("Mono last.", MONO),
    )  # fmt: skip
    assert [problem.split(":")[0] for problem in result.problems] == [
        '(start) ("Mono first.")', '(start) ("Side.")', '(start) ("Mono last.")',
    ]  # fmt: skip


def test_a_heading_with_no_text_leaves_the_last_heading_standing(run):
    result = run(heading(2, "Chapter One"), heading(2, ""), ("Mono.", MONO))
    assert result.problems[0].startswith("Chapter One (")


def test_the_summary_counts_tags_pairs_kinds_fonts_and_problems(run):
    result = run(
        heading(2, "Chapter One"),
        *QUOTE,
        "[begin boxed text, computer font]", ("Mono.", MONO), "[end boxed text]",
        "[begin boxed text]", "Words.", "[end boxed text]",
        "[end sidebar]",
    )  # fmt: skip
    assert report_lines(result)[-1] == (
        f"7 tags in 3 pairs; kinds: block quote 1, boxed text 2;"
        f" fonts in the body (paragraph counts): {SERIF} 10, {MONO} 1; 1 problem(s)"
    )


def test_the_summary_says_none_for_an_empty_manuscript(run):
    assert report_lines(run())[-1] == (
        "0 tags in 0 pairs; kinds: none; fonts in the body (paragraph counts): none; 0 problem(s)"
    )


def test_the_summary_names_a_run_with_no_font_as_not_set(run):
    assert "(not set) 1" in report_lines(run("Words.", default_font=None, tag_font=None, kinds={}))[-1]


def test_prints_problems_before_the_summary(run):
    lines = report_lines(run("[end sidebar]"))
    assert lines[0] == '(start) ("[end sidebar]"): "[end sidebar]" closes nothing'
    assert len(lines) == 2


def test_verbose_lists_every_pair(run):
    result = run(
        heading(2, "Chapter One"),
        "[begin boxed text, centered]", "One box.", "Two.", "[end boxed text]",
        *QUOTE,
    )  # fmt: skip
    assert report_lines(result, verbose=True)[:2] == [
        'pair: boxed text, centered | Chapter One | "One box." | 2 paragraphs',
        'pair: block quote | Chapter One | "Quoted words." | 1 paragraph',
    ]
