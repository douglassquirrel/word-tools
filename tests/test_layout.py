import pytest

from tests.samples import W
from wordtools.layout import Styles, blocks

pytestmark = pytest.mark.tier1

STYLES = f"""<w:styles {W}>
<w:docDefaults>
  <w:rPrDefault><w:rPr><w:rFonts w:ascii="Doc Serif" w:hAnsi="Doc Serif"/></w:rPr></w:rPrDefault>
  <w:pPrDefault><w:pPr><w:ind w:right="100"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
<w:style w:type="paragraph" w:styleId="Quote"><w:name w:val="Quote"/><w:basedOn w:val="Normal"/>
  <w:pPr><w:ind w:left="720" w:firstLine="360"/></w:pPr>
  <w:rPr><w:rFonts w:ascii="Quote Face"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="DeepQuote"><w:name w:val="Deep"/><w:basedOn w:val="Quote"/>
  <w:pPr><w:ind w:left="1440" w:hanging="200"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Listed"><w:name w:val="Listed"/>
  <w:pPr><w:numPr><w:numId w:val="3"/></w:numPr></w:pPr></w:style>
<w:style w:type="character" w:styleId="Code"><w:name w:val="Code"/>
  <w:rPr><w:rFonts w:ascii="Code Face"/></w:rPr></w:style>
<w:style w:type="character" w:styleId="MoreCode"><w:name w:val="More"/><w:basedOn w:val="Code"/></w:style>
<w:style w:type="paragraph" w:styleId="Looped"><w:name w:val="Looped"/><w:basedOn w:val="Looped"/></w:style>
</w:styles>"""


def body(*paragraphs):
    return f"<w:document {W}><w:body>{''.join(paragraphs)}</w:body></w:document>"


def one(paragraph, styles=STYLES, default_font="Fallback"):
    return blocks(body(paragraph), Styles(styles), default_font)[0]


def test_joins_the_text_of_a_paragraph_and_keeps_its_runs_apart():
    block = one("<w:p><w:r><w:t>one </w:t></w:r><w:r><w:t>two</w:t></w:r></w:p>")
    assert block.text == "one two"
    assert [run.text for run in block.runs] == ["one ", "two"]


def test_reads_paragraphs_in_tables_but_not_those_in_text_boxes():
    found = blocks(
        body(
            "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>cell</w:t></w:r></w:p></w:tc></w:tr></w:tbl>",
            "<w:p><w:r><w:drawing><w:p><w:r><w:t>boxed</w:t></w:r></w:p></w:drawing></w:r></w:p>",
        ),
        Styles(STYLES),
        "Fallback",
    )
    assert [block.text for block in found] == ["cell", ""]


def test_a_run_s_own_font_comes_first():
    block = one(
        '<w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:rPr><w:rStyle w:val="Code"/><w:rFonts w:ascii="Mine"/></w:rPr>'
        "<w:t>x</w:t></w:r></w:p>"
    )
    assert block.runs[0].font == "Mine"


def test_takes_hansi_when_a_run_names_no_ascii_font():
    block = one('<w:p><w:r><w:rPr><w:rFonts w:hAnsi="Other"/></w:rPr><w:t>x</w:t></w:r></w:p>')
    assert block.runs[0].font == "Other"


def test_a_character_style_comes_before_the_paragraph_style_and_follows_its_base():
    block = one(
        '<w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr>'
        '<w:r><w:rPr><w:rStyle w:val="MoreCode"/></w:rPr><w:t>x</w:t></w:r></w:p>'
    )
    assert block.runs[0].font == "Code Face"


def test_a_paragraph_style_gives_its_font_to_a_run_with_none_through_what_it_is_based_on():
    block = one('<w:p><w:pPr><w:pStyle w:val="DeepQuote"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>')
    assert block.runs[0].font == "Quote Face"


def test_the_document_defaults_come_after_the_styles():
    assert one("<w:p><w:r><w:t>x</w:t></w:r></w:p>").runs[0].font == "Doc Serif"


def test_the_rules_default_font_comes_last():
    plain = f"<w:styles {W}/>"
    assert one("<w:p><w:r><w:t>x</w:t></w:r></w:p>", plain).runs[0].font == "Fallback"


def test_lists_the_fonts_of_non_blank_runs_only():
    block = one(
        '<w:p><w:r><w:rPr><w:rFonts w:ascii="Blank"/></w:rPr><w:t xml:space="preserve">  </w:t></w:r>'
        '<w:r><w:rPr><w:rFonts w:ascii="Seen"/></w:rPr><w:t>x</w:t></w:r>'
        "<w:r><w:t>y</w:t></w:r></w:p>"
    )
    assert block.fonts == ["Doc Serif", "Seen"]


def test_leaves_out_a_run_with_only_a_tracked_deletion():
    block = one(
        '<w:p><w:del w:id="1"><w:r><w:rPr><w:rFonts w:ascii="Gone"/></w:rPr>'
        "<w:delText>x</w:delText></w:r></w:del><w:r><w:t>y</w:t></w:r></w:p>"
    )
    assert block.fonts == ["Doc Serif"]


def test_indents_default_to_nothing_set_anywhere():
    block = one("<w:p><w:r><w:t>x</w:t></w:r></w:p>", f"<w:styles {W}/>")
    assert (block.left, block.right, block.first_line) == (0, 0, 0)


def test_indents_come_from_the_document_defaults_and_the_style_chain():
    block = one('<w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>')
    assert (block.left, block.right, block.first_line) == (720, 100, 360)


def test_a_paragraph_s_own_indent_wins_side_by_side():
    block = one(
        '<w:p><w:pPr><w:pStyle w:val="Quote"/><w:ind w:left="0"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>'
    )
    assert (block.left, block.right, block.first_line) == (0, 100, 360)


def test_a_hanging_indent_replaces_an_inherited_first_line_and_counts_as_negative():
    block = one('<w:p><w:pPr><w:pStyle w:val="DeepQuote"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>')
    assert (block.left, block.first_line, block.hanging) == (1440, -200, True)


def test_a_first_line_replaces_an_inherited_hanging_indent():
    block = one(
        '<w:p><w:pPr><w:pStyle w:val="DeepQuote"/><w:ind w:firstLine="50"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>'
    )
    assert (block.first_line, block.hanging) == (50, False)


def test_reads_start_and_end_as_left_and_right():
    block = one('<w:p><w:pPr><w:ind w:start="11" w:end="22"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>')
    assert (block.left, block.right) == (11, 22)


def test_ignores_the_old_indent_kept_by_a_tracked_format_change():
    block = one(
        '<w:p><w:pPr><w:pPrChange w:id="1"><w:pPr><w:ind w:left="999"/></w:pPr></w:pPrChange></w:pPr>'
        "<w:r><w:t>x</w:t></w:r></w:p>"
    )
    assert block.left == 0


def test_says_whether_a_paragraph_is_numbered_by_itself_or_by_its_style():
    own = '<w:p><w:pPr><w:numPr><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t>x</w:t></w:r></w:p>'
    styled = '<w:p><w:pPr><w:pStyle w:val="Listed"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>'
    assert (one(own).numbered, one(styled).numbered) == (True, True)


def test_number_id_nought_takes_a_paragraph_out_of_a_list():
    block = one(
        '<w:p><w:pPr><w:pStyle w:val="Listed"/><w:numPr><w:numId w:val="0"/></w:numPr></w:pPr><w:r><w:t>x</w:t></w:r></w:p>'
    )
    assert block.numbered is False


def test_a_plain_paragraph_is_not_numbered():
    assert one("<w:p><w:r><w:t>x</w:t></w:r></w:p>").numbered is False


def test_gives_the_paragraph_its_style_or_the_default_one():
    styled = one('<w:p><w:pPr><w:pStyle w:val="Quote"/></w:pPr></w:p>')
    plain = one("<w:p/>")
    assert (styled.style, plain.style) == ("Quote", "Normal")


def test_a_style_based_on_itself_does_not_hang():
    assert one('<w:p><w:pPr><w:pStyle w:val="Looped"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>').left == 0


def test_a_style_the_document_does_not_define_is_treated_as_having_nothing_set():
    block = one('<w:p><w:pPr><w:pStyle w:val="Nowhere"/></w:pPr><w:r><w:t>x</w:t></w:r></w:p>')
    assert (block.left, block.runs[0].font) == (0, "Doc Serif")
