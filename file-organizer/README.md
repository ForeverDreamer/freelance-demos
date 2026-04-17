# file-organizer

Automatic file organizer. Watches a folder, matches incoming files
against YAML rules, and routes them within 2 seconds of detection.

**Status**: 🔴 In progress. Implementation planned for 2026-04-18 to
2026-04-19.

Subdirectory of [freelance-demos](..). Part of an Upwork capability
demo package targeting file-automation briefs.

## Planned structure

```
file-organizer/
├── README.md                # this file (to be expanded)
├── requirements.txt         # watchdog, pyyaml, pytest
├── organizer.py             # watchdog observer entry point
├── config.py                # YAML / JSON rules loader
├── rules.example.yaml
├── actions/
│   └── move.py              # single action in this demo
├── tests/
│   ├── test_config.py
│   ├── test_rules.py
│   └── test_latency.py      # sub-2s detection measurement
├── sample_data/             # synthetic test files
└── logs/
```

## What this demo will show

- Sub-2s detection via `watchdog` OS-level events (inotify /
  ReadDirectoryChangesW / FSEvents)
- YAML rule configuration with extension-based matching
- Single `move` action with errors that do not halt the watcher
- Runnable tests including a latency measurement

## What this demo will NOT do

This is a 60-70% scope capability demo. Full paid delivery adds:

- Multi-root watching with independent rule sets
- Full action set: compress, rename, delete, archive, trash, shell hooks
- Content-based matching: regex on filename, file size, mtime, MIME type
- Windows Task Scheduler XML for silent headless install
- Structured JSON logging with rotation
- Dry-run / preview mode
- Rollback on partial failure
- Config hot-reload
- Per-folder rule overrides

## Coming back

Re-check this folder in 48 hours for runnable code, tests, and a
companion 60-90s demo video.
