"""What a manuscript says, as Word shows it, paragraph by paragraph."""

import re
from collections import Counter

from wordtools.paragraph import Paragraph
from wordtools.text import nfc
from wordtools.xmlscan import paragraph_spans

# Word stores a text box twice, once for old readers; only the first copy is read.
FALLBACK = re.compile(r"<mc:Fallback\b.*?</mc:Fallback>", re.S)
OWN_STYLE = re.compile(
    r"<w:p\b[^>]*>\s*<w:pPr\b[^>]*>(?:(?!</w:pPr>).)*?<w:pStyle w:val=\"([^\"]*)\"", re.S
)
HEADINGS = ("Title", *(f"Heading{level}" for level in range(1, 10)))
HIGHLIGHT = re.compile(r'<w:highlight\b[^>]*\bw:val="([^"]*)"')


def paragraph_texts(xml):
    """The text of every paragraph of a part, text boxes included, as Word shows it."""
    xml = FALLBACK.sub("", xml)
    return [Paragraph(xml[start:end]).text for start, end, _ in paragraph_spans(xml)]


def placeholder_count(texts, placeholder):
    """How many times `placeholder` appears within the paragraphs `texts`."""
    needle = nfc(placeholder)
    return sum(nfc(text).count(needle) for text in texts)


def own_style(paragraph):
    """The style id set in a paragraph's own properties, or None."""
    found = OWN_STYLE.match(paragraph)
    return found.group(1) if found else None


def heading_counts(xml):
    """How many paragraphs of a part carry each heading style, in outline order. A
    paragraph inside a text box is not one of the book's headings."""
    styles = Counter(
        own_style(xml[start:end]) for start, end, depth in paragraph_spans(xml) if depth == 1
    )
    return {name: styles[name] for name in HEADINGS if styles[name]}


def tag_pattern(opening, closing):
    """A regular expression for one bracketed tag, with these opening and closing words."""
    return re.compile(
        rf"\[\s*(?P<word>{re.escape(opening)}|{re.escape(closing)})\s+"
        r"(?P<kind>[^\[\],]*[^\[\],\s])\s*(?:,(?P<variant>[^\[\]]*))?\]",
        re.I,
    )


def tag_kind(text):
    """A tag's kind as it is compared: lowercased, its spaces single."""
    return " ".join(text.lower().split())


def tag_counts(texts, opening, closing):
    """{kind: (opening tags, closing tags)} for the bracketed tags in the paragraphs `texts`."""
    pattern = tag_pattern(opening, closing)
    found = {}
    for text in texts:
        for tag in pattern.finditer(text):
            kind = tag_kind(tag.group("kind"))
            opens, closes = found.get(kind, (0, 0))
            if tag.group("word").lower() == opening.lower():
                found[kind] = (opens + 1, closes)
            else:
                found[kind] = (opens, closes + 1)
    return dict(sorted(found.items()))


def highlight_colours(xml):
    """[(colour, number of highlights)] in `xml`, the most common first."""
    colours = Counter(HIGHLIGHT.findall(xml))
    return sorted(colours.items(), key=lambda item: (-item[1], item[0]))
