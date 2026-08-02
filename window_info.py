"""
Best-effort foreground window / app title helpers.

Used so session logs can show *which application* received keystrokes —
useful for learning how input is routed, not for stealth.
Returns None when the platform API is unavailable.
"""

from __future__ import annotations

import sys
from typing import Optional


def get_foreground_title() -> Optional[str]:
    """Return the title of the currently focused window, or None."""
    if sys.platform == "win32":
        return _windows_title()
    if sys.platform == "darwin":
        return _macos_title()
    return _linux_title()


def _windows_title() -> Optional[str]:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        return title or None
    except Exception:  # noqa: BLE001 — platform helpers must never crash the logger
        return None


def _macos_title() -> Optional[str]:
    try:
        from AppKit import NSWorkspace  # type: ignore

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        name = app.localizedName()
        return str(name) if name else None
    except Exception:  # noqa: BLE001
        return None


def _linux_title() -> Optional[str]:
    try:
        import subprocess

        # Prefer xdotool when present (X11). Silent on Wayland / missing tools.
        result = subprocess.run(
            ["xdotool", "getactivewindow", "getwindowname"],
            capture_output=True,
            text=True,
            timeout=0.5,
            check=False,
        )
        if result.returncode == 0:
            title = result.stdout.strip()
            return title or None
    except Exception:  # noqa: BLE001
        pass
    return None
