from __future__ import annotations

import argparse


def _cmd_app(_args: argparse.Namespace) -> int:
    from .app import main as app_main

    app_main()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recordprep")
    subparsers = parser.add_subparsers(dest="command")

    app_parser = subparsers.add_parser("app", help="launch the GTK app")
    app_parser.set_defaults(func=_cmd_app)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        args = parser.parse_args(["app", *(argv or [])])
    return int(args.func(args))

