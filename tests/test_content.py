import pytest

from tests.samples import W
from wordtools.content import (
    heading_counts,
    highlight_colours,
    paragraph_texts,
    placeholder_count,
    tag_counts,
)

pytestmark = pytest.mark.tier1


def body(*paragraphs):
    return f"<w:document {W}><w:body>{''.join(paragraphs)}<w:sectPr/></w:body></w:document>"


def test_joins_the_runs_of_a_paragraph_and_keeps_paragraphs_apart():
    xml = body(
        "<w:p><w:r><w:t>TK</w:t></w:r><w:r><w:t>TK</w:t></w:r></w:p>",
        "<w:p><w:r><w:t>second</w:t></w:r></w:p>",
    )
    assert paragraph_texts(xml) == ["TKTK", "second"]


def test_shows_entities_as_the_characters_they_stand_for():
    assert paragraph_texts(body("<w:p><w:r><w:t>Salt &amp; oil</w:t></w:r></w:p>")) == ["Salt & oil"]


def test_counts_an_empty_paragraph_as_empty_text():
    assert paragraph_texts(body("<w:p/>")) == [""]


def test_leaves_out_text_struck_out_by_a_tracked_deletion():
    xml = body(
        "<w:p><w:r><w:t>kept </w:t></w:r>"
        '<w:del w:id="1"><w:r><w:delText>gone</w:delText></w:r></w:del>'
        '<w:ins w:id="2"><w:r><w:t>added</w:t></w:r></w:ins></w:p>'
    )
    assert paragraph_texts(xml) == ["kept added"]


def test_reads_a_text_box_once_though_the_xml_holds_it_twice():
    box = "<w:txbxContent><w:p><w:r><w:t>In the box</w:t></w:r></w:p></w:txbxContent>"
    xml = body(
        "<w:p><w:r><w:t>Outside</w:t></w:r><w:r><mc:AlternateContent>"
        f"<mc:Choice><w:drawing>{box}</w:drawing></mc:Choice>"
        f"<mc:Fallback><w:pict>{box}</w:pict></mc:Fallback>"
        "</mc:AlternateContent></w:r></w:p>"
    )
    assert paragraph_texts(xml) == ["Outside", "In the box"]


def test_counts_a_placeholder_split_across_runs():
    texts = paragraph_texts(body("<w:p><w:r><w:t>a TKT</w:t></w:r><w:r><w:t>KTK b TKTKTK</w:t></w:r></w:p>"))
    assert placeholder_count(texts, "TKTKTK") == 2


def test_does_not_find_a_placeholder_across_a_paragraph_break():
    assert placeholder_count(["TKT", "KTK"], "TKTKTK") == 0


def test_counts_a_longer_run_of_the_placeholder_once():
    assert placeholder_count(["https://TKTKTKTK"], "TKTKTK") == 1


def test_matches_a_placeholder_whatever_the_unicode_spelling():
    assert placeholder_count(["café"], "café") == 1


def styled(style, text="x"):
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/></w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>'


def test_counts_title_and_headings_by_style_in_outline_order():
    xml = body(styled("Heading2"), styled("Title"), styled("Heading1"), styled("Heading2"), styled("Heading9"))
    assert heading_counts(xml) == {"Title": 1, "Heading1": 1, "Heading2": 2, "Heading9": 1}


def test_ignores_styles_that_are_not_headings():
    xml = body(styled("BlockQuote"), styled("Heading10"), "<w:p><w:r><w:t>plain</w:t></w:r></w:p>")
    assert heading_counts(xml) == {}


def test_takes_a_heading_style_only_from_the_paragraph_itself_not_a_text_box_inside_it():
    xml = body(
        "<w:p><w:r><w:drawing><w:txbxContent>"
        + styled("BlockQuote")
        + "</w:txbxContent></w:drawing></w:r></w:p>",
        "<w:p><w:r><w:drawing><w:txbxContent>"
        + styled("Heading1")
        + "</w:txbxContent></w:drawing></w:r></w:p>",
    )
    assert heading_counts(xml) == {}


def tags(*texts, opening="begin", closing="end"):
    return tag_counts(list(texts), opening, closing)


def test_counts_opening_and_closing_tags_of_each_kind():
    assert tags("[begin sidebar]", "words", "[end sidebar]", "[begin block quote]") == {
        "block quote": (1, 0),
        "sidebar": (1, 1),
    }


def test_treats_variants_case_and_inner_spaces_as_the_same_kind():
    found = tags("[begin boxed text]", "[ begin boxed text, centered ]", "[End Boxed Text]")
    assert found == {"boxed text": (2, 1)}


def test_finds_a_tag_in_the_middle_of_a_paragraph():
    assert tags("Before [begin sidebar] after [end sidebar].") == {"sidebar": (1, 1)}


@pytest.mark.parametrize(
    "text", ["[beginning of time]", "[begin]", "[begin ]", "[begin , x]", "[endless]", "begin sidebar", "[begin sidebar"]
)
def test_does_not_take_these_for_tags(text):
    assert tags(text) == {}


def test_opening_and_closing_words_can_be_chosen():
    found = tags("[start sidebar]", "[stop sidebar]", "[begin sidebar]", opening="start", closing="stop")
    assert found == {"sidebar": (1, 1)}


def test_a_word_with_a_regex_character_in_it_is_taken_literally():
    assert tags("[o.k sidebar]", "[oxk sidebar]", opening="o.k", closing="end") == {"sidebar": (1, 0)}


def test_collapses_runs_of_spaces_inside_a_kind():
    assert tags("[begin  boxed   text]", "[end boxed text]") == {"boxed text": (1, 1)}


def test_counts_highlights_by_colour_most_common_first():
    xml = (
        '<w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr></w:r>'
        '<w:r><w:rPr><w:highlight w:val="white"/></w:rPr></w:r>'
        '<w:r><w:rPr><w:highlight w:val="white"/></w:rPr></w:r>'
    )
    assert highlight_colours(xml) == [("white", 2), ("yellow", 1)]


def test_has_no_colours_where_nothing_is_highlighted():
    assert highlight_colours("<w:r><w:t>plain</w:t></w:r>") == []
