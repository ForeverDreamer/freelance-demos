# file-organizer

Automatic file organizer. Watches a folder, matches incoming files
against YAML rules, and routes them within 2 seconds of detection.

Subdirectory of [freelance-demos](https://github.com/ForeverDreamer/freelance-demos).
Reference implementation for file-automation briefs on Upwork.

## Why this is interesting

Most "watched folder" scripts poll every 30 to 60 seconds and miss
bursty writes. This one uses `watchdog` event notifications backed by
OS-level file system events (inotify on Linux, ReadDirectoryChangesW on
Windows, FSEvents on macOS), so detection latency is under 2 seconds
on every platform.

See `tests/test_latency.py` for the measurement.

## Prerequisites

This project requires **Python 3.11+** and [uv](https://docs.astral.sh/uv/)
for dependency management. You do **not** need to install Python
separately — `uv` will fetch and manage the interpreter for you.

### Windows

Open PowerShell and run:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then restart the terminal so `uv` is on your `PATH`. Verify with:

```powershell
uv --version
```

### macOS

Open Terminal and run either of:

```bash
# Official installer (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via Homebrew
brew install uv
```

Verify with `uv --version`.

## Downloading only this subfolder

The full repo contains several unrelated demos, but you do **not** need
to install git or clone anything. Just grab the ZIP:

1. Open <https://github.com/ForeverDreamer/freelance-demos> in your browser
2. Click the green **Code** button, then **Download ZIP**
3. Unzip the file:
   - **Windows**: right-click the ZIP → *Extract All…* → pick a folder
     (e.g. `Desktop\freelance-demos`)
   - **macOS**: double-click the ZIP in Finder — it extracts next to the ZIP
4. Open the extracted folder. You only need the `file-organizer/` subfolder
   — you can delete the rest if you want.
5. Open a terminal inside `file-organizer/`:
   - **Windows**: in File Explorer, click the address bar, type `powershell`,
     and press Enter
   - **macOS**: right-click the folder in Finder → *New Terminal at Folder*
     (enable this under *System Settings → Keyboard → Keyboard Shortcuts →
     Services* if you don't see it)

## Quick start

Run these commands from inside the `file-organizer/` folder (the terminal
you opened in the previous section).

### Windows (PowerShell)

```powershell
uv sync
Copy-Item rules.example.yaml rules.yaml
uv run python organizer.py --config rules.yaml --watch .\sample_data
```

### macOS (Terminal)

```bash
uv sync
cp rules.example.yaml rules.yaml
uv run python organizer.py --config rules.yaml --watch ./sample_data
```

Then drop any file into the `sample_data` folder and watch the log print
which rule matched.

## What this demo shows

| Capability | Where | Proof |
|---|---|---|
| Sub-2s detection | `organizer.py` watchdog observer | `tests/test_latency.py` |
| YAML / JSON config parsing | `config.py` | `tests/test_config.py` |
| Extension-based rule matching | `config.py` + `actions/move.py` | `tests/test_config.py::test_match_case_insensitive` |
| Move action with collision handling | `actions/move.py` | `tests/test_rules.py::test_move_collision` |
| Errors do not halt the watcher | `organizer.py` `_process` outer try/except | `tests/test_rules.py::test_error_recovery` |
| Plain-text log with rule trace | stdout (configurable via `--log-level`) | runtime output |

## What this demo does NOT do

This is a capability demo, not a production deployment. A full paid
delivery adds:

- **Multi-root watching** with independent rule sets per root
- **Full action set** beyond `move`: compress, rename, delete, archive,
  trash, custom shell hooks
- **Content-based matching**: regex on filename, file size, mtime,
  MIME type, magic bytes (demo only matches file extensions)
- **One-click auto-start installer for Windows and macOS** — pre-built
  Task Scheduler XML + PowerShell registrar on Windows, and a launchd
  `.plist` + `launchctl bootstrap` script on macOS. Client double-clicks
  once and the watcher runs headless at boot, skipping the GUI minefield
  (Windows: startup trigger, run-as account, highest privileges, retry
  policy; macOS: LaunchAgent vs LaunchDaemon placement, Login Items
  authorization on macOS 13+, Full Disk Access grants, absolute `uv`
  path since launchd ignores shell `PATH`)
- **Structured JSON logging** with rotation and optional external
  sinks (syslog, ELK, CloudWatch)
- **Dry-run / preview mode** before applying destructive actions
- **Rollback on partial failure** when a multi-step action halts mid-way
- **Config hot-reload** without restarting the watcher
- **Per-folder overrides and rule inheritance**
- **Test coverage for your specific file layout and edge cases**

If any of these matter for your project, that is the paid work.

## Running the tests

```bash
uv sync
uv run pytest tests/
```

Expected: 13 tests pass in under 2 seconds, including the sub-2s latency assertion.

## Scheduling

### Linux / macOS (cron)

```
@reboot /usr/bin/python3 /path/to/organizer.py --config /path/to/rules.yaml --watch /path/to/folder
```

### Windows (Task Scheduler)

Quick hint: run via `pythonw.exe` + Task Scheduler trigger "At startup".
Full XML import and service-wrap is part of paid delivery.

## License

MIT. Fork, read, learn freely.

## Custom builds

For your specific project, folder map, rule set, production deployment,
or ongoing maintenance, reach out on Upwork: <https://www.upwork.com/freelancers/~0140562708001afd27>
