# video-creation-pipeline

Architecture showcase for an **agentic code-to-video pipeline** where Claude Code drives Blender (procedural 3D) and Adobe CEP + ExtendScript (programmatic 2D compositions) as long-lived TCP services.

Subdirectory of [freelance-demos](https://github.com/ForeverDreamer/freelance-demos). Companion to [sapphire-studios-promo](../sapphire-studios-promo/), which shows the lighter HTML + GSAP path via Hyperframes. This directory shows the heavier path: full 3D, procedural simulation, compositor depth.

## Why this demo exists

Clients hiring an "AI Video Engineer" want to verify one specific thing: can this person drive Blender and After Effects from Claude Code as if those apps were libraries, with the same discipline a senior backend engineer brings to a microservice.

A traditional portfolio (rendered reels, Dribbble clips) does not answer that question. Architecture and a reproducible demo do.

## What is in this subdirectory

- `README.md` (this file), high level thesis and quick run
- `ARCHITECTURE.md`, deeper dive with data flow, three pillars, MCP sketch
- `demo/`, a self-contained reproducible pipeline that a reviewer can run locally
- `pyproject.toml`, minimal dependencies for the demo orchestrator

That is it. The production pipeline is larger by roughly two orders of magnitude (see [Scale signals](#scale-signals) below), but everything load-bearing about the architecture is captured in the files above.

## Architecture at a glance

```
┌──────────────────────────────────────────────────────────────┐
│  WSL2 Ubuntu (dev environment)                               │
│                                                              │
│    Claude Code                                               │
│      │ slash commands, skills, MCP tool calls                │
│      ▼                                                       │
│    CLI wrappers (blender_cli.sh, adobe_cli.sh)               │
│      │ JSON / JSX payload                                    │
│      ▼                                                       │
│    Python bridge clients                                     │
│      │ raw TCP                                               │
└──────┼───────────────────────────────────────────────────────┘
       │
┌──────▼───────────────────────────────────────────────────────┐
│  Windows host (always-running creative apps)                 │
│                                                              │
│    Blender 4.4+       ◄── 19876 ── bridge-server addon       │
│    After Effects      ◄── 19877 ── CEP plugin (Node.js TCP)  │
│    Premiere Pro       ◄── 19878 ── CEP plugin                │
│    Photoshop          ◄── 19879 ── CEP plugin                │
│    Illustrator        ◄── 19880 ── CEP plugin                │
└──────────────────────────────────────────────────────────────┘
```

Three invariants make this work:

1. **Zero restart cost.** Creative apps stay running. Script edits reload in 2 to 5 seconds, not 30 to 60.
2. **Text wire protocol.** JSON for Blender, raw JSX for Adobe. Debuggable with `netcat`.
3. **Language isolation.** Python talks Python, JSX talks JSX. The bridge only ferries text.

Full walkthrough in [ARCHITECTURE.md](ARCHITECTURE.md).

## Quick run: the demo pipeline

The `demo/` subdirectory is a minimal end-to-end pipeline that a reviewer can run without any Windows setup, without CEP, without the TCP bridge. It renders a short procedural clip from a text prompt, end to end.

```bash
# Prerequisites: Blender 4.0+ on PATH, ffmpeg, Python 3.11+
cd demo
python pipeline.py --prompt prompt.txt --out /tmp/demo.mp4
```

What happens:

1. `pipeline.py` reads `prompt.txt` (one line, e.g. "a blue cube rotating on white background, 3 seconds")
2. Parses the prompt into a config (color, duration), passes it to `blender_render.py`
3. Invokes `blender --background --python blender_render.py -- <args>`, which builds the scene procedurally and renders 90 frames to PNG
4. Invokes `ffmpeg_export.sh` to assemble the frames into `/tmp/demo.mp4`

Total runtime on a warm laptop: roughly 30 to 60 seconds, dominated by Blender's own render.

### Why the demo uses `--background` mode, not the TCP bridge

The production pipeline runs Blender as a long-lived process with the `bridge-server` addon on TCP 19876. That gives 2 to 5 second feedback loops for iterative work.

This demo intentionally uses the simpler `blender --background --python <script>` path. Reasons:

- It runs cross-platform (Linux, macOS, Windows) with only `blender` and `ffmpeg` on PATH
- It does not require installing an addon, opening a GUI, or configuring ports
- The architectural thesis (Claude Code reads a prompt, builds a scene procedurally, orchestrates a pipeline) is visible end to end
- The TCP bridge is an optimization, not the claim

A reviewer who wants to verify the bridge architecture can read [ARCHITECTURE.md](ARCHITECTURE.md), where the data flow, lifecycle, and failure modes are documented with the same rigor as an RFC. The receiving-side sketches (Blender addon registration, CEP Node.js TCP server bootstrap) are there. The shipping bridge implementations stay in the private main repo.

## Scale signals

Numbers below describe the private `video_creation_x` main repo as of 2026-04-19, for calibration. This public subdirectory is a small fraction.

| Signal | Main repo | Here |
| ---- | ---- | ---- |
| Git commits | ~2,800 | 1 (squashed) |
| Top-level directories | 18 | 1 |
| Claude Code slash commands | 34 | 0 shipped (documented) |
| Claude Code skills | 10 | 0 shipped (documented) |
| MCP servers | 2 | 0 shipped (architecture described) |
| Blender procedural effect libraries | 11 | 0 shipped (1 demo scene) |
| CEP bridge plugins | 4 (AE, Premiere, Photoshop, Illustrator) | 0 shipped (architecture described) |
| Lines of code | ~100k across Python + JSX + Bash + PowerShell | ~500 (demo + docs) |

The main repo is where the delivery value lives. This subdirectory exists so clients can calibrate depth before engaging.

## What this demo does NOT do

- No TCP bridge implementation. The `bridge-server` Blender addon and the Adobe CEP plugins are not shipped here. Their architecture is described in [ARCHITECTURE.md](ARCHITECTURE.md).
- No MCP server code. Architecture only.
- No slash commands, no skills, no `.claude/` directory. Those are workflow-specific and stay private.
- No After Effects JSX examples. The demo is Blender-only. AE patterns are documented in [ARCHITECTURE.md](ARCHITECTURE.md).
- No production assets. No `.blend` files, no project binaries, no rendered reels.

Everything listed above is available under contract. This subdirectory proves the architecture is real and the author writes it at depth. The rest is paid work.

## Related

- [sapphire-studios-promo](../sapphire-studios-promo/), the lighter HTML + GSAP + Hyperframes counterpart in this same monorepo
- [ForeverDreamer on GitHub](https://github.com/ForeverDreamer)
- Available for AI Video Engineer, creative automation, and agentic workflow engagements. Contact via GitHub issues on [freelance-demos](https://github.com/ForeverDreamer/freelance-demos).

## License

MIT. See [LICENSE](../LICENSE) at the monorepo root.
