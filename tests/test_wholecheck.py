import pytest

from tests.docxkit import pack_docx
from tests.samples import W, heading, note, p, sample_parts, separators
from wordtools.docx import Docx
from wordtools.wholecheck import check

pytestmark = pytest.mark.tier2


# The sample's notes need their markers wherever a test gives a body of its own.
MARKERS = (
    '<w:p><w:r><w:endnoteReference w:id="1"/></w:r><w:r><w:endnoteReference w:id="2"/></w:r>'
    '<w:r><w:footnoteReference w:id="1"/></w:r></w:p>'
)


@pytest.fixture
def run(tmp_path):
    def run(change=None, body=None, settings=None, **options):
        parts = sample_parts(None if body is None else [*body, MARKERS])
        if change:
            change(parts)
        path = tmp_path / "Book.docx"
        pack_docx(path, parts)
        return check(Docx(path), settings or {}, **options)

    return run


def in_note(parts, old="Ibid.", new="Ibid."):
    parts["word/endnotes.xml"] = parts["word/endnotes.xml"].replace(old, new)


def in_body(parts, old, new):
    parts["word/document.xml"] = parts["word/document.xml"].replace(old, new)


def test_every_always_on_check_is_reported_for_a_clean_manuscript(run):
    report = run()
    assert report.lines == [
        "OK   no tracked changes (found 0)",
        "OK   Track Changes switched off",
        "OK   no comments (comments part: no; references: 0)",
        "OK   endnotes 2, markers 2, one marker each",
        "OK   footnotes 1, markers 1, one marker each",
        "OK   no straight quotes or apostrophes (found 0)",
        "OK   no zero-width space (found 0)",
        "OK   no soft hyphen (found 0)",
        "OK   no zero-width non-joiner (found 0)",
        "OK   no byte-order mark (found 0)",
        "OK   no placeholder TKTKTK (found 0)",
        "OK   no fields in headers or footers (found none)",
        "OK   no watermark (found 0)",
        "NOTE fonts used in runs: Times-Roman",
        "NOTE highlighted runs: 0",
        "NOTE explicit line spacing other than 480: 1 (values 280); check-spacing is the full check",
        "NOTE notes of more than one paragraph: 0",
        "NOTE paragraphs by heading style: Heading1 1, Heading2 2",
    ]
    assert report.fails == []
    assert report.result() == "RESULT: PASS"


def only_failure(report, said):
    assert report.fails == [said]
    assert f"FAIL {said}" in report.lines
    assert report.result() == f"RESULT: 1 FAIL(S): {said}"


def test_fails_a_tracked_insertion_in_a_note(run):
    report = run(lambda parts: in_note(parts, new='</w:t></w:r><w:ins w:id="9"><w:r><w:t>x</w:t></w:r></w:ins><w:r><w:t>y'))
    only_failure(report, "no tracked changes (found 1)")


def test_fails_a_tracked_deletion_in_a_footnote(run):
    def change(parts):
        parts["word/footnotes.xml"] = parts["word/footnotes.xml"].replace(
            "</w:p></w:footnote></w:footnotes>",
            '<w:del w:id="9"><w:r><w:delText>x</w:delText></w:r></w:del></w:p></w:footnote></w:footnotes>',
        )

    only_failure(run(change), "no tracked changes (found 1)")


def test_fails_track_changes_left_on(run):
    def change(parts):
        parts["word/settings.xml"] = f"<w:settings {W}><w:trackRevisions/></w:settings>"

    only_failure(run(change), "Track Changes switched off")


def test_fails_a_comment_reference(run):
    report = run(lambda parts: in_body(parts, "<w:r><w:t>The log for March", '<w:r><w:commentReference w:id="0"/></w:r><w:r><w:t>The log for March'))
    only_failure(report, "no comments (comments part: no; references: 1)")


def test_fails_a_comments_part_with_no_reference_to_it(run):
    def change(parts):
        parts["word/comments.xml"] = f"<w:comments {W}/>"

    only_failure(run(change), "no comments (comments part: yes; references: 0)")


def test_fails_an_endnote_whose_marker_was_deleted(run):
    report = run(lambda parts: in_body(parts, '<w:r><w:endnoteReference w:id="2"/></w:r>', ""))
    only_failure(report, "endnotes 2, markers 1, one marker each (no marker: 2)")


def test_fails_a_marker_with_no_note(run):
    report = run(lambda parts: in_body(parts, '<w:endnoteReference w:id="2"/>', '<w:endnoteReference w:id="7"/>'))
    only_failure(report, "endnotes 2, markers 2, one marker each (no marker: 2; no note: 7)")


def test_fails_a_note_with_two_markers(run):
    report = run(lambda parts: in_body(parts, '<w:endnoteReference w:id="2"/>', '<w:endnoteReference w:id="1"/>'))
    only_failure(report, "endnotes 2, markers 2, one marker each (no marker: 2; repeated: 1)")


def test_fails_a_footnote_whose_marker_was_deleted(run):
    report = run(lambda parts: in_body(parts, '<w:r><w:footnoteReference w:id="1"/></w:r>', ""))
    only_failure(report, "footnotes 1, markers 0, one marker each (no marker: 1)")


def test_separators_are_not_notes_whatever_their_ids(run):
    def change(parts):
        parts["word/endnotes.xml"] = (
            f'<w:endnotes {W}><w:endnote w:type="separator" w:id="1"><w:p/></w:endnote>'
            f'{note("endnote", 2, "Only.")}</w:endnotes>'
        )
        in_body(parts, '<w:endnoteReference w:id="1"/>', "")

    assert run(change).fails == []


def test_a_manuscript_with_no_notes_parts_has_none_to_fail(run):
    def change(parts):
        del parts["word/endnotes.xml"], parts["word/footnotes.xml"]
        in_body(parts, '<w:endnoteReference w:id="1"/>', "")
        in_body(parts, '<w:endnoteReference w:id="2"/>', "")
        in_body(parts, '<w:footnoteReference w:id="1"/>', "")

    assert run(change).fails == []


def test_expect_notes_adds_a_check_of_the_count(run):
    assert "OK   endnote count is 2" in run(expect_notes=2).lines
    only_failure(run(expect_notes=3), "endnote count is 3 (found 2)")


def test_the_notes_setting_adds_the_same_check_and_the_flag_wins(run):
    only_failure(run(settings={"notes": 5}), "endnote count is 5 (found 2)")
    assert run(settings={"notes": 5}, expect_notes=2).fails == []


def test_fails_a_straight_apostrophe_in_a_note(run):
    only_failure(run(lambda parts: in_note(parts, new="It&apos;s.")), "no straight quotes or apostrophes (found 1)")


def test_fails_a_straight_quote_in_the_body(run):
    report = run(body=[p('He said "no".')])
    only_failure(report, "no straight quotes or apostrophes (found 2)")


@pytest.mark.parametrize(
    "character, name",
    [
        ("​", "zero-width space"),
        ("­", "soft hyphen"),
        ("‌", "zero-width non-joiner"),
        ("﻿", "byte-order mark"),
    ],
)
def test_fails_an_invisible_character(run, character, name):
    only_failure(run(body=[p(f"wo{character}rd")]), f"no {name} (found 1)")


def test_fails_word_s_own_optional_hyphen_as_a_soft_hyphen(run):
    report = run(body=["<w:p><w:r><w:t>wo</w:t><w:softHyphen/><w:t>rd</w:t></w:r></w:p>"])
    only_failure(report, "no soft hyphen (found 1)")


def test_fails_a_placeholder_in_a_note(run):
    only_failure(run(lambda parts: in_note(parts, new="TKTKTK")), "no placeholder TKTKTK (found 1)")


def test_placeholders_can_be_set_and_replace_the_default(run):
    report = run(body=[p("XXX TKTKTK")], settings={"placeholders": ["XXX", "YYY"]})
    only_failure(report, "no placeholder XXX (found 1)")
    assert "OK   no placeholder YYY (found 0)" in report.lines


def test_allow_placeholders_turns_the_failure_into_a_note_and_the_run_passes(run):
    report = run(body=[p("TKTKTK")], allow_placeholders=True)
    assert "NOTE no placeholder TKTKTK (found 1)" in report.lines
    assert report.result() == "RESULT: PASS"


def footer(xml):
    def change(parts):
        parts["word/footer1.xml"] = f"<w:ftr {W}>{xml}</w:ftr>"

    return change


def test_fails_a_page_field_in_a_footer(run):
    report = run(footer('<w:p><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r></w:p>'))
    only_failure(report, "no fields in headers or footers (found PAGE)")


def test_fails_a_simple_field_in_a_header(run):
    def change(parts):
        parts["word/header1.xml"] = f'<w:hdr {W}><w:p><w:fldSimple w:instr=" NUMPAGES \\* MERGEFORMAT "/></w:p></w:hdr>'

    only_failure(run(change), "no fields in headers or footers (found NUMPAGES)")


def test_a_field_in_the_body_is_not_a_header_field(run):
    body = ['<w:p><w:r><w:instrText xml:space="preserve"> PAGE </w:instrText></w:r></w:p>']
    assert run(body=body).fails == []


def test_fails_a_watermark_in_a_header(run):
    def change(parts):
        parts["word/header1.xml"] = f'<w:hdr {W}><w:p><w:r><w:pict id="PowerPlusWaterMarkObject1"/></w:r></w:p></w:hdr>'

    only_failure(run(change), "no watermark (found 1)")


def test_the_word_watermark_in_the_text_is_not_a_watermark(run):
    assert run(body=[p("The PowerPlusWaterMark of a page.")]).fails == []


def test_notes_never_fail(run):
    body = [
        '<w:p><w:r><w:rPr><w:rFonts w:ascii="Mono Face"/><w:highlight w:val="yellow"/></w:rPr><w:t>x</w:t></w:r></w:p>',
        '<w:p><w:r><w:rPr><w:highlight w:val="white"/></w:rPr><w:t>y</w:t></w:r></w:p>',
        '<w:p><w:r><w:rPr><w:highlight w:val="white"/></w:rPr><w:t>z</w:t></w:r></w:p>',
        heading(3, "A Part"),
    ]

    def change(parts):
        two = note("endnote", 1, "First.").replace("</w:p></w:endnote>", "</w:p>" + p("Second.") + "</w:endnote>")
        parts["word/endnotes.xml"] = f"<w:endnotes {W}>{separators('endnote')}{two}{note('endnote', 2, 'x')}</w:endnotes>"

    report = run(change, body=body)
    assert report.fails == []
    assert [line for line in report.lines if line.startswith("NOTE")] == [
        "NOTE fonts used in runs: Mono Face",
        "NOTE highlighted runs: 3 (white 2, yellow 1)",
        "NOTE explicit line spacing other than 480: 0",
        "NOTE notes of more than one paragraph: 1",
        "NOTE paragraphs by heading style: Heading3 1",
    ]


def test_the_expected_line_spacing_can_be_set(run):
    report = run(body=['<w:p><w:pPr><w:spacing w:line="360"/></w:pPr></w:p>', '<w:p><w:pPr><w:spacing w:line="480"/></w:pPr></w:p>'], settings={"line_spacing": 360})
    assert "NOTE explicit line spacing other than 360: 1 (values 480); check-spacing is the full check" in report.lines


def test_no_headings_and_no_fonts_are_said_plainly(run):
    report = run(body=[p("x")])
    assert "NOTE paragraphs by heading style: none" in report.lines
    assert "NOTE fonts used in runs: none set directly" in report.lines


def test_the_word_watermark_in_the_text_is_not_a_watermark_even_beside_a_picture(run):
    body = [p("The PowerPlusWaterMark of a page."), "<w:p><w:r><w:pict/></w:r></w:p>"]
    assert run(body=body).fails == []


def test_a_watermark_shape_in_the_body_is_found(run):
    body = ['<w:p><w:r><w:pict id="PowerPlusWaterMarkObject9"/></w:r></w:p>']
    only_failure(run(body=body), "no watermark (found 1)")


def test_a_multi_paragraph_notes_setting_compares_the_count_and_only_ever_notes(run):
    assert "OK   notes of more than one paragraph: 0 (expected 0)" in run(settings={"multi_paragraph_notes": 0}).lines
    report = run(settings={"multi_paragraph_notes": 14})
    assert "NOTE notes of more than one paragraph: 0 (expected 14)" in report.lines
    assert report.fails == []


def test_no_links_in_notes_fails_a_live_link(run):
    assert "OK   no live hyperlinks in the notes (found 0)" in run(settings={"no_links_in_notes": True}).lines
    linked = lambda parts: in_note(parts, new='</w:t></w:r><w:hyperlink r:id="rId9"><w:r><w:t>x</w:t></w:r></w:hyperlink><w:r><w:t>y')  # noqa: E731
    only_failure(run(linked, settings={"no_links_in_notes": True}), "no live hyperlinks in the notes (found 1)")
    assert run(linked, settings={"no_links_in_notes": False}).fails == []
    assert run(linked).fails == []


SECTION = (
    '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/>'
    '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr>'
)


def sections(first=SECTION, last=SECTION):
    def change(parts):
        in_body(parts, "<w:sectPr/>", f"<w:p><w:pPr>{first}</w:pPr></w:p>{last}")

    return change


def test_margins_pass_when_every_section_has_them(run):
    assert "OK   margins 1 inch in every section (2 sections)" in run(sections(), settings={"margins_inches": 1}).lines


def test_fails_a_wide_margin_in_the_second_of_two_sections(run):
    wide = SECTION.replace('w:top="1440"', 'w:top="1800"')
    only_failure(
        run(sections(last=wide), settings={"margins_inches": 1}),
        "margins 1 inch in every section (2 sections): section 2 top 1.25",
    )


def test_fails_a_section_that_sets_no_margins(run):
    only_failure(
        run(sections(last="<w:sectPr/>"), settings={"margins_inches": 1}),
        "margins 1 inch in every section (2 sections): section 2 sets none",
    )


def test_fails_a_document_with_no_sections(run):
    only_failure(
        run(lambda parts: in_body(parts, "<w:sectPr/>", ""), settings={"margins_inches": 1}),
        "margins 1 inch in every section (0 sections): no sections found",
    )


def test_page_size_passes_letter_and_fails_a_section_in_a4(run):
    a4 = SECTION.replace('w:w="12240" w:h="15840"', 'w:w="11906" w:h="16838"')
    assert "OK   page size letter in every section (2 sections)" in run(sections(), settings={"page_size": "letter"}).lines
    assert "OK   page size a4 in every section (1 sections)" in run(lambda parts: in_body(parts, "<w:sectPr/>", a4), settings={"page_size": "a4"}).lines
    only_failure(
        run(sections(first=a4), settings={"page_size": "letter"}),
        "page size letter in every section (2 sections): section 1 is 8.27 by 11.69",
    )


def test_page_size_can_be_given_in_inches(run):
    report = run(sections(), settings={"page_size": [8.5, 11]})
    assert "OK   page size 8.5 by 11 in every section (2 sections)" in report.lines


def test_fails_a_section_with_no_page_size(run):
    only_failure(
        run(sections(last="<w:sectPr/>"), settings={"page_size": "letter"}),
        "page size letter in every section (2 sections): section 2 sets none",
    )


def header(text):
    def change(parts):
        parts["word/header1.xml"] = f"<w:hdr {W}>{p(text)}</w:hdr>"

    return change


def test_headers_footers_empty_fails_text_or_only_notes_it(run):
    only_failure(run(header("Running head"), settings={"headers_footers_empty": True}), "headers and footers empty (text in word/header1.xml)")
    report = run(header("Running head"), settings={"headers_footers_empty": "note"})
    assert "NOTE headers and footers empty (text in word/header1.xml)" in report.lines
    assert report.fails == []
    assert "OK   headers and footers empty" in run(header(" "), settings={"headers_footers_empty": True}).lines
    assert run(header("x"), settings={"headers_footers_empty": False}).fails == []


def test_max_embedded_images_notes_a_manuscript_over_it(run):
    assert "OK   embedded images: 1, at most 1" in run(settings={"max_embedded_images": 1}).lines
    report = run(settings={"max_embedded_images": 0})
    assert "NOTE embedded images: 1, at most 0 (image1.png)" in report.lines
    assert report.fails == []


def test_word_count_passes_in_range_and_fails_out_of_it_counting_body_and_notes(run):
    body = [p("one two three"), "<w:p><w:r><w:t>four</w:t><w:br/><w:t>five</w:t></w:r></w:p>"]
    report = run(body=body, settings={"word_count": [16, 16]})
    assert "OK   word count 16 (body 5, notes 11), wanted 16 to 16" in report.lines
    only_failure(run(body=body, settings={"word_count": [17, 20]}), "word count 16 (body 5, notes 11), wanted 17 to 20")


def test_word_count_does_not_run_paragraphs_together(run):
    assert "OK   word count 15 (body 4, notes 11), wanted 15 to 15" in run(body=[p("one"), p("two"), p("three"), p("four")], settings={"word_count": [15, 15]}).lines


def test_title_must_appear_near_the_start_of_the_body(run):
    assert 'OK   title "A Ledger" in the first 3,000 characters' in run(body=[p("A Ledger")], settings={"title": "A Ledger"}).lines
    late = [p("x" * 3000), p("A Ledger")]
    only_failure(run(body=late, settings={"title": "A Ledger"}), 'title "A Ledger" in the first 3,000 characters')


def test_fails_an_old_title_in_a_note(run):
    assert 'OK   no old title "A Log"' in run(settings={"old_titles": ["A Log"]}).lines
    only_failure(run(lambda parts: in_note(parts, new="See A Log."), settings={"old_titles": ["A Log", "Other"]}), 'no old title "A Log"')


PAIRS = {"open": "begin", "close": "end", "kinds": ["sidebar", "boxed text"], "required": ["sidebar"]}


def test_tag_pairs_pass_when_they_balance(run):
    body = [p("[begin sidebar]"), p("[end sidebar]"), p("[begin boxed text, centered]"), p("[End Boxed Text]")]
    report = run(body=body, settings={"tag_pairs": PAIRS})
    assert "OK   tags balanced: sidebar 1/1" in report.lines
    assert "OK   tags balanced: boxed text 1/1" in report.lines


def test_fails_an_unbalanced_tag_pair(run):
    body = [p("[begin sidebar]"), p("[begin sidebar]"), p("[end sidebar]")]
    only_failure(run(body=body, settings={"tag_pairs": PAIRS}), "tags balanced: sidebar 2/1")


def test_fails_a_required_kind_that_does_not_occur_but_not_an_optional_one(run):
    only_failure(run(body=[p("x")], settings={"tag_pairs": PAIRS}), "tags balanced: sidebar 0/0 (required)")


def test_a_required_kind_need_not_be_listed_again(run):
    pairs = {"open": "start", "close": "stop", "kinds": [], "required": ["Sidebar"]}
    assert "OK   tags balanced: sidebar 1/1" in run(body=[p("[start sidebar]"), p("[stop sidebar]")], settings={"tag_pairs": pairs}).lines


def test_counts_passes_and_fails_each_way_of_saying_what_is_wanted(run):
    body = [p("Map 1 and Map 2"), p("Map 3")]
    settings = {
        "counts": [
            {"name": "maps", "pattern": r"Map \d", "expect": 3},
            {"name": "at least", "pattern": r"Map \d", "min": 1},
            {"name": "at most", "pattern": r"Map \d", "max": 5},
            {"name": "between", "pattern": r"Map \d", "min": 1, "max": 5},
        ]
    }
    assert [line for line in run(body=body, settings=settings).lines if "Map" in line or ": 3" in line] == [
        "OK   maps: 3 (expected 3)",
        "OK   at least: 3 (at least 1)",
        "OK   at most: 3 (at most 5)",
        "OK   between: 3 (at least 1, at most 5)",
    ]
    only_failure(run(body=body, settings={"counts": [{"name": "maps", "pattern": r"Map \d", "expect": 2}]}), "maps: 3 (expected 2)")
    only_failure(run(body=body, settings={"counts": [{"name": "maps", "pattern": r"Map \d", "min": 4}]}), "maps: 3 (at least 4)")
    only_failure(run(body=body, settings={"counts": [{"name": "maps", "pattern": r"Map \d", "max": 2}]}), "maps: 3 (at most 2)")


def test_a_count_pattern_with_a_group_still_counts_matches(run):
    report = run(body=[p("a1 a2")], settings={"counts": [{"name": "as", "pattern": r"a(\d)", "expect": 2}]})
    assert report.fails == []


def test_a_count_pattern_reads_the_text_as_word_shows_it_across_runs_not_markers(run):
    def change(parts):
        in_body(parts, "The log for March is missing.", "Ma")
        in_body(parts, '<w:endnoteReference w:id="2"/></w:r></w:p>', '<w:endnoteReference w:id="2"/></w:r><w:r><w:t>p 1</w:t></w:r></w:p>')

    assert run(change, settings={"counts": [{"name": "maps", "pattern": "Map 1", "expect": 1}]}).fails == []


def test_a_count_of_the_body_does_not_look_in_the_notes(run):
    only_failure(run(lambda parts: in_note(parts, new="Map 1"), settings={"counts": [{"name": "maps", "pattern": "Map 1", "min": 1}]}), "maps: 0 (at least 1)")


FIGURES = {
    "callout": r"\[Figure (\d+\.\d+)\]",
    "caption": r"\[([^\]]+)\]",
    "credit": r"\[Credit: ([^\]]*)\]",
    "expect": 2,
    "caption_no_full_stop": True,
}


def figure(number, caption="A lamp", credit="The Keeper"):
    return [p(f"[Figure {number}]"), p(f"[{caption}]"), p(f"[Credit: {credit}]")]


def test_figures_pass_with_three_lines_each_the_expected_count_credits_and_captions(run):
    report = run(body=[*figure("1.1"), p(""), p("Text."), *figure("2.1")], settings={"figures": FIGURES})
    assert report.fails == []
    assert "OK   figures: 2, each a callout, caption and credit line (expected 2)" in report.lines
    assert "OK   every figure credit line filled" in report.lines
    assert "OK   no figure caption ends with a full stop" in report.lines


def test_empty_lines_between_a_figure_s_lines_do_not_matter(run):
    a, b, c = figure("1.1")
    assert run(body=[a, p(""), b, p(" "), c, *figure("2.1")], settings={"figures": FIGURES}).fails == []


def test_fails_the_wrong_number_of_figures(run):
    only_failure(run(body=figure("1.1"), settings={"figures": FIGURES}), "figures: 1, each a callout, caption and credit line (expected 2)")


def test_expect_may_be_left_out_of_figures(run):
    settings = {key: value for key, value in FIGURES.items() if key != "expect"}
    assert "OK   figures: 1, each a callout, caption and credit line" in run(body=figure("1.1"), settings={"figures": settings}).lines


def test_fails_a_callout_without_its_caption_and_credit(run):
    report = run(body=[*figure("1.1"), p("[Figure 2.1]"), p("Text at once.")], settings={"figures": {**FIGURES, "expect": 1}})
    only_failure(report, "figures: 1, each a callout, caption and credit line (expected 1): incomplete 2.1")


def test_fails_a_callout_at_the_very_end_of_the_body(run):
    report = run(lambda parts: in_body(parts, "<w:sectPr/>", '<w:p><w:r><w:t>[Figure 2.1]</w:t></w:r></w:p><w:sectPr/>'), body=figure("1.1"), settings={"figures": {**FIGURES, "expect": 1}})
    only_failure(report, "figures: 1, each a callout, caption and credit line (expected 1): incomplete 2.1")


def test_fails_an_empty_credit_line(run):
    only_failure(run(body=[*figure("1.1", credit=""), *figure("2.1")], settings={"figures": FIGURES}), "every figure credit line filled (not filled: 1.1)")


def test_fails_a_placeholder_in_a_credit_line_as_well_as_the_placeholder_check(run):
    report = run(body=[*figure("1.1", credit="XXX"), *figure("2.1")], settings={"figures": FIGURES, "placeholders": ["XXX"]})
    assert report.fails == ["no placeholder XXX (found 1)", "every figure credit line filled (not filled: 1.1)"]


def test_fails_a_caption_ending_with_a_full_stop(run):
    only_failure(run(body=[*figure("1.1", caption="A lamp."), *figure("2.1")], settings={"figures": FIGURES}), "no figure caption ends with a full stop (ending so: 1.1)")


def test_a_full_stop_is_allowed_unless_the_setting_says_otherwise(run):
    settings = {key: value for key, value in FIGURES.items() if key != "caption_no_full_stop"}
    assert run(body=[*figure("1.1", caption="A lamp."), *figure("2.1")], settings={"figures": settings}).fails == []


def test_patterns_with_no_group_use_the_whole_match(run):
    settings = {"callout": r"Fig \d", "caption": "Caption", "credit": "Credit"}
    report = run(body=[p("Fig 1"), p("Caption"), p("Credit"), p("Fig 2"), p("nothing")], settings={"figures": settings})
    only_failure(report, "figures: 1, each a callout, caption and credit line: incomplete Fig 2")


def test_tables_must_each_be_named(run):
    body = [p("Table 1.1 Oil used"), p("See Table II.1 and Table 1.10 here.")]
    assert "OK   tables named: 1.1, II.1" in run(body=body, settings={"tables": ["1.1", "II.1"]}).lines
    only_failure(run(body=body, settings={"tables": ["1.1", "1.2", "1"]}), "tables named: 1.1 (missing: 1.2, 1)")


LISTED = {"from": "List of Figures", "to": "Dedication"}


def book(entries, *figures):
    return [p("List of Figures"), *[p(entry) for entry in entries], p("Dedication"), *[line for f in figures for line in f]]


def test_the_list_names_every_figure_with_its_caption_ignoring_a_number_at_the_end(run):
    body = book(["Figure 1.1 A lamp", "Figure 2.1 A log"], figure("1.1"), figure("2.1", caption="A log3"))
    report = run(body=body, settings={"figures": FIGURES, "list_of_figures": LISTED})
    assert 'OK   "List of Figures" names every figure' in report.lines
    assert report.fails == []


def test_fails_a_figure_missing_from_the_list(run):
    body = book(["Figure 1.1 A lamp"], figure("1.1"), figure("2.1", caption="A log"))
    only_failure(run(body=body, settings={"figures": FIGURES, "list_of_figures": LISTED}), '"List of Figures" names every figure (missing: Figure 2.1 A log)')


def test_only_the_text_between_the_two_headings_counts_as_the_list(run):
    body = [p("Figure 1.1 A lamp"), *book([], figure("1.1"), figure("2.1"))]
    assert run(body=body, settings={"figures": FIGURES, "list_of_figures": LISTED}).fails == [
        '"List of Figures" names every figure (missing: Figure 1.1 A lamp, Figure 2.1 A lamp)'
    ]


def test_an_entry_can_be_worded_otherwise(run):
    body = book(["Fig. 1.1: A lamp", "Fig. 2.1: A lamp"], figure("1.1"), figure("2.1"))
    listed = {**LISTED, "entry": "Fig. {number}: {caption}"}
    assert run(body=body, settings={"figures": FIGURES, "list_of_figures": listed}).fails == []


def test_fails_when_either_heading_of_the_list_is_not_found(run):
    said = '"List of Figures" to "Dedication" found in the body'
    only_failure(run(body=[*figure("1.1"), *figure("2.1"), p("List of Figures")], settings={"figures": FIGURES, "list_of_figures": LISTED}), said)
    only_failure(run(body=[p("Dedication"), p("List of Figures"), *figure("1.1"), *figure("2.1")], settings={"figures": FIGURES, "list_of_figures": LISTED}), said)


def test_allow_placeholders_also_softens_credit_lines_and_marked_counts(run):
    settings = {
        "figures": {**FIGURES, "expect": 1},
        "counts": [
            {"name": "unfilled links", "pattern": "TKTKTK", "expect": 0, "placeholder": True},
            {"name": "plain", "pattern": "nothing", "min": 1},
        ],
    }
    report = run(body=figure("1.1", credit=""), settings=settings, allow_placeholders=True)
    assert "NOTE every figure credit line filled (not filled: 1.1)" in report.lines
    assert report.fails == ["plain: 0 (at least 1)"]
    marked = run(body=[p("TKTKTK"), *figure("1.1")], settings=settings, allow_placeholders=True)
    assert "NOTE unfilled links: 1 (expected 0)" in marked.lines
    failed = run(body=[p("TKTKTK"), *figure("1.1")], settings=settings)
    assert "unfilled links: 1 (expected 0)" in failed.fails


def test_a_setting_left_out_prints_no_line_for_its_check(run):
    lines = "\n".join(run().lines)
    for word in ("margins", "page size", "word count", "title", "tags balanced", "figures", "tables", "embedded"):
        assert word not in lines
