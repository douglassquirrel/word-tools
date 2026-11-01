"""check-tags: check a manuscript's bracketed production tags against a rules file."""

import argparse
from xml.etree import ElementTree

from wordtools import cli
from wordtools.cli import Refusal
from wordtools.docx import Docx, DocxError
from wordtools.layout import Styles, blocks
from wordtools.manuscript import BODY, STYLES
from wordtools.rules import RulesError, load_rules
from wordtools.tagcheck import check, report_lines

NO_STYLES = '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'


def main(argv=None):
    """Run the command; return its exit code."""
    return cli.run("check-tags", _parser(), _run, argv)


def read_parts(path):
    """The parts of the manuscript at `path`, each checked to be well-formed; a Refusal
    naming the fault if it cannot be read."""
    try:
        parts = Docx(path).texts()
    except DocxError as error:
        raise Refusal(str(error)) from None
    except OSError as error:
        raise Refusal(f"{path}: cannot be read: {error.strerror}") from None
    for name, xml in parts.items():
        try:
            ElementTree.fromstring(xml.encode("utf-8"))
        except ElementTree.ParseError:
            raise Refusal(f"{path}: {name} is not well-formed XML") from None
    return parts


def _run(args):
    try:
        rules = load_rules(args.rules)
    except RulesError as error:
        raise Refusal(str(error)) from None
    parts = read_parts(args.manuscript)
    found = blocks(parts[BODY], Styles(parts.get(STYLES, NO_STYLES)), rules["default_font"])
    result = check(found, rules)
    for line in report_lines(result, args.verbose):
        print(line)
    return 1 if result.problems else 0


def _parser():
    parser = argparse.ArgumentParser(
        prog="check-tags",
        description="Check a manuscript's bracketed production tags against a rules file:"
        " their wording, pairing and font, and the fonts and indents of what lies between"
        " each pair. Reads only.",
    )
    parser.add_argument("manuscript", metavar="MANUSCRIPT.docx")
    parser.add_argument(
        "--rules", required=True, metavar="RULES.json", help="the rules file (see the README)"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="also list every pair")
    return parser
