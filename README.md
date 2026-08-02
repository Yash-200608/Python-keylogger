# Python Keylogger

A simple, cross-platform keystroke logger written in Python for **educational
purposes**. It demonstrates how a user-space program can receive global
keyboard events through the operating system, using the `pynput` library.

> ### Ethical Notice
> This project is for **learning and authorized security testing only**.
> Run it **only on devices you own** or where you have **explicit written
> permission** from the owner.
> Unauthorized keystroke logging is illegal in most jurisdictions
> (e.g. the US CFAA, the UK Computer Misuse Act, the EU GDPR).
> The author and contributors accept no responsibility for misuse.

---

## Features

- Cross-platform keystroke capture (Windows / macOS / Linux)
- Human-readable output (special keys rendered as `[ENTER]`, `[BACKSPACE]`, `[UP]`, …)
- **Foreground window titles** recorded when focus changes (see which app got the keys)
- **Live status line** — keystroke count, elapsed time, and current app
- **Live echo mode** (`--live`) — watch tokens appear as you type
- Simple commands: `start`, `list`, `view`
- Timestamped log files in a local `logs/` directory
- Clean stop via a configurable hotkey (`Ctrl + Alt + K` by default)
- Visible, non-stealth operation — announces itself and prints the log path
- Explicit consent prompt on startup
- Session summary with duration and keys/sec

## Quick start

```bash
python main.py                 # start capturing (same as: python main.py start)
# type something, switch apps, then press Ctrl+Alt+K to stop

python main.py list            # see recent sessions
python main.py view <file>     # pretty-print a session
```

## Project structure

```
Python-keylogger/
├── main.py            # CLI entry point (start / list / view)
├── keylogger.py       # KeyLogger class (events, buffering, status)
├── viewer.py          # Session list + pretty-print
├── window_info.py     # Foreground window title helpers
├── requirements.txt   # Python dependencies
├── .gitignore
├── logs/              # Captured sessions (git-ignored)
└── README.md
```

## Requirements

- Python **3.9** or newer
- [`pynput`](https://pypi.org/project/pynput/) `>= 1.7.6`

On Linux you may additionally need the X server development headers
(`python3-xlib` / `libx11-dev`) — see the pynput docs for your distro.
Optional: `xdotool` for window-title tracking on X11.

## Installation

```bash
git clone https://github.com/Yash-200608/Python-keylogger.git
cd Python-keylogger

python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

## Usage

### Capture a session

```bash
python main.py
# or
python main.py start
```

You will see a banner, an ethical-use notice, and a consent prompt.
Type `y` and press Enter to continue. A live status line shows key count
and the focused app. Press **`Ctrl + Alt + K`** to stop.

### Browse sessions

```bash
python main.py list
python main.py view keylog_20260802_164500.txt
python main.py view keylog_20260802_164500      # .txt optional
```

### Options (`start`)

| Option | Description | Default |
| --- | --- | --- |
| `-o`, `--output-dir` | Directory for log files. | `./logs` |
| `-f`, `--filename` | Fixed log filename instead of timestamped. | `keylog_<date>_<time>.txt` |
| `--stop-char` | Letter used with `Ctrl+Alt` to stop. | `k` |
| `--live` | Echo captured tokens to the console. | off |
| `--no-windows` | Skip foreground window markers. | off |
| `--no-status` | Hide the live status line. | off |
| `--no-banner` | Skip banner and consent (for tests). | off |

Examples:

```bash
python main.py start --live                 # see keys as they are logged
python main.py start -o mylogs              # write to ./mylogs
python main.py start -f today.txt           # fixed filename
python main.py start --stop-char q          # stop with Ctrl+Alt+Q
python main.py start --no-windows           # keys only, no app titles
python main.py list -n 5
python main.py view today.txt --raw         # dump file unchanged
```

### Example log output

```
=== Session started 2026-08-02 16:45:02 ===
[WINDOW] Untitled - Notepad
hello world

[WINDOW] Python-keylogger - Cursor
this is a test[BACKSPACE][BACKSPACE][BACKSPACE]demo

=== Session ended 2026-08-02 16:45:47 (34 keystrokes captured) ===
```

## How it works

1. `main.py` routes `start` / `list` / `view`, prints the ethical notice, and asks for consent.
2. `KeyLogger.start()` opens the log file, seeds the current window title, and attaches a `pynput.keyboard.Listener`.
3. On each key press:
   - If the stop combo is held → write footer, flush, exit.
   - If the focused window changed → write a `[WINDOW]` marker.
   - Otherwise format the key and buffer it (flush on Enter / stop).
4. A background thread refreshes the status line (count, time, app).
5. `viewer.py` parses session headers, window markers, and keystroke totals for `list` / `view`.

Modifier keys (Ctrl / Alt / Shift / Cmd / Caps-Lock) are tracked but not
written alone — the logger records the character they modify (Shift+`a` → `A`).

## What this project is **not**

To keep it clearly educational, this project intentionally does **not**
include:

- Network exfiltration or remote control
- Persistence, autostart, or hiding from task managers
- Anti-debug, anti-VM, or detection-evasion techniques
- Screenshot, clipboard, or microphone capture

## Troubleshooting

- **`ImportError: No module named pynput`** — activate your venv and run
  `pip install -r requirements.txt`.
- **macOS: keystrokes are not captured** — grant Terminal (or your
  Python interpreter) *Accessibility* and *Input Monitoring* permissions
  in *System Settings → Privacy & Security*.
- **Linux: `ImportError: Xlib` or no events** — install `python3-xlib`
  and ensure you are running an X session (Wayland is not supported by
  pynput's key hook).
- **Window titles missing on Linux** — install `xdotool` (X11) or use
  `--no-windows`.
- **Windows: some keys print as `[VK_...]`** — pynput could not map the
  scan code (often non-US layouts). Cosmetic; the event was still captured.

## License

Released for educational use. See the repository for any license file.
If none is present, treat the code as "all rights reserved" and ask the
author before redistributing.

## Author

[Yash](https://github.com/Yash-200608)
