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

## Quick start

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

```bash
uv sync
cp rules.example.yaml rules.yaml
uv run python organizer.py --config rules.yaml --watch ./sample_data
```

Drop any file into `./sample_data` and watch the log.

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
- **Windows Task Scheduler XML** for silent headless install
  (cron snippet is in this README, Windows install is paid delivery)
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

Expected: 11 tests pass in under a second, including the sub-2s latency assertion.

## Scheduling

### Linux / macOS (cron)

```
@reboot /usr/bin/python3 /path/to/organizer.py --config /path/to/rules.yaml --watch /path/to/folder
```

### Windows

Quick hint: run via `pythonw.exe` + Task Scheduler trigger "At startup".
Full XML import and service-wrap is part of paid delivery.

## License

MIT. Fork, read, learn freely.

## Custom builds

For your specific project, folder map, rule set, production deployment,
or ongoing maintenance, reach out on Upwork: `<YOUR_UPWORK_PROFILE_URL>`
