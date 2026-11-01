"""check-tags: check a manuscript's bracketed production tags against a rules file."""

import argparse

from wordtools import cli
from wordtools.cli import Refusal, open_manuscript
from wordtools.layout import Styles, blocks
from wordtools.manuscript import BODY, STYLES
from wordtools.rules import RulesError, load_rules
from wordtools.tagcheck import check, report_lines

NO_STYLES = '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'


def main(argv=None):
    """Run the command; return its exit code."""
    return cli.run("check-tags", _parser(), _run, argv)


def _run(args):
    try:
        rules = load_rules(args.rules)
    except RulesError as error:
        raise Refusal(str(error)) from None
    parts = open_manuscript(args.manuscript).texts()
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
