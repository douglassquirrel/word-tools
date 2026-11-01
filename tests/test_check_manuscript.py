import hashlib
import json
import os
from pathlib import Path

import pytest

from tests.docxkit import pack_docx
from tests.samples import ready_parts
from wordtools.check_manuscript import main

pytestmark = pytest.mark.tier2

KIT = Path(__file__).resolve().parent.parent
FIXTURES = KIT / "tests" / "fixtures"
PUBLISHER = FIXTURES / "publisher.example.json"
BOOK = FIXTURES / "book.example.json"


class Book:
    def __init__(self, folder):
        self.folder = folder
        self.docx = folder / "Book.docx"
        pack_docx(self.docx, ready_parts())

    def settings(self, content, name="settings.json"):
        path = self.folder / name
        path.write_text(content if isinstance(content, str) else json.dumps(content), encoding="utf-8")
        return str(path)

    def check(self, *flags):
        return main([str(self.docx), *flags])

    def change(self, old, new):
        parts = ready_parts()
        assert old in parts["word/document.xml"]
        parts["word/document.xml"] = parts["word/document.xml"].replace(old, new)
        pack_docx(self.docx, parts)


@pytest.fixture
def book(tmp_path):
    return Book(tmp_path)


def test_an_invented_manuscript_passes_with_sample_publisher_and_book_settings(book, capsys):
    assert book.check("--settings", str(PUBLISHER), "--settings", str(BOOK)) == 0
    out, err = capsys.readouterr()
    assert out.splitlines()[-1] == "RESULT: PASS"
    assert not [line for line in out.splitlines() if line.startswith("FAIL")]
    assert err == ""


def test_the_first_line_gives_file_size_hash_revision_and_time(book, capsys):
    assert book.check() == 0
    size = book.docx.stat().st_size
    sha = hashlib.sha256(book.docx.read_bytes()).hexdigest()[:16]
    assert capsys.readouterr().out.splitlines()[0] == (
        f"File {book.docx}  {size:,} bytes  SHA-256 {sha}  revision 3  modified 2026-10-01 10:00 London time"
    )


def test_a_failure_exits_1_and_the_result_lists_it(book, capsys):
    book.change("Dedication", "It&apos;s for you")
    assert book.check() == 1
    assert capsys.readouterr().out.splitlines()[-1] == (
        "RESULT: 1 FAIL(S): no straight quotes or apostrophes (found 1)"
    )


def test_quiet_prints_only_fail_and_note_lines_and_the_result(book, capsys):
    book.change("Dedication", "TKTKTK")
    assert book.check("-q") == 1
    lines = capsys.readouterr().out.splitlines()
    assert {line[:4] for line in lines[:-1]} == {"FAIL", "NOTE"}
    assert lines[-1] == "RESULT: 1 FAIL(S): no placeholder TKTKTK (found 1)"


def test_allow_placeholders_passes_a_known_placeholder(book, capsys):
    book.change("Dedication", "TKTKTK")
    assert book.check("--allow-placeholders") == 0
    out = capsys.readouterr().out
    assert "NOTE no placeholder TKTKTK (found 1)" in out
    assert out.splitlines()[-1] == "RESULT: PASS"


def test_expect_notes_adds_the_check(book, capsys):
    assert book.check("--expect-notes", "2") == 0
    assert "OK   endnote count is 2" in capsys.readouterr().out
    assert book.check("--expect-notes", "9") == 1


def test_a_second_settings_file_changes_one_key_and_keeps_the_first_file_s_others(book, capsys):
    first = book.settings({"max_embedded_images": 0, "title": "The Lighthouse Ledger"}, "first.json")
    second = book.settings({"max_embedded_images": 5}, "second.json")
    assert book.check("--settings", first, "--settings", second) == 0
    out = capsys.readouterr().out
    assert "OK   embedded images: 1, at most 5" in out
    assert 'OK   title "The Lighthouse Ledger" in the first 3,000 characters' in out


@pytest.mark.parametrize(
    "content, said",
    [
        ("{not json", "not valid JSON"),
        ({"notez": 1}, 'unknown key "notez"'),
        ({"counts": [{"name": "maps", "pattern": "(", "expect": 1}]}, 'counts "maps": "pattern" is a bad regular expression'),
    ],
)
def test_a_bad_settings_file_exits_2_naming_it_and_prints_no_report(book, capsys, content, said):
    path = book.settings(content)
    assert book.check("--settings", path) == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith(f"check-manuscript: {path}: ")
    assert said in err


def test_a_setting_that_needs_another_exits_2(book, capsys):
    path = book.settings({"list_of_figures": {"from": "a", "to": "b"}})
    assert book.check("--settings", path) == 2
    assert capsys.readouterr().err == (
        'check-manuscript: the settings give "list_of_figures" but not "figures", which it needs\n'
    )


def test_a_missing_manuscript_exits_2(book, capsys):
    book.docx.unlink()
    assert book.check() == 2
    assert capsys.readouterr().err == f"check-manuscript: {book.docx}: no such file\n"


def test_a_file_that_is_not_a_docx_exits_2(book, capsys):
    book.docx.write_bytes(b"not a zip")
    assert book.check() == 2
    assert "not a .docx file" in capsys.readouterr().err


def test_a_damaged_part_exits_2(book, capsys):
    parts = ready_parts()
    parts["word/endnotes.xml"] = "<w:broken></w:mismatched>"
    pack_docx(book.docx, parts)
    assert book.check() == 2
    assert capsys.readouterr().err == f"check-manuscript: {book.docx}: word/endnotes.xml is not well-formed XML\n"


@pytest.mark.parametrize("flags", [["--expect-notes", "x"], ["--expect-notes", "-1"], ["--nonsense"]])
def test_bad_arguments_exit_2(book, capsys, flags):
    assert book.check(*flags) == 2
    assert capsys.readouterr().out == ""


def test_help_exits_0_and_names_the_flags(capsys):
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    for flag in ("--settings", "--expect-notes", "--allow-placeholders", "-q"):
        assert flag in out


def test_writes_nothing_and_leaves_the_manuscript_as_it_was(book):
    settings = book.settings({"title": "x"})
    before = sorted(os.listdir(book.folder))
    bytes_before = book.docx.read_bytes()
    book.check("--settings", settings)
    assert sorted(os.listdir(book.folder)) == before
    assert book.docx.read_bytes() == bytes_before


@pytest.mark.parametrize("name", ['with "quotes"', "back\\slash", "new\nline", "$HOME", "</script>", "Bücher é"])
def test_names_with_awkward_characters_are_only_ever_data(tmp_path, name):
    folder = tmp_path / name
    folder.mkdir(parents=True)  # the / of </script> makes two folders
    assert Book(folder).check() == 0


def test_text_from_settings_with_awkward_characters_is_only_ever_data(book, capsys):
    title = '"$HOME" \\ </script>\n é'
    assert book.check("--settings", book.settings({"title": title})) == 1
    assert f'title "{title}" in the first' in capsys.readouterr().out


def readme():
    return (KIT / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("path", [PUBLISHER, BOOK])
def test_the_readme_shows_each_sample_settings_file_exactly(path):
    assert f"```json\n{path.read_text(encoding='utf-8')}```" in readme()
