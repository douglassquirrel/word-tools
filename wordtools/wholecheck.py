"""The checks of check-manuscript: the whole file, against the rules every manuscript shares
and the settings of a publisher and a book."""

import re
from collections import namedtuple

from wordtools.content import (
    heading_counts,
    highlight_colours,
    placeholder_count,
    reading_texts,
    tag_counts,
    tag_kind,
)
from wordtools.counts import MEDIA, PLACEHOLDER, counts
from wordtools.manuscript import BODY, ENDNOTES, FOOTNOTES
from wordtools.text import nfc

ODD_CHARACTERS = (
    ("​", "zero-width space"),
    ("­", "soft hyphen"),
    ("‌", "zero-width non-joiner"),
    ("﻿", "byte-order mark"),
)
HEADER_OR_FOOTER = re.compile(r"word/(header|footer)\d*\.xml$")
FIELD = re.compile(r"<w:instrText\b[^>]*>\s*(\S+)|<w:fldSimple\b[^>]*\bw:instr=\"\s*(\S+)")
WATERMARK = re.compile(r'="[^"]*WaterMark')  # in a value, so never in the words of the text
NOTE_ENTRY = "<w:{kind}\\b([^>]*)>"
ATTRIBUTE_ID = re.compile(r'\bw:id="(-?\d+)"')
EXPECTED_SPACING = 480
SECTION = re.compile(r"<w:sectPr\b[^>]*?/>|<w:sectPr\b.*?</w:sectPr>", re.S)
PAGE_SIZES = {"letter": (12240, 15840), "a4": (11906, 16838)}
TWIPS_IN_AN_INCH = 1440
TOLERANCE = 10  # twips: 8.27 inches is near enough to A4's 11906
TITLE_WITHIN = 3000
ENTRY = "Figure {number} {caption}"
TRAILING_NUMBER = re.compile(r"\d+$")
Figure = namedtuple("Figure", "number caption credit")


class Report:
    """The lines of a run so far, and what failed."""

    def __init__(self):
        self.lines = []
        self.fails = []

    def check(self, passed, message, soft=False):
        """OK if `passed`; otherwise FAIL, or NOTE if `soft`."""
        if passed:
            self.lines.append(f"OK   {message}")
        elif soft:
            self.note(message)
        else:
            self.lines.append(f"FAIL {message}")
            self.fails.append(message)

    def note(self, message):
        self.lines.append(f"NOTE {message}")

    def result(self):
        if not self.fails:
            return "RESULT: PASS"
        return f"RESULT: {len(self.fails)} FAIL(S): {'; '.join(self.fails)}"


class Save:
    """One manuscript, as the checks need it."""

    def __init__(self, docx):
        self.parts = docx.texts()
        self.names = [info.filename for info, _ in docx.entries]
        self.counts = counts(docx)
        self.xml = self.parts[BODY]
        self.endnotes = self.parts.get(ENDNOTES, "")
        self.footnotes = self.parts.get(FOOTNOTES, "")
        self.all_xml = self.xml + self.endnotes + self.footnotes
        self.body = reading_texts(self.xml)
        self.notes = []
        for part in (self.endnotes, self.footnotes):
            if part:
                self.notes += reading_texts(part)
        self.texts = self.body + self.notes
        self.body_text = "\n".join(self.body)
        self.headers = {
            name: xml for name, xml in self.parts.items() if HEADER_OR_FOOTER.match(name)
        }

    def note_ids(self, kind, xml):
        """The ids of the real notes of a part: not the separators, whatever their ids."""
        ids = []
        for attributes in re.findall(NOTE_ENTRY.format(kind=kind), xml):
            found = ATTRIBUTE_ID.search(attributes)
            if found and "w:type=" not in attributes:
                ids.append(found.group(1))
        return ids

    def markers(self, kind):
        return re.findall(rf'<w:{kind}Reference\b[^>]*\bw:id="(-?\d+)"', self.xml)


def _always_on(save, report, placeholders, expect_notes, allow_placeholders):
    found = save.counts
    tracked = found["tracked changes"]
    report.check(not tracked, f"no tracked changes (found {tracked})")
    report.check(not found["trackRevisions"], "Track Changes switched off")
    has_part = "word/comments.xml" in save.names
    report.check(
        not has_part and not found["comments"],
        f"no comments (comments part: {'yes' if has_part else 'no'};"
        f" references: {found['comments']})",
    )
    _notes(save, report, "endnote", save.endnotes)
    _notes(save, report, "footnote", save.footnotes)
    if expect_notes is not None:
        count = found["endnotes"]
        detail = "" if count == expect_notes else f" (found {count})"
        report.check(count == expect_notes, f"endnote count is {expect_notes}{detail}")
    straight = sum(text.count('"') + text.count("'") for text in save.texts)
    report.check(not straight, f"no straight quotes or apostrophes (found {straight})")
    for character, name in ODD_CHARACTERS:
        count = sum(text.count(character) for text in save.texts)
        if name == "soft hyphen":
            count += save.all_xml.count("<w:softHyphen")
        report.check(not count, f"no {name} (found {count})")
    for placeholder in placeholders:
        count = placeholder_count(save.texts, placeholder)
        message = f"no placeholder {placeholder} (found {count})"
        report.check(not count, message, soft=allow_placeholders)
    fields = [
        simple or complicated
        for xml in save.headers.values()
        for complicated, simple in FIELD.findall(xml)
    ]
    shown = ", ".join(fields) or "none"
    report.check(not fields, f"no fields in headers or footers (found {shown})")
    marks = sum(len(WATERMARK.findall(xml)) for xml in (save.xml, *save.headers.values()))
    report.check(not marks, f"no watermark (found {marks})")


def _notes(save, report, kind, xml):
    ids, markers = save.note_ids(kind, xml), save.markers(kind)
    problems = []
    missing = [id for id in ids if id not in markers]
    strays = [id for id in markers if id not in ids]
    repeated = sorted({id for id in markers if markers.count(id) > 1})
    for word, found in (("no marker", missing), ("no note", strays), ("repeated", repeated)):
        if found:
            problems.append(f"{word}: {', '.join(found)}")
    detail = f" ({'; '.join(problems)})" if problems else ""
    report.check(
        not problems, f"{kind}s {len(ids)}, markers {len(markers)}, one marker each{detail}"
    )


def _notes_for_the_reader(save, report, settings):
    fonts = sorted(set(re.findall(r'w:ascii="([^"]+)"', save.all_xml)))
    report.note(f"fonts used in runs: {', '.join(fonts) or 'none set directly'}")
    colours = highlight_colours(save.all_xml)
    shown = ", ".join(f"{colour} {count}" for colour, count in colours)
    total = sum(count for _, count in colours)
    report.note(f"highlighted runs: {total} ({shown})" if total else "highlighted runs: 0")
    expected = settings.get("line_spacing", EXPECTED_SPACING)
    spacings = re.findall(r'<w:spacing\b[^>]*\bw:line="(\d+)"', save.all_xml)
    others = [value for value in spacings if int(value) != expected]
    message = f"explicit line spacing other than {expected}: {len(others)}"
    if others:
        values = ", ".join(sorted(set(others), key=int))
        message += f" (values {values}); check-spacing is the full check"
    report.note(message)
    several = len(save.counts["notes of more than one paragraph"])
    message = f"notes of more than one paragraph: {several}"
    if "multi_paragraph_notes" in settings:
        wanted = settings["multi_paragraph_notes"]
        report.check(several == wanted, f"{message} (expected {wanted})", soft=True)
    else:
        report.note(message)
    headings = ", ".join(f"{name} {n}" for name, n in heading_counts(save.xml).items())
    report.note(f"paragraphs by heading style: {headings or 'none'}")


def _links(save, report):
    links = save.counts["links in notes"]
    report.check(not links, f"no live hyperlinks in the notes (found {links})")


def _sections(save):
    return SECTION.findall(save.xml)


def _number(tag, name):
    """A whole number from the attribute `name` of the XML tag `tag`, or None."""
    found = re.search(rf'\bw:{name}="(-?\d+)"', tag)
    return int(found.group(1)) if found else None


def _margins(save, report, inches):
    sections = _sections(save)
    faults = [] if sections else ["no sections found"]
    for number, section in enumerate(sections, 1):
        tag = re.search(r"<w:pgMar\b[^>]*>", section)
        if not tag:
            faults.append(f"section {number} sets none")
            continue
        for side in ("top", "bottom", "left", "right"):
            value = abs(_number(tag.group(0), side) or 0)
            if abs(value - inches * TWIPS_IN_AN_INCH) > TOLERANCE:
                faults.append(f"section {number} {side} {value / TWIPS_IN_AN_INCH:g}")
    message = f"margins {inches:g} inch in every section ({len(sections)} sections)"
    report.check(not faults, f"{message}: {', '.join(faults)}" if faults else message)


def _page_size(save, report, size):
    if isinstance(size, str):
        wanted, label = PAGE_SIZES[size], size
    else:
        wanted = tuple(side * TWIPS_IN_AN_INCH for side in size)
        label = f"{size[0]:g} by {size[1]:g}"
    sections = _sections(save)
    faults = []
    for number, section in enumerate(sections, 1):
        tag = re.search(r"<w:pgSz\b[^>]*>", section)
        if not tag:
            faults.append(f"section {number} sets none")
            continue
        width, height = _number(tag.group(0), "w") or 0, _number(tag.group(0), "h") or 0
        if abs(width - wanted[0]) > TOLERANCE or abs(height - wanted[1]) > TOLERANCE:
            shown = f"{width / TWIPS_IN_AN_INCH:.2f} by {height / TWIPS_IN_AN_INCH:.2f}"
            faults.append(f"section {number} is {shown}")
    message = f"page size {label} in every section ({len(sections)} sections)"
    report.check(not faults, f"{message}: {', '.join(faults)}" if faults else message)


def _headers_empty(save, report, setting):
    filled = [
        name for name, xml in save.headers.items() if "".join(reading_texts(xml)).strip()
    ]
    detail = f" (text in {', '.join(filled)})" if filled else ""
    report.check(not filled, f"headers and footers empty{detail}", soft=setting == "note")


def _images(save, report, most):
    media = [name[len(MEDIA) :] for name in save.names if name.startswith(MEDIA)]
    message = f"embedded images: {len(media)}, at most {most}"
    detail = f" ({', '.join(media)})" if len(media) > most else ""
    report.check(not detail, message + detail, soft=True)


def _word_count(save, report, wanted):
    body = sum(len(text.split()) for text in save.body)
    notes = sum(len(text.split()) for text in save.notes)
    total = body + notes
    report.check(
        wanted[0] <= total <= wanted[1],
        f"word count {total:,} (body {body:,}, notes {notes:,}),"
        f" wanted {wanted[0]:,} to {wanted[1]:,}",
    )


def _title(save, report, title):
    report.check(
        nfc(title) in nfc(save.body_text)[:TITLE_WITHIN],
        f'title "{title}" in the first {TITLE_WITHIN:,} characters',
    )


def _old_titles(save, report, titles):
    for title in titles:
        report.check(
            not any(nfc(title) in nfc(text) for text in save.texts), f'no old title "{title}"'
        )


def _tag_pairs(save, report, pairs):
    found = tag_counts(save.texts, pairs["open"], pairs["close"])
    required = [tag_kind(kind) for kind in pairs.get("required", [])]
    listed = [tag_kind(kind) for kind in pairs["kinds"]]
    for kind in listed + [kind for kind in required if kind not in listed]:
        opens, closes = found.get(kind, (0, 0))
        absent = kind in required and not opens + closes
        report.check(
            opens == closes and not absent,
            f"tags balanced: {kind} {opens}/{closes}{' (required)' if absent else ''}",
        )


def _counts(save, report, entries, allow_placeholders):
    for entry in entries:
        found = len(re.findall(entry["pattern"], save.body_text))
        wants, passed = [], True
        if "expect" in entry:
            wants.append(f"expected {entry['expect']}")
            passed = found == entry["expect"]
        if "min" in entry:
            wants.append(f"at least {entry['min']}")
            passed = passed and found >= entry["min"]
        if "max" in entry:
            wants.append(f"at most {entry['max']}")
            passed = passed and found <= entry["max"]
        report.check(
            passed,
            f"{entry['name']}: {found} ({', '.join(wants)})",
            soft=allow_placeholders and entry.get("placeholder", False),
        )


def _first(match):
    """What a pattern picked out: its first group, or all it matched if it has none."""
    return (match.group(1) or "") if match.re.groups else match.group(0)


def _figures(save, setting):
    """(the complete figures as Figures, the numbers of the callouts left incomplete)."""
    callout, caption, credit = (
        re.compile(setting[name]) for name in ("callout", "caption", "credit")
    )
    lines = [line.strip() for text in save.body for line in text.split("\n") if line.strip()]
    figures, incomplete = [], []
    for index, line in enumerate(lines):
        called = callout.search(line)
        if not called:
            continue
        captioned = caption.search(lines[index + 1]) if index + 1 < len(lines) else None
        credited = credit.search(lines[index + 2]) if index + 2 < len(lines) else None
        if captioned and credited:
            figures.append(Figure(_first(called), _first(captioned), _first(credited)))
        else:
            incomplete.append(_first(called))
    return figures, incomplete


def _check_figures(figures, incomplete, report, setting, placeholders, allow_placeholders):
    message = f"figures: {len(figures)}, each a callout, caption and credit line"
    if "expect" in setting:
        message += f" (expected {setting['expect']})"
    passed = not incomplete and setting.get("expect", len(figures)) == len(figures)
    if incomplete:
        message += f": incomplete {', '.join(incomplete)}"
    report.check(passed, message)
    unfilled = [
        figure.number
        for figure in figures
        if not figure.credit.strip() or any(text in figure.credit for text in placeholders)
    ]
    detail = f" (not filled: {', '.join(unfilled)})" if unfilled else ""
    report.check(
        not unfilled, f"every figure credit line filled{detail}", soft=allow_placeholders
    )
    if setting.get("caption_no_full_stop"):
        stopped = [f.number for f in figures if f.caption.rstrip().endswith(".")]
        detail = f" (ending so: {', '.join(stopped)})" if stopped else ""
        report.check(not stopped, f"no figure caption ends with a full stop{detail}")


def _tables(save, report, tables):
    named = [
        table
        for table in tables
        if re.search(rf"\bTable {re.escape(table)}(?![\d.]*\d)", save.body_text)
    ]
    missing = [table for table in tables if table not in named]
    detail = f" (missing: {', '.join(missing)})" if missing else ""
    report.check(not missing, f"tables named: {', '.join(named)}{detail}")


def _list_of_figures(save, report, setting, figures):
    start, end = setting["from"], setting["to"]
    lines = [text.strip() for text in save.body]
    try:
        first = lines.index(start)
        last = lines.index(end, first + 1)
    except ValueError:
        report.check(False, f'"{start}" to "{end}" found in the body')
        return
    listed = "\n".join(lines[first + 1 : last])
    template = setting.get("entry", ENTRY)
    missing = []
    for figure in figures:
        caption = TRAILING_NUMBER.sub("", figure.caption).strip()
        entry = template.replace("{number}", figure.number).replace("{caption}", caption)
        if entry not in listed:
            missing.append(entry)
    detail = f" (missing: {', '.join(missing)})" if missing else ""
    report.check(not missing, f'"{start}" names every figure{detail}')


def _from_settings(save, report, settings, placeholders, allow_placeholders):
    """The checks each setting switches on, in the order the README lists them."""
    if settings.get("no_links_in_notes"):
        _links(save, report)
    if "margins_inches" in settings:
        _margins(save, report, settings["margins_inches"])
    if "page_size" in settings:
        _page_size(save, report, settings["page_size"])
    if settings.get("headers_footers_empty"):
        _headers_empty(save, report, settings["headers_footers_empty"])
    if "max_embedded_images" in settings:
        _images(save, report, settings["max_embedded_images"])
    if "word_count" in settings:
        _word_count(save, report, settings["word_count"])
    if "title" in settings:
        _title(save, report, settings["title"])
    _old_titles(save, report, settings.get("old_titles", []))
    if "tag_pairs" in settings:
        _tag_pairs(save, report, settings["tag_pairs"])
    _counts(save, report, settings.get("counts", []), allow_placeholders)
    if "figures" in settings:
        setting = settings["figures"]
        figures, incomplete = _figures(save, setting)
        _check_figures(figures, incomplete, report, setting, placeholders, allow_placeholders)
        if "list_of_figures" in settings:
            _list_of_figures(save, report, settings["list_of_figures"], figures)
    if "tables" in settings:
        _tables(save, report, settings["tables"])


def check(docx, settings, expect_notes=None, allow_placeholders=False):
    """Check the manuscript `docx`; return a Report."""
    save = Save(docx)
    report = Report()
    placeholders = settings.get("placeholders", [PLACEHOLDER])
    if expect_notes is None:
        expect_notes = settings.get("notes")
    _always_on(save, report, placeholders, expect_notes, allow_placeholders)
    _notes_for_the_reader(save, report, settings)
    _from_settings(save, report, settings, placeholders, allow_placeholders)
    return report
