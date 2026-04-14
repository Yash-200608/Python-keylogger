"""
Command-line entry point for the educational keylogger.

Usage
-----
    python main.py                  # default: logs/ directory, Ctrl+Alt+K to stop
    python main.py -o mylogs        # write logs to ./mylogs
    python main.py -f today.txt     # fixed filename instead of timestamped
    python main.py --stop-char q    # change stop combo to Ctrl+Alt+Q
    python main.py --no-banner      # skip the banner and consent prompt

The program prints its log path on startup (it does not hide itself),
writes keystrokes to a plain-text file you can inspect, and stops
cleanly when the stop combo is pressed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from keylogger import KeyLogger


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


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="keylogger",
        description="Educational Python keystroke logger.",
        epilog="For educational and authorized-testing use only.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("logs"),
        help="Directory where log files are written (default: ./logs).",
    )
    parser.add_argument(
        "-f",
        "--filename",
        type=str,
        default=None,
        help="Log filename. Default: timestamped keylog_YYYYMMDD_HHMMSS.txt.",
    )
    parser.add_argument(
        "--stop-char",
        type=str,
        default="k",
        metavar="CHAR",
        help="Single letter used with Ctrl+Alt to stop the logger (default: k).",
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the banner and consent prompt (for automated testing).",
    )
    return parser.parse_args(argv)


def confirm_consent() -> bool:
    """Return True only if the user explicitly acknowledges the ethical notice."""
    try:
        response = input(
            "I will only use this on devices I own or am authorized to test. [y/N]: "
        )
    except EOFError:
        return False
    return response.strip().lower() in {"y", "yes"}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

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


if __name__ == "__main__":
    sys.exit(main())
