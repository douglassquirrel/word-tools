"""A paragraph's fonts and indents, through Word's chain of style inheritance."""

import html
import re
from collections import namedtuple

from wordtools.paragraph import Paragraph
from wordtools.xmlscan import paragraph_spans, parse

SIDES = {"left": "left", "start": "left", "right": "right", "end": "right"}
SIDES.update(firstLine="firstLine", hanging="hanging")
SIDE = re.compile(r'\bw:(left|start|right|end|firstLine|hanging)="(-?\d+)"')
Style = namedtuple("Style", "based_on font indent numbered")
Run = namedtuple("Run", "text font")


def _child(node, name):
    if node is None:
        return None
    return next((child for child in node.children if child.name == name), None)


def _value(node, name="w:val"):
    found = re.search(rf'\b{name}="([^"]*)"', node.attrs) if node is not None else None
    return html.unescape(found.group(1)) if found else None


def _font(properties):
    """The font named in a <w:rPr>, if any: the one Word uses for Latin text."""
    fonts = _child(properties, "w:rFonts")
    return _value(fonts, "w:ascii") or _value(fonts, "w:hAnsi")


def _indent(properties):
    """The indents set in a <w:pPr> itself, in twentieths of a point, by side."""
    indent = _child(properties, "w:ind")
    if indent is None:
        return {}
    return {SIDES[side]: int(value) for side, value in SIDE.findall(indent.attrs)}


def _merged(base, own):
    """Indents `own` laid over `base`. A first-line and a hanging indent are one setting."""
    result = dict(base)
    if "firstLine" in own:
        result.pop("hanging", None)
    if "hanging" in own:
        result.pop("firstLine", None)
    result.update(own)
    return result


def _numbered(properties):
    """True or False if a <w:pPr> says whether its paragraph is in a list, else None."""
    numbering = _child(properties, "w:numPr")
    if numbering is None:
        return None
    return _value(_child(numbering, "w:numId")) != "0"


class Styles:
    """What each style of a document gives, read from its styles part."""

    def __init__(self, styles_xml):
        root = parse(styles_xml)
        self._styles = {}
        self.default = "Normal"
        for style in root.children:
            if style.name != "w:style":
                continue
            properties = _child(style, "w:pPr")
            self._styles[_value(style, "w:styleId")] = Style(
                _value(_child(style, "w:basedOn")),
                _font(_child(style, "w:rPr")),
                _indent(properties),
                _numbered(properties),
            )
            if _value(style, "w:default") == "1" and _value(style, "w:type") == "paragraph":
                self.default = _value(style, "w:styleId")
        defaults = _child(root, "w:docDefaults")
        self._font = _font(_child(_child(defaults, "w:rPrDefault"), "w:rPr"))
        self._indent = _indent(_child(_child(defaults, "w:pPrDefault"), "w:pPr"))

    def _chain(self, style_id):
        """A style and what it is based on, nearest first."""
        chain, seen = [], set()
        while style_id in self._styles and style_id not in seen:
            seen.add(style_id)
            chain.append(self._styles[style_id])
            style_id = chain[-1].based_on
        return chain

    def indent(self, style_id):
        """The indents a paragraph style gives, through what it is based on."""
        result = self._indent
        for style in reversed(self._chain(style_id)):
            result = _merged(result, style.indent)
        return result

    def numbered(self, style_id):
        """Whether a paragraph style puts its paragraphs in a list."""
        return next((s.numbered for s in self._chain(style_id) if s.numbered is not None), False)

    def font(self, paragraph_style, run_style):
        """The font a run with none of its own takes from its styles, or None."""
        for style in self._chain(run_style) + self._chain(paragraph_style):
            if style.font:
                return style.font
        return self._font


class Block:
    """One paragraph: its text, its style, its effective layout and its runs."""

    def __init__(self, xml, styles, default_font):
        root = parse(xml)
        properties = _child(root, "w:pPr")
        self.style = _value(_child(properties, "w:pStyle")) or styles.default
        indent = _merged(styles.indent(self.style), _indent(properties))
        self.left = indent.get("left", 0)
        self.right = indent.get("right", 0)
        self.first_line = indent.get("firstLine", 0) - indent.get("hanging", 0)
        self.hanging = indent.get("hanging", 0) != 0
        own = _numbered(properties)
        self.numbered = styles.numbered(self.style) if own is None else own
        paragraph = Paragraph(xml)
        self.text = paragraph.text
        grouped = {}
        for piece in paragraph.pieces:
            grouped.setdefault(id(piece.run), (piece.run, []))[1].extend(piece.units)
        self.runs = []
        for run, units in grouped.values():
            properties = _child(run, "w:rPr")
            font = _font(properties) or styles.font(
                self.style, _value(_child(properties, "w:rStyle"))
            )
            self.runs.append(Run("".join(html.unescape(u) for u in units), font or default_font))
        self.fonts = sorted({run.font for run in self.runs if run.text.strip()}, key=str)


def blocks(xml, styles, default_font=None):
    """The paragraphs of the body, as Blocks, leaving out those inside a text box."""
    return [
        Block(xml[start:end], styles, default_font)
        for start, end, depth in paragraph_spans(xml)
        if depth == 1
    ]
