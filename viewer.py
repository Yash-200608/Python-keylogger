"""
Session log viewer for the educational keylogger.

Makes captured sessions easy to skim: lists recent logs, pretty-prints
content with window markers highlighted, and shows quick stats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


WINDOW_RE = re.compile(r"^\[WINDOW\]\s+(.*)$")
START_RE = re.compile(
    r"^=== Session started\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s*==="
)
END_RE = re.compile(
    r"^=== Session ended\s+(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})"
    r"(?:\s+\((\d+)\s+keystrokes captured\))?\s*==="
)
TOKEN_RE = re.compile(r"\[[A-Z0-9_]+\]")


@dataclass
class SessionStats:
    path: Path
    started: Optional[datetime]
    ended: Optional[datetime]
    keystrokes: int
    windows: list[str]
    size_bytes: int


def _parse_dt(text: str) -> Optional[datetime]:
    try:
        return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def _read_text(path: Path) -> str:
    """Read a log file, stripping a UTF-8 BOM if present."""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def analyze_log(path: Path) -> SessionStats:
    """Extract lightweight stats from a session log."""
    text = _read_text(path)
    started: Optional[datetime] = None
    ended: Optional[datetime] = None
    keystrokes = 0
    windows: list[str] = []

    for line in text.splitlines():
        m = START_RE.match(line.strip())
        if m:
            started = _parse_dt(m.group(1))
            continue
        m = END_RE.match(line.strip())
        if m:
            ended = _parse_dt(m.group(1))
            if m.group(2):
                keystrokes = int(m.group(2))
            continue
        m = WINDOW_RE.match(line.strip())
        if m:
            title = m.group(1).strip()
            if title and title not in windows:
                windows.append(title)

    if keystrokes == 0:
        # Approximate: count printable chars + special tokens, skip markers.
        body_lines = []
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("===") or s.startswith("[WINDOW]"):
                continue
            body_lines.append(line)
        body = "\n".join(body_lines)
        tokens = TOKEN_RE.findall(body)
        stripped = TOKEN_RE.sub("", body)
        # Also count bracket tokens that include punctuation (e.g. [<75>]).
        other = re.findall(r"\[[^\]]+\]", stripped)
        stripped = re.sub(r"\[[^\]]+\]", "", stripped)
        keystrokes = (
            len(tokens)
            + len(other)
            + sum(1 for c in stripped if not c.isspace() or c == " ")
        )

    return SessionStats(
        path=path,
        started=started,
        ended=ended,
        keystrokes=keystrokes,
        windows=windows,
        size_bytes=path.stat().st_size,
    )


def list_sessions(log_dir: Path, limit: int = 20) -> list[SessionStats]:
    """Return recent session stats, newest first."""
    log_dir = Path(log_dir)
    if not log_dir.exists():
        return []
    files = sorted(
        (p for p in log_dir.glob("*.txt") if p.is_file()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [analyze_log(p) for p in files[:limit]]


def resolve_log(log_dir: Path, name: str) -> Path:
    """Resolve a log path from a bare name, relative path, or absolute path."""
    candidate = Path(name)
    if candidate.is_file():
        return candidate
    under_dir = Path(log_dir) / name
    if under_dir.is_file():
        return under_dir
    # Allow omitting .txt
    if not name.endswith(".txt"):
        under_dir = Path(log_dir) / f"{name}.txt"
        if under_dir.is_file():
            return under_dir
    raise FileNotFoundError(f"No log found matching '{name}' in {log_dir}")


def format_list(sessions: list[SessionStats]) -> str:
    if not sessions:
        return "No sessions found. Run: python main.py start"

    lines = [
        f"{'#':<3} {'File':<28} {'Keys':>6} {'Size':>8}  Started",
        "-" * 72,
    ]
    for i, s in enumerate(sessions, 1):
        started = s.started.strftime("%Y-%m-%d %H:%M") if s.started else "—"
        size = _human_size(s.size_bytes)
        lines.append(
            f"{i:<3} {s.path.name:<28} {s.keystrokes:>6} {size:>8}  {started}"
        )
    lines.append("")
    lines.append('View one:  python main.py view <filename>')
    return "\n".join(lines)


def pretty_print(path: Path, *, show_stats: bool = True) -> str:
    """Return a readable rendering of a session log."""
    stats = analyze_log(path)
    raw = _read_text(path)
    out: list[str] = []

    if show_stats:
        out.append("=" * 56)
        out.append(f"  {path.name}")
        if stats.started:
            out.append(f"  Started    : {stats.started:%Y-%m-%d %H:%M:%S}")
        if stats.ended:
            out.append(f"  Ended      : {stats.ended:%Y-%m-%d %H:%M:%S}")
        out.append(f"  Keystrokes : {stats.keystrokes}")
        out.append(f"  Size       : {_human_size(stats.size_bytes)}")
        if stats.windows:
            out.append(f"  Apps       : {len(stats.windows)}")
            for w in stats.windows[:8]:
                out.append(f"               - {w}")
            if len(stats.windows) > 8:
                out.append(f"               ... +{len(stats.windows) - 8} more")
        out.append("=" * 56)
        out.append("")

    in_window = False
    for line in raw.splitlines():
        stripped = line.strip()
        m = WINDOW_RE.match(stripped)
        if m:
            out.append("")
            out.append(f"[+] {m.group(1).strip()}")
            in_window = True
            continue
        if stripped.startswith("==="):
            in_window = False
            out.append(line)
            continue
        if in_window:
            out.append(f"    {line}" if line else "")
        else:
            out.append(line)

    out.append("")
    return "\n".join(out)


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.1f} MB"
