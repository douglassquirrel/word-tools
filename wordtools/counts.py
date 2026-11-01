"""The structure and counts of a save: what a glance at two saves should compare first."""

import hashlib
import re
from datetime import datetime, timezone

from wordtools.clock import london
from wordtools.content import (
    HEADINGS,
    heading_counts,
    highlight_colours,
    paragraph_texts,
    placeholder_count,
    tag_counts,
)
from wordtools.manuscript import BODY, ENDNOTES, FOOTNOTES

PLACEHOLDER = "TKTKTK"
TAG_OPEN, TAG_CLOSE = "begin", "end"
TEXT = re.compile(r"<w:t(?: [^>]*)?>([^<]*)</w:t>")
STRAIGHT = ('"', "'", "&quot;", "&apos;")
MEDIA = "word/media/"


def counts(docx):
    """The counts of one save, a Docx, by name."""
    parts = {info.filename: data for info, data in docx.entries}

    def read(name):
        return parts.get(name, b"").decode("utf-8", "replace")

    core = read("docProps/core.xml")
    document = read("word/document.xml")
    endnotes, footnotes = read("word/endnotes.xml"), read("word/footnotes.xml")
    notes = document + endnotes + footnotes
    body = document.split("<w:body>")[1] if "<w:body>" in document else document
    with open(docx.path, "rb") as file:
        sha = hashlib.sha256(file.read()).hexdigest()[:16]
    text = "".join(TEXT.findall(notes))
    several = []
    for kind, xml in (("endnote", endnotes), ("footnote", footnotes)):
        for id, inside in _notes(kind, xml):
            if len(re.findall(r"<w:p[ >]", inside)) > 1:
                several.append(f"{kind} {id}")
    return {
        "sha256": sha,
        "revision": "".join(re.findall(r"<cp:revision>(.*?)<", core)[:1]),
        "modified": "".join(re.findall(r"<dcterms:modified[^>]*>(.*?)<", core)[:1]),
        "paragraphs": len(re.findall(r"<w:p[ >]", body)),
        "tracked changes": sum(
            len(re.findall(rf"<w:{name}[ >]", notes))
            for name in ("ins", "del", "moveFrom", "moveTo")
        ),
        "trackRevisions": "<w:trackRevisions" in read("word/settings.xml"),
        "comments": document.count("<w:commentReference"),
        "endnote markers": document.count("<w:endnoteReference"),
        "endnotes": len(_notes("endnote", endnotes)),
        "footnote markers": document.count("<w:footnoteReference"),
        "footnotes": len(_notes("footnote", footnotes)),
        "straight quotes": sum(text.count(mark) for mark in STRAIGHT),
        "links in notes": (endnotes + footnotes).count("<w:hyperlink"),
        "highlighted runs": notes.count("<w:highlight "),
        "notes of more than one paragraph": several,
    }


def _notes(kind, xml):
    """(id, content) of each real note of a notes part: not the separators."""
    found = re.findall(rf'<w:{kind} w:id="(\d+)">(.*?)</w:{kind}>', xml, re.S)
    return [(id, inside) for id, inside in found if int(id) > 0]


def structure_lines(old, new, utc=False, placeholders=(PLACEHOLDER,), tags=(TAG_OPEN, TAG_CLOSE)):
    """The 'Structure and counts' section for two saves. `placeholders` are the texts to
    count; `tags` the opening and closing words of bracketed tags, or None for no tag line."""
    before, after = counts(old), counts(new)
    was_read, now_read = _read(old), _read(new)
    lines = ["== Structure and counts (old | new)"]
    for name in ("sha256", "revision"):
        lines.append(f"{name}: {before[name]} | {after[name]}")
    zone = "UTC" if utc else "London time"
    times = shown_time(before["modified"], utc), shown_time(after["modified"], utc)
    lines.append(f"modified ({zone}): {times[0]} | {times[1]}")
    lines.extend(_parts(old, new))
    for name in list(before)[3:]:
        was, now = before[name], after[name]
        if name == "highlighted runs":
            change = f" ({now - was:+d})" if now != was else ""
            shown = _coloured(was, was_read), _coloured(now, now_read)
            lines.append(f"{name}: {shown[0]} | {shown[1]}{change}")
        elif isinstance(was, bool):
            lines.append(f"{name}: {'on' if was else 'off'} | {'on' if now else 'off'}")
        elif isinstance(was, list):
            lines.append(f"{name}: {', '.join(was) or 'none'} | {', '.join(now) or 'none'}")
        else:
            change = f" ({now - was:+d})" if now != was else ""
            lines.append(f"{name}: {was} | {now}{change}")
    for placeholder in placeholders:
        label = "placeholders" if len(placeholders) == 1 else f"placeholders {placeholder}"
        was = placeholder_count(was_read["texts"], placeholder)
        now = placeholder_count(now_read["texts"], placeholder)
        change = f" ({now - was:+d})" if now != was else ""
        lines.append(f"{label}: {was} | {now}{change}")
    lines.append(_headings(was_read, now_read))
    if tags:
        lines.append(_tags(was_read, now_read, *tags))
    return lines


def _read(docx):
    """What the lines beyond the plain counts need from one save."""
    parts = docx.texts()
    xml = [parts[name] for name in (BODY, ENDNOTES, FOOTNOTES) if name in parts]
    return {
        "body": parts[BODY],
        "xml": "".join(xml),
        "texts": [text for part in xml for text in paragraph_texts(part)],
    }


def _coloured(total, read):
    """A count of highlighted runs, followed by their colours if there are any."""
    if not total:
        return "0"
    colours = ", ".join(f"{colour} {count}" for colour, count in highlight_colours(read["xml"]))
    return f"{total} ({colours})"


def _headings(was_read, now_read):
    """The headings line. A style in either save is shown on both sides."""
    was, now = heading_counts(was_read["body"]), heading_counts(now_read["body"])
    names = [name for name in {**was, **now}]
    names.sort(key=HEADINGS.index)
    if not names:
        return "headings: none | none"
    old_side = ", ".join(f"{name} {was.get(name, 0)}" for name in names)
    new_side = ", ".join(f"{name} {now.get(name, 0)}" for name in names)
    return f"headings: {old_side} | {new_side}"


def _tags(was_read, now_read, opening, closing):
    """The tags line. A kind in either save is shown on both sides; a kind whose counts
    differ in the new save is marked there."""
    was = tag_counts(was_read["texts"], opening, closing)
    now = tag_counts(now_read["texts"], opening, closing)
    kinds = sorted({*was, *now})
    if not kinds:
        return "tags: none | none"

    def side(found, marking):
        shown = []
        for kind in kinds:
            opens, closes = found.get(kind, (0, 0))
            mark = " UNBALANCED" if marking and opens != closes else ""
            shown.append(f"{kind} {opening} {opens} {closing} {closes}{mark}")
        return ", ".join(shown)

    return f"tags: {side(was, False)} | {side(now, True)}"


def shown_time(stamp, utc):
    """A time from core.xml (UTC) as it is to be shown."""
    try:
        moment = datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return stamp
    return (moment if utc else london(moment)).strftime("%Y-%m-%d %H:%M")


def _parts(old, new):
    """Which entries differ between two saves, and what became of the pictures."""
    was = {info.filename: data for info, data in old.entries}
    now = {info.filename: data for info, data in new.entries}
    differ = []
    for name in list(now) + [name for name in was if name not in now]:
        if name.startswith(MEDIA) and (name not in was or name not in now):
            continue  # a picture added or removed is told on the media line
        if name not in was:
            differ.append(f"{name} (new only)")
        elif name not in now:
            differ.append(f"{name} (old only)")
        elif was[name] != now[name]:
            differ.append(name)
    old_media = sorted(name[len(MEDIA) :] for name in was if name.startswith(MEDIA))
    new_media = sorted(name[len(MEDIA) :] for name in now if name.startswith(MEDIA))
    if old_media == new_media:
        count = len(old_media)
        media = f"the same {count} file{'' if count == 1 else 's'}" if count else "none"
    else:
        removed = [name for name in old_media if name not in new_media]
        added = [name for name in new_media if name not in old_media]
        media = "; ".join(
            f"{word} {', '.join(names)}"
            for word, names in (("removed", removed), ("added", added))
            if names
        )
    return [f"parts that differ: {', '.join(differ) or 'none'}", f"media: {media}"]
