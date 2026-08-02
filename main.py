"""
Command-line entry point for the educational keylogger.

Usage
-----
    python main.py                  # start (default)
    python main.py start            # start a capture session
    python main.py list             # list recent sessions
    python main.py view <file>      # pretty-print a session log

    python main.py start -o mylogs
    python main.py start --live
    python main.py start --no-windows
    python main.py start --stop-char q

The program prints its log path on startup (it does not hide itself),
writes keystrokes to a plain-text file you can inspect, and stops
cleanly when the stop combo is pressed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from keylogger import KeyLogger
from viewer import format_list, list_sessions, pretty_print, resolve_log


BANNER = r"""
 ____            _                    _
|  _ \ _   _    | |/ /___ _   _      | |    ___   __ _
| |_) | | | |   | ' // _ \ | | |     | |   / _ \ / _` |
|  __/| |_| |_  | . \  __/ |_| |_    | |__| (_) | (_| |
|_|    \__, (_) |_|\_\___|\__, ( )   |_____\___/ \__, |
       |___/              |___/|/                |___/
        Educational Python Keystroke Logger
""".strip("\n")


ETHICAL_NOTICE = """
=============================================================
                       ETHICAL NOTICE
=============================================================
  This tool is for EDUCATIONAL purposes only.

  Only run it on devices you own, or where you have received
  explicit WRITTEN permission from the owner.

  Unauthorized keystroke logging is illegal in most
  jurisdictions and can carry serious legal consequences.
=============================================================
""".strip("\n")

DEFAULT_LOG_DIR = Path("logs")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="keylogger",
        description="Educational Python keystroke logger.",
        epilog="For educational and authorized-testing use only.",
    )

    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help="Directory where log files live (default: ./logs).",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser(
        "start",
        parents=[shared],
        help="Start a keystroke capture session.",
    )
    start.add_argument(
        "-f",
        "--filename",
        type=str,
        default=None,
        help="Log filename. Default: timestamped keylog_YYYYMMDD_HHMMSS.txt.",
    )
    start.add_argument(
        "--stop-char",
        type=str,
        default="k",
        metavar="CHAR",
        help="Single letter used with Ctrl+Alt to stop (default: k).",
    )
    start.add_argument(
        "--live",
        action="store_true",
        help="Echo captured tokens to the console as you type.",
    )
    start.add_argument(
        "--no-windows",
        action="store_true",
        help="Do not record foreground window titles.",
    )
    start.add_argument(
        "--no-status",
        action="store_true",
        help="Hide the live keystroke counter.",
    )
    start.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the banner and consent prompt.",
    )

    list_p = sub.add_parser(
        "list",
        parents=[shared],
        help="List recent session logs.",
    )
    list_p.add_argument(
        "-n",
        "--limit",
        type=int,
        default=20,
        help="How many sessions to show (default: 20).",
    )

    view = sub.add_parser(
        "view",
        parents=[shared],
        help="Pretty-print a session log.",
    )
    view.add_argument(
        "file",
        help="Log filename, path, or name without .txt",
    )
    view.add_argument(
        "--raw",
        action="store_true",
        help="Print the file as-is without formatting.",
    )
    return parser


def confirm_consent() -> bool:
    """Return True only if the user explicitly acknowledges the ethical notice."""
    try:
        response = input(
            "I will only use this on devices I own or am authorized to test. [y/N]: "
        )
    except EOFError:
        return False
    return response.strip().lower() in {"y", "yes"}


def cmd_start(args: argparse.Namespace) -> int:
    if len(args.stop_char) != 1 or not args.stop_char.isalpha():
        print("[!] --stop-char must be a single ASCII letter.", file=sys.stderr)
        return 2

    if not args.no_banner:
        print(BANNER)
        print()
        print(ETHICAL_NOTICE)
        print()
        if not confirm_consent():
            print("[!] Consent not given. Exiting.")
            return 1

    logger = KeyLogger(
        log_dir=args.output_dir,
        filename=args.filename,
        stop_char=args.stop_char,
        live=args.live,
        track_windows=not args.no_windows,
        status=not args.no_status,
    )

    try:
        logger.start()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by Ctrl+C.")
        return 0
    except Exception as exc:  # noqa: BLE001 — surface any platform-level error
        print(f"[!] Error while running listener: {exc}", file=sys.stderr)
        return 3

    return 0


def cmd_view(args: argparse.Namespace) -> int:
    try:
        path = resolve_log(args.output_dir, args.file)
    except FileNotFoundError as exc:
        print(f"[!] {exc}", file=sys.stderr)
        return 1

    if args.raw:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    else:
        text = pretty_print(path)
    _safe_print(text)
    return 0


def _safe_print(text: str) -> None:
    """Print text even on legacy Windows code pages."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        sys.stdout.buffer.write(
            (text + "\n").encode(encoding, errors="replace")
        )
        sys.stdout.buffer.flush()


def cmd_list(args: argparse.Namespace) -> int:
    sessions = list_sessions(args.output_dir, limit=args.limit)
    _safe_print(format_list(sessions))
    return 0


def _normalize_argv(argv: list[str] | None) -> list[str]:
    """Treat bare flags as `start`, and keep `list` / `view` as-is.

    Examples
    --------
    []                    -> ["start"]
    ["--live"]            -> ["start", "--live"]
    ["-o", "mylogs"]      -> ["start", "-o", "mylogs"]
    ["list"]              -> ["list"]
    ["view", "x.txt"]     -> ["view", "x.txt"]
    ["start", "--live"]   -> ["start", "--live"]
    """
    raw = list(sys.argv[1:] if argv is None else argv)
    if not raw:
        return ["start"]

    first = raw[0]
    if first in {"start", "list", "view", "-h", "--help"}:
        return raw
    # Unknown first token that looks like a flag → start subcommand.
    if first.startswith("-"):
        return ["start", *raw]
    return raw


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(_normalize_argv(argv))

    if args.command == "start":
        return cmd_start(args)
    if args.command == "list":
        return cmd_list(args)
    if args.command == "view":
        return cmd_view(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
