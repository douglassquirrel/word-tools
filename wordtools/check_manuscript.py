"""check-manuscript: a whole-file check of a manuscript before it goes to the publisher."""

import argparse
import os

from wordtools import cli
from wordtools.cli import Refusal, open_manuscript
from wordtools.counts import counts, shown_time
from wordtools.rules import RulesError
from wordtools.settings import load_settings
from wordtools.wholecheck import check


def main(argv=None):
    """Run the command; return its exit code."""
    return cli.run("check-manuscript", _parser(), _run, argv)


def _first_line(path, docx):
    found = counts(docx)
    return (
        f"File {path}  {os.path.getsize(path):,} bytes  SHA-256 {found['sha256']}"
        f"  revision {found['revision']}  modified {shown_time(found['modified'], False)}"
        " London time"
    )


def _run(args):
    if args.expect_notes is not None and args.expect_notes < 0:
        raise Refusal("--expect-notes must not be negative")
    try:
        settings = load_settings(args.settings)
    except RulesError as error:
        raise Refusal(str(error)) from None
    docx = open_manuscript(args.manuscript)
    report = check(docx, settings, args.expect_notes, args.allow_placeholders)
    if not args.quiet:
        print(_first_line(args.manuscript, docx))
    for line in report.lines:
        if not (args.quiet and line.startswith("OK")):
            print(line)
    print(report.result())
    return 1 if report.fails else 0


def _parser():
    parser = argparse.ArgumentParser(
        prog="check-manuscript",
        description="Check a whole manuscript against the rules every manuscript shares and"
        " the settings of a publisher and a book. One line per check, OK, FAIL or NOTE, then"
        " the result. Reads only.",
    )
    parser.add_argument("manuscript", metavar="MANUSCRIPT.docx")
    parser.add_argument(
        "--settings",
        action="append",
        default=[],
        metavar="FILE",
        help="a JSON settings file; may be given more than once, and later files win key by key",
    )
    parser.add_argument(
        "--expect-notes", type=int, metavar="N", help="check that there are N endnotes"
    )
    parser.add_argument(
        "--allow-placeholders",
        action="store_true",
        help="report placeholders, unfilled credit lines and counts marked as placeholders"
        " as NOTEs, not FAILs",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true", help="print only FAIL and NOTE lines and the result"
    )
    return parser
