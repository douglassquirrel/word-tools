import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.docxkit import pack_docx
from tests.samples import SAMPLE_EDITS, sample_parts

pytestmark = pytest.mark.tier2

KIT = Path(__file__).resolve().parent.parent
LAUNCHERS = ("propose-edits", "note-map", "compare-saves", "check-spacing", "check-tags")


@pytest.fixture
def kit(tmp_path):
    """A copy of the kit's code in a folder of its own, so that what running it
    leaves behind can be seen."""
    copy = tmp_path / "kit"
    copy.mkdir()
    shutil.copytree(KIT / "wordtools", copy / "wordtools", ignore=shutil.ignore_patterns("__pycache__"))
    for launcher in LAUNCHERS:
        shutil.copy2(KIT / launcher, copy / launcher)
    return copy


def run(kit, command, *args, cwd):
    env = {"PATH": os.environ["PATH"]}
    return subprocess.run(
        [sys.executable, str(kit / command), *args],
        cwd=cwd, env=env, capture_output=True, text=True, timeout=60,
    )


def test_propose_edits_runs_from_another_folder_and_leaves_no_bytecode_anywhere(kit, tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    pack_docx(book / "in.docx", sample_parts())
    (book / "edits.json").write_text(json.dumps(SAMPLE_EDITS), encoding="utf-8")
    done = run(kit, "propose-edits", "edits.json", "--in", "in.docx", "--out", "new.docx", cwd=book)
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout.splitlines()[-1] == "wrote new.docx"
    assert sorted(path.name for path in book.iterdir()) == ["edits.json", "in.docx", "new.docx"]
    assert list(kit.rglob("__pycache__")) == []


@pytest.mark.parametrize("name", LAUNCHERS)
def test_each_launcher_is_executable_and_asks_for_python3_on_the_path(name):
    launcher = KIT / name
    assert os.access(launcher, os.X_OK)
    assert launcher.read_text().splitlines()[0] == "#!/usr/bin/env python3"


def test_help_names_every_flag_in_the_synopsis(kit, tmp_path):
    done = run(kit, "propose-edits", "--help", cwd=tmp_path)
    assert done.returncode == 0
    for flag in (
        "EDITS.json", "--in", "--out", "--author", "--date", "--dry-run", "--force",
        "--keep-on-failure", "--utc", "--tmp", "--timeout",
    ):
        assert flag in done.stdout


def test_note_map_runs_from_another_folder(kit, tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    pack_docx(book / "in.docx", sample_parts())
    done = run(kit, "note-map", "in.docx", "--registry", "../notes.json", "--dry-run", cwd=book)
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout.splitlines()[0] == "dry run: 3 notes: 0 carried, 3 new, 0 retired; nothing written"
    assert [path.name for path in book.iterdir()] == ["in.docx"]
    assert list(kit.rglob("__pycache__")) == []


def test_compare_saves_runs_from_another_folder(kit, tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    pack_docx(book / "old.docx", sample_parts())
    pack_docx(book / "new.docx", sample_parts())
    done = run(kit, "compare-saves", "old.docx", "new.docx", "--no-text-diff", cwd=book)
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout.splitlines()[:3] == [
        "old: old.docx", "new: new.docx", "text diff left out (--no-text-diff)",
    ]
    assert sorted(path.name for path in book.iterdir()) == ["new.docx", "old.docx"]
    assert list(kit.rglob("__pycache__")) == []


def test_check_spacing_runs_from_another_folder(kit, tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    pack_docx(book / "in.docx", sample_parts())
    done = run(kit, "check-spacing", "in.docx", cwd=book)
    assert (done.returncode, done.stderr) == (1, "")
    assert done.stdout.splitlines()[0] == "== TEXT: 9 paragraphs, 8 double, 1 not double"
    assert [path.name for path in book.iterdir()] == ["in.docx"]
    assert list(kit.rglob("__pycache__")) == []


def test_check_tags_runs_from_another_folder_and_leaves_no_bytecode_anywhere(kit, tmp_path):
    book = tmp_path / "book"
    book.mkdir()
    pack_docx(book / "in.docx", sample_parts())
    (book / "rules.json").write_text(
        json.dumps({"open": "begin", "close": "end", "allowed": ["[begin x]"]}), encoding="utf-8"
    )
    done = run(kit, "check-tags", "in.docx", "--rules", "rules.json", cwd=book)
    assert (done.returncode, done.stderr) == (0, "")
    assert done.stdout.startswith("0 tags in 0 pairs;")
    assert sorted(path.name for path in book.iterdir()) == ["in.docx", "rules.json"]
    assert list(kit.rglob("__pycache__")) == []
