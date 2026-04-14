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
- Timestamped log files, each saved to a local `logs/` directory
- Clean stop via a configurable hotkey (`Ctrl + Alt + K` by default)
- Visible, non-stealth operation — the program announces itself and prints
  the exact file path it is writing to
- Explicit consent prompt on startup
- Small, well-commented code suitable for reading and learning

## Project structure

```
Python-keylogger/
├── main.py            # CLI entry point (banner, consent, argparse)
├── keylogger.py       # KeyLogger class (event loop, key formatting, log I/O)
├── requirements.txt   # Python dependencies
├── .gitignore         # Excludes logs/, __pycache__, venvs, IDE files
├── logs/              # Captured sessions land here (git-ignored)
└── README.md
```

## Requirements

- Python **3.9** or newer
- [`pynput`](https://pypi.org/project/pynput/) `>= 1.7.6`

On Linux you may additionally need the X server development headers
(`python3-xlib` / `libx11-dev`) — see the pynput docs for your distro.

## Installation

```bash
# Clone the repository
git clone https://github.com/Yash-200608/Python-keylogger.git
cd Python-keylogger

# (Recommended) create and activate a virtual environment
python -m venv venv
# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

Run the program from the project root:

```bash
python main.py
```

You will see a banner, an ethical-use notice, and a consent prompt.
Type `y` and press Enter to continue. The logger will print the exact
log file path it is writing to, then start capturing keystrokes.

Press **`Ctrl + Alt + K`** at any time to stop. A summary line is written
to the log and the total keystroke count is printed to the console.

### Command-line options

| Option | Description | Default |
| --- | --- | --- |
| `-o`, `--output-dir` | Directory where log files are written. | `./logs` |
| `-f`, `--filename`   | Fixed log filename instead of a timestamped one. | `keylog_<date>_<time>.txt` |
| `--stop-char`        | Single letter used with `Ctrl+Alt` to stop the logger. | `k` |
| `--no-banner`        | Skip the banner and consent prompt (for automated tests). | off |

Examples:

```bash
python main.py                        # default behavior
python main.py -o mylogs              # write to ./mylogs
python main.py -f today.txt           # fixed filename
python main.py --stop-char q          # stop with Ctrl+Alt+Q
```

### Example log output

```
=== Session started 2026-04-14 21:45:02 ===
hello world[ENTER]
this is a test[BACKSPACE][BACKSPACE][BACKSPACE]demo[ENTER]

=== Session ended 2026-04-14 21:45:47 (34 keystrokes captured) ===
```

## How it works

1. `main.py` parses CLI flags, prints the ethical notice, and asks for consent.
2. It constructs a `KeyLogger` (from `keylogger.py`) pointing at a log file
   inside the output directory.
3. `KeyLogger.start()` attaches a `pynput.keyboard.Listener` that runs in a
   background thread managed by pynput. Two callbacks are registered:
   - `_on_press` — formats the key and appends it to the log file; if the
     stop combo is held, writes a footer and returns `False` to signal the
     listener to exit.
   - `_on_release` — keeps the "currently pressed" set accurate so multi-key
     combos do not appear sticky.
4. The main thread blocks on `listener.join()` until the stop combo fires.

Modifier keys (Ctrl / Alt / Shift / Cmd / Caps-Lock) are tracked but not
written to the log on their own — the logger records the character they
modify (for example, Shift+`a` is logged as `A`).

## What this project is **not**

To keep it clearly educational, this project intentionally does **not**
include:

- Network exfiltration or remote control
- Persistence, autostart, or hiding from task managers
- Anti-debug, anti-VM, or detection-evasion techniques
- Screenshot, clipboard, or microphone capture

If you want to extend it for a classroom exercise, consider features that
make the tool *more* transparent — for example, a live on-screen counter,
a "redact passwords" mode, or a viewer that replays a session.

## Troubleshooting

- **`ImportError: No module named pynput`** — make sure your virtual
  environment is activated and run `pip install -r requirements.txt`.
- **macOS: keystrokes are not captured** — grant Terminal (or your
  Python interpreter) *Accessibility* and *Input Monitoring* permissions
  in *System Settings → Privacy & Security*.
- **Linux: `ImportError: Xlib` or no events** — install `python3-xlib`
  and ensure you are running an X session (Wayland is not supported by
  pynput's key hook).
- **Windows: some keys print as `[VK_...]`** — this means pynput could
  not map the scan code to a character, usually on non-US layouts. It is
  cosmetic; the raw event was still captured.

## License

Released for educational use. See the repository for any license file.
If none is present, treat the code as "all rights reserved" and ask the
author before redistributing.

## Author

[Yash](https://github.com/Yash-200608)
