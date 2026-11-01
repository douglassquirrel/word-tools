"""The checks of check-tags: a manuscript's bracketed production tags against a rules file."""

import re
from collections import Counter

from wordtools.content import tag_kind, tag_pattern
from wordtools.rules import rule_key
from wordtools.text import nfc

FIRST_WORDS = 35
TYPED_LIST = re.compile(r"[-–—•]")
TWIPS_IN_AN_INCH = 1440
SIDES = (("left", "left"), ("right", "right"), ("first", "first_line"))


class Box:
    """What lies between an opening tag and the tag that closes it."""

    def __init__(self, index, text, kind, variant, heading, worded):
        self.index = index
        self.text = text
        self.kind = kind
        self.variant = variant
        self.heading = heading
        self.worded = worded  # whether the opening tag is one of the allowed wordings
        self.content = []  # (index, block) of each paragraph with text in it
        self.closed = False

    @property
    def start(self):
        """The text of the first paragraph with text in it."""
        return self.content[0][1].text.strip() if self.content else ""


class Result:
    def __init__(self, problems, tags, pairs, fonts):
        self.problems = problems  # lines, in document order
        self.tags = tags  # how many tags
        self.pairs = pairs  # the closed Boxes, in document order
        self.fonts = fonts  # {font: how many paragraphs have a run in it}


def _starts(text, start):
    return nfc(text).startswith(nfc(start))


def _inches(twips):
    return f"{twips / TWIPS_IN_AN_INCH:.2f}"


class _Check:
    def __init__(self, blocks, rules):
        self.blocks = blocks
        self.rules = rules
        self.found = []  # (index, the box or None, what is wrong)
        self.headings = []  # the heading above each paragraph
        self.boxes = []
        self.loose = []  # (index, block) of the paragraphs outside every box
        self.tags = 0

    def pair(self):
        """Find the tags, pair them, and check each one's wording and font."""
        pattern = tag_pattern(self.rules["open"], self.rules["close"])
        opening = self.rules["open"].lower()
        heading = "(start)"
        box = None
        for index, block in enumerate(self.blocks):
            text = block.text.strip()
            if text and block.style in self.rules["heading_styles"]:
                heading = text
            self.headings.append(heading)
            tag = pattern.match(text)
            if not tag:
                if box is None:
                    self.loose.append((index, block))
                elif text:
                    box.content.append((index, block))
                continue
            self.tags += 1
            worded = text in self.rules["allowed"]
            kind = tag_kind(tag.group("kind"))
            owner = None
            if tag.group("word").lower() == opening:
                if box is not None:
                    self.found.append(
                        (box.index, box, f'"{box.text}" was not closed before the next tag opened')
                    )
                box = owner = Box(index, text, kind, tag.group("variant"), heading, worded)
                self.boxes.append(box)
            elif box is None:
                self.found.append((index, None, f'"{text}" closes nothing'))
            else:
                owner = box
                box.closed = True
                if box.kind != kind and box.worded and worded:
                    self.found.append(
                        (index, box, f'"{text}" closes a box opened by "{box.text}"')
                    )
                box = None
            if not worded:
                self.found.append((index, owner, f'tag wording "{text}"'))
            self._tag_font(index, block, text, owner)
        if box is not None:
            self.found.append((box.index, box, f'"{box.text}" is never closed'))

    def _tag_font(self, index, block, text, box):
        wanted = self.rules["tag_font"]
        if wanted and block.fonts != [wanted]:
            fonts = ", ".join(block.fonts)
            self.found.append((index, box, f'tag "{text}" in {fonts} (want {wanted})'))

    def contents(self):
        """Check what lies inside each closed box."""
        for box in self.boxes:
            if box.closed and not self._skipped(box):
                rule = self._rule(box)
                for place, (index, block) in enumerate(box.content):
                    self._paragraph(box, rule, place, index, block)

    def _skipped(self, box):
        return any(_starts(box.start, start) for start in self.rules["skip_boxes_starting"])

    def _rule(self, box):
        """The rule for a box: its kind and variant's, or its kind's, then any exception."""
        kinds = self.rules["kinds"]
        rule = kinds.get(rule_key(box.kind, box.variant), kinds.get(box.kind, {}))
        for exception in self.rules["box_exceptions"]:
            if _starts(box.start, exception["starts_with"]):
                return {**rule, **exception}
        return rule

    def _exception(self, block):
        for exception in self.rules["paragraph_exceptions"]:
            if _starts(block.text.strip(), exception["starts_with"]):
                return exception
        return {}

    def _paragraph(self, box, rule, place, index, block):
        exception = self._exception(block)
        if exception.get("skip"):
            return
        said = self._fonts(box, rule, index, block)
        self._elsewhere(box, rule, index, block, said)
        self._indent(box, rule, place, index, block, exception)

    def _fonts(self, box, rule, index, block):
        """Check the fonts of a paragraph in a box; return those found at fault."""
        said = []
        if "font" in rule and block.fonts and block.fonts != [rule["font"]]:
            said = [font for font in block.fonts if font != rule["font"]]
            shown = ", ".join(block.fonts)
            self.found.append((index, box, f"font {shown} (want {rule['font']})"))
        barred = [font for font in block.fonts if font in rule.get("not_fonts", ())]
        if barred:
            self.found.append((index, box, f"font {', '.join(barred)} (not allowed here)"))
        return said + barred

    def _elsewhere(self, box, rule, index, block, said=()):
        for font, kinds in self.rules["only_inside"].items():
            if font not in block.fonts or font in said or rule.get("font") == font:
                continue
            if box is None or not {rule_key(box.kind, box.variant), box.kind} & set(kinds):
                self.found.append((index, box, f"{font} outside a box that allows it"))

    def _indent(self, box, rule, place, index, block, exception):
        listed = block.numbered or block.hanging or TYPED_LIST.match(block.text.strip())
        if rule.get("skip_numbered") and listed:
            return
        wanted = dict(exception.get("indent", rule.get("indent", {})))
        if place and "first_line_after_first" in rule and "indent" not in exception:
            wanted["first_line"] = rule["first_line_after_first"]
        actual = {"left": block.left, "right": block.right, "first_line": block.first_line}
        if any(round(inches * TWIPS_IN_AN_INCH) != actual[s] for s, inches in wanted.items()):
            shown = " ".join(f"{word} {_inches(actual[side])}" for word, side in SIDES)
            want = " ".join(f"{word} {wanted[side]:.2f}" for word, side in SIDES if side in wanted)
            self.found.append((index, box, f"indent {shown} (want {want})"))

    def outside(self):
        """Check the paragraphs outside every box for fonts kept to the inside of one."""
        for index, block in self.loose:
            if not self._exception(block).get("skip"):
                self._elsewhere(None, {}, index, block)

    def lines(self):
        """Each thing found, as one line, in document order."""
        lines = []
        for index, box, what in sorted(self.found, key=lambda item: item[0]):
            if box is None:
                heading, start = self.headings[index], self.blocks[index].text.strip()
            else:
                heading, start = box.heading, box.start
            lines.append(f'{heading} ("{start[:FIRST_WORDS]}"): {what}')
        return lines


def check(blocks, rules):
    """Check the paragraphs `blocks` against `rules`; return a Result."""
    run = _Check(blocks, rules)
    run.pair()
    run.contents()
    run.outside()
    fonts = Counter(font for block in blocks for font in block.fonts)
    return Result(run.lines(), run.tags, [box for box in run.boxes if box.closed], fonts)


def report_lines(result, verbose=False):
    """The report: each problem, with `verbose` each pair, then the summary."""
    lines = list(result.problems)
    if verbose:
        for box in result.pairs:
            count = len(box.content)
            lines.append(
                f"pair: {rule_key(box.kind, box.variant)} | {box.heading}"
                f' | "{box.start[:FIRST_WORDS]}" | {count} paragraph{"" if count == 1 else "s"}'
            )
    kinds = Counter(box.kind for box in result.pairs)
    shown_kinds = ", ".join(f"{kind} {count}" for kind, count in sorted(kinds.items()))
    fonts = sorted(result.fonts.items(), key=lambda item: (-item[1], str(item[0])))
    shown_fonts = ", ".join(f"{font or '(not set)'} {count}" for font, count in fonts)
    lines.append(
        f"{result.tags} tags in {len(result.pairs)} pairs; kinds: {shown_kinds or 'none'};"
        f" fonts in the body (paragraph counts): {shown_fonts or 'none'};"
        f" {len(result.problems)} problem(s)"
    )
    return lines
