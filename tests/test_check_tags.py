import json
import os
from pathlib import Path

import pytest

from tests.docxkit import pack_docx
from tests.samples import sample_parts
from wordtools.check_tags import main
from wordtools.rules import load_rules

pytestmark = pytest.mark.tier2


def p(text):
    return f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"


GOOD = [p("[begin sidebar]"), p("Words."), p("[end sidebar]")]
RULES = {"open": "begin", "close": "end", "allowed": ["[begin sidebar]", "[end sidebar]"]}


class Book:
    def __init__(self, folder):
        self.folder = folder
        self.docx = folder / "Book.docx"
        self.rules = folder / "rules.json"
        pack_docx(self.docx, sample_parts(GOOD))
        self.rules.write_text(json.dumps(RULES), encoding="utf-8")

    def check(self, *flags):
        return main([str(self.docx), "--rules", str(self.rules), *flags])


@pytest.fixture
def book(tmp_path):
    return Book(tmp_path)


def test_no_problems_prints_the_summary_and_exits_0(book, capsys):
    assert book.check() == 0
    out, err = capsys.readouterr()
    assert out.splitlines() == [
        "2 tags in 1 pairs; kinds: sidebar 1; fonts in the body (paragraph counts): (not set) 3; 0 problem(s)"
    ]
    assert err == ""


def test_any_problem_exits_1(book, capsys):
    pack_docx(book.docx, sample_parts([p("[end sidebar]")]))
    assert book.check() == 1
    assert capsys.readouterr().out.splitlines()[0] == '(start) ("[end sidebar]"): "[end sidebar]" closes nothing'


def test_verbose_flag_lists_the_pairs(book, capsys):
    assert book.check("-v") == 0
    assert capsys.readouterr().out.splitlines()[0] == 'pair: sidebar | (start) | "Words." | 1 paragraph'


def test_reads_the_style_chain_of_the_document(book, capsys):
    rules = {**RULES, "default_font": "Fallback", "tag_font": "Sample Face"}
    book.rules.write_text(json.dumps(rules), encoding="utf-8")
    parts = sample_parts(GOOD)
    parts["word/styles.xml"] = parts["word/styles.xml"].replace(
        '<w:name w:val="Normal"/>', '<w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Sample Face"/></w:rPr>'
    )
    pack_docx(book.docx, parts)
    assert book.check() == 0


def test_a_manuscript_with_no_styles_part_can_still_be_checked(book):
    parts = sample_parts(GOOD)
    del parts["word/styles.xml"]
    pack_docx(book.docx, parts)
    assert book.check() == 0


@pytest.mark.parametrize(
    "content, said",
    [
        ("{not json", "not valid JSON"),
        (json.dumps({"open": "begin", "close": "end"}), '"allowed" is missing'),
        (json.dumps({**RULES, "kinds": {"sidebar": {"fnt": "x"}}}), 'kind "sidebar": unknown key "fnt"'),
    ],
)
def test_a_bad_rules_file_exits_2_with_the_reason_and_the_manuscript_unchanged(book, capsys, content, said):
    book.rules.write_text(content, encoding="utf-8")
    before = book.docx.read_bytes()
    assert book.check() == 2
    out, err = capsys.readouterr()
    assert out == ""
    assert err.startswith(f"check-tags: {book.rules}: ")
    assert said in err
    assert book.docx.read_bytes() == before


def test_a_missing_manuscript_exits_2(book, capsys):
    book.docx.unlink()
    assert book.check() == 2
    assert capsys.readouterr().err == f"check-tags: {book.docx}: no such file\n"


def test_a_file_that_is_not_a_docx_exits_2(book, capsys):
    book.docx.write_bytes(b"not a zip")
    assert book.check() == 2
    assert capsys.readouterr().err == f"check-tags: {book.docx}: not a .docx file (it is not a zip archive)\n"


def test_a_manuscript_it_may_not_read_exits_2(book, capsys):
    book.docx.unlink()
    book.docx.mkdir()
    assert book.check() == 2
    assert capsys.readouterr().err == f"check-tags: {book.docx}: cannot be read: Is a directory\n"


@pytest.mark.parametrize("part", ["word/document.xml", "word/styles.xml"])
def test_a_damaged_part_exits_2_and_names_it(book, capsys, part):
    parts = sample_parts(GOOD)
    parts[part] = "<w:broken></w:mismatched>"
    pack_docx(book.docx, parts)
    assert book.check() == 2
    assert capsys.readouterr().err == f"check-tags: {book.docx}: {part} is not well-formed XML\n"


def test_rules_are_required(book, capsys):
    assert main([str(book.docx)]) == 2
    assert "--rules" in capsys.readouterr().err


def test_help_exits_0_and_names_the_flags(capsys):
    assert main(["--help"]) == 0
    out = capsys.readouterr().out
    assert "--rules RULES.json" in out and "-v" in out


def test_writes_nothing_and_leaves_the_manuscript_as_it_was(book):
    before = sorted(os.listdir(book.folder))
    docx, rules = book.docx.read_bytes(), book.rules.read_bytes()
    book.check()
    assert sorted(os.listdir(book.folder)) == before
    assert (book.docx.read_bytes(), book.rules.read_bytes()) == (docx, rules)


@pytest.mark.parametrize("name", ['with "quotes"', "back\\slash", "new\nline", "$HOME", "</script>", "Bücher é"])
def test_names_with_awkward_characters_are_only_ever_data(tmp_path, capsys, name):
    folder = tmp_path / name
    folder.mkdir(parents=True)  # the / of </script> makes two folders
    book = Book(folder)
    assert book.check() == 0


def test_tag_text_with_awkward_characters_is_only_ever_data(book, capsys):
    awkward = '[begin &quot;x&quot; $HOME \\ &lt;/script&gt;]'
    pack_docx(book.docx, sample_parts([p(awkward)]))
    assert book.check() == 1
    assert '[begin "x" $HOME \\ </script>]' in capsys.readouterr().out


KIT = Path(__file__).resolve().parent.parent
EXAMPLE = KIT / "tests" / "fixtures" / "rules.example.json"


def test_the_example_rules_file_is_accepted():
    assert load_rules(str(EXAMPLE))["open"] == "begin"


def test_the_readme_shows_the_example_rules_file_exactly():
    readme = (KIT / "README.md").read_text(encoding="utf-8")
    assert f"```json\n{EXAMPLE.read_text(encoding='utf-8')}```" in readme
