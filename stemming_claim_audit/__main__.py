"""Command line entry point."""
import argparse
import json
from . import __version__
from .audit import audit


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    parser = Parser(description='Audit documentation claims offline.')
    parser.add_argument('--version', action='store_true')
    sub = parser.add_subparsers(dest='command', parser_class=Parser)
    command = sub.add_parser('audit')
    command.add_argument('repo', nargs='?', default='.')
    command.add_argument('--json', action='store_true')
    command.add_argument('--verbose', action='store_true')
    command.add_argument('--ignore', action='append', default=[])
    command.add_argument('--fail-on', choices=['high', 'medium'], default='high')
    try:
        args = parser.parse_args(argv)
        if args.version:
            print(__version__)
            return 0
        if args.command != 'audit':
            parser.print_help()
            return 1
        decisions = []
        findings = audit(args.repo, args.ignore, decisions)
        if args.verbose:
            import sys
            print('Scope: README.md, docs/**/*.md, tests/ fixtures, Python sources', file=sys.stderr)
            for decision in decisions: print(decision, file=sys.stderr)
        if args.json:
            print(json.dumps(findings, indent=2))
        elif findings:
            for finding in findings:
                print('{severity} {verdict} {path}: {message}'.format(**finding))
        else:
            print('PASS')
        return 2 if any(f['severity'] == 'HIGH' or args.fail_on == 'medium' for f in findings) else 0
    except (OSError, UnicodeError, ValueError) as exc:
        print('Error: ' + str(exc))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
