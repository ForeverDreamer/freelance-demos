# ARCHITECTURE — video-creation-pipeline

Deep dive for the code-to-video pipeline introduced in [README.md](README.md). This document covers the bridge pattern, the three pillars (Blender, Adobe, Claude Code), and the MCP layer that sits on top.

The shipping implementations of the bridge live in the private main repo. This document is detailed enough that someone reading it with Blender and After Effects open could reproduce the core architecture in a few weeks.

## 目录

- [1. The constraint shaping every decision](#1-the-constraint-shaping-every-decision)
- [2. The bridge pattern](#2-the-bridge-pattern)
  - [2.1 Wire layout](#21-wire-layout)
  - [2.2 Request lifecycle: Blender](#22-request-lifecycle-blender)
  - [2.3 Request lifecycle: After Effects](#23-request-lifecycle-after-effects)
  - [2.4 Why this matters for agents](#24-why-this-matters-for-agents)
- [3. Pillar 1 — Blender 3D procedural rendering](#3-pillar-1--blender-3d-procedural-rendering)
  - [3.1 Effect library shape](#31-effect-library-shape)
  - [3.2 Why modular, not monolithic](#32-why-modular-not-monolithic)
  - [3.3 The bridge-server addon](#33-the-bridge-server-addon)
- [4. Pillar 2 — Adobe CEP + ExtendScript](#4-pillar-2--adobe-cep--extendscript)
  - [4.1 CEP plugin layout](#41-cep-plugin-layout)
  - [4.2 Why CEP, not UXP or ScriptUI](#42-why-cep-not-uxp-or-scriptui)
  - [4.3 Modular JSX composition pattern](#43-modular-jsx-composition-pattern)
- [5. Pillar 3 — Claude Code as operator](#5-pillar-3--claude-code-as-operator)
  - [5.1 Slash commands](#51-slash-commands)
  - [5.2 Skills (auto-triggering behaviors)](#52-skills-auto-triggering-behaviors)
  - [5.3 CLAUDE.md conventions](#53-claudemd-conventions)
- [6. The MCP layer (optional)](#6-the-mcp-layer-optional)
  - [6.1 Two paths, same destination](#61-two-paths-same-destination)
  - [6.2 Why two paths exist](#62-why-two-paths-exist)
  - [6.3 MCP server sketch](#63-mcp-server-sketch)
- [7. What would it take to reproduce this](#7-what-would-it-take-to-reproduce-this)
- [8. References](#8-references)

---

## 1. The constraint shaping every decision

Blender and the Adobe Creative Cloud apps run natively on Windows. Claude Code, the Python orchestration layer, the Bash CLIs, and developer tooling live in WSL2 Ubuntu. The pipeline crosses that boundary on every render.

Two traditional options were considered and rejected:

1. **CLI-only scripting** (Blender `--background --python`, Adobe via ExtendScript Toolkit). Rejected because process startup is 30 to 60 seconds per change, which breaks the feedback loop agentic work depends on.
2. **GUI + macro recording** (ScriptUI dialogs, Blender addon panels). Rejected because agents cannot reliably drive GUIs and the output is not versionable.

The chosen architecture keeps Blender and each Adobe app **always running** and addresses them as long-lived TCP services.

Note on this subdirectory's demo: the `demo/` pipeline intentionally uses `blender --background --python` (option 1 above) because it is self-contained and cross-platform. That path has the slower feedback loop, but it is the right tradeoff for a reproducible public demo. The production bridge pattern, described below, is what powers real work.

## 2. The bridge pattern

### 2.1 Wire layout

```
┌─────────────────────────────────────────────────────────────┐
│  WSL2 Ubuntu                                                │
│                                                             │
│   Claude Code                                               │
│     │ invokes                                               │
│     ▼                                                       │
│   /slash commands  (.claude/commands/*.md)                  │
│     │ shell out                                             │
│     ▼                                                       │
│   CLI wrappers (blender_cli.sh, adobe_cli.sh)               │
│     │ argparse + validation                                 │
│     ▼                                                       │
│   Python bridge clients (bl/apis/, adobe/apis/)             │
│     │ build JSON / JSX payload                              │
│     ▼                                                       │
│   Raw TCP socket send (127.0.0.1 via WSL localhost fwd)     │
└─────┬───────────────────────────────────────────────────────┘
      │
┌─────▼───────────────────────────────────────────────────────┐
│  Windows host                                               │
│                                                             │
│   ┌─ port 19876 ── Blender bridge-server addon (Python)     │
│   │                 runs inside live Blender process        │
│   │                                                         │
│   ├─ port 19877 ── After Effects CEP plugin                 │
│   │                 (Node.js TCP server + JSX host)         │
│   │                                                         │
│   ├─ port 19878 ── Premiere Pro CEP plugin                  │
│   ├─ port 19879 ── Photoshop CEP plugin                     │
│   └─ port 19880 ── Illustrator CEP plugin                   │
└─────────────────────────────────────────────────────────────┘
```

Three consequences of this layout:

1. **Zero restart cost.** A Blender procedural script edit takes 2 to 5 seconds to re-run because the Blender process is already warm. An After Effects JSX edit is similar.
2. **Language isolation.** Python talks Python, JSX talks JSX. The wire protocol is text (JSON for Blender, raw JSX source for Adobe).
3. **Parallel work.** Claude Code can orchestrate Blender and After Effects in the same session without process contention.

### 2.2 Request lifecycle: Blender

1. User types `/bl-exec path/to/effect/main_execution.py --reload` in Claude Code
2. Claude reads the slash command definition and shells out to `./blender_cli.sh exec-script <path> --reload`
3. `blender_cli.sh` validates arguments, loads i18n strings, calls the Python bridge client
4. The Python bridge client builds `{"action": "exec_script", "path": "...", "reload": true}` and writes it to TCP 19876
5. Inside the running Blender, the `bridge-server` addon reads the JSON, reloads the target module tree, calls `main()`, and streams stdout + errors back on the same socket
6. The CLI prints the result; Claude sees it as normal command output and can reason about errors

Total roundtrip on a warm Blender: **2 to 5 seconds**, dominated by Blender's own viewport update or render.

### 2.3 Request lifecycle: After Effects

1. User types `/ae-exec adobe/ae/scripts/<project>/main_execution.jsx` in Claude Code
2. Claude reads the slash command and shells out to `./adobe_cli.sh ae exec <path>`
3. `adobe_cli.sh` calls the Python bridge client
4. Python reads the JSX file, wraps it with a response-capturing prologue and epilogue, writes it to TCP 19877
5. Inside the running After Effects, the CEP plugin receives the JSX on its Node.js TCP server, forwards it to `CSInterface.evalScript`, captures the return value, writes it back on the socket
6. The CLI receives the result; an auto-triggering skill may post-audit any error patterns

### 2.4 Why this matters for agents

An agent that can make a code edit and observe the rendered effect in under 5 seconds behaves differently from one that has to wait 30 to 60 seconds. Tight loops let Claude Code:

- Try one parameter tweak, see the Blender viewport update, try a different tweak, all in one turn
- Detect a JSX type error in the first line of stdout and fix it before moving on
- Run a render, parse the output path, pipe it into an FFmpeg step without human intervention

This is the feedback-rate advantage that makes "Claude Code as primary operator" viable, not a demo.

## 3. Pillar 1 — Blender 3D procedural rendering

### 3.1 Effect library shape

Every Blender effect in the main repo follows the same layout. This uniformity is what lets Claude Code read and write effects by pattern:

```
<effect>/
├── config.py                  # Typed parameters (colors, scale, timing, audio source)
├── i18n.py                    # Bilingual text labels (zh / en)
├── main_execution.py          # def main(): orchestrator, entry point
├── 01_objects_and_setup.py    # Scene init: clear default cube, add camera, lights
├── 02_apply_materials.py      # Shader assignment (PBR, emission, procedural nodes)
├── 03_keyframes.py            # Animation timeline driven by config
├── 04_camera.py               # Camera transforms, tracking constraints
└── *_gn.py, *_sn.py           # Geometry / Shader Nodes exported via NodeToPython
```

Each numbered module is idempotent. The orchestrator imports them in sequence and passes shared state through `config.py`.

### 3.2 Why modular, not monolithic

Three reasons, in order of importance:

1. **Partial reload matters.** Blender's Python API supports `importlib.reload(module)` to pick up edits without restarting the process. Splitting scene setup, materials, and keyframes into separate modules means editing a shader reloads only the shader module, in 1 to 2 seconds.
2. **Claude Code can target one step.** A command like "adjust the emission color" maps to editing `02_apply_materials.py` alone. One-file effects force Claude to read and re-emit the whole file for every change.
3. **Node graphs are big.** Geometry Nodes and Shader Nodes exported via NodeToPython can run into thousands of lines. Keeping them in sibling files preserves orchestrator readability.

### 3.3 The bridge-server addon

The addon runs inside the live Blender process. Its job:

- Open a TCP listener on port 19876 during Blender startup, registered as a modal operator so Blender's event loop keeps it alive
- Accept JSON requests: `exec_script`, `exec_code`, `reload_module`, `get_scene_info`, `render_frame`
- Execute requests inside Blender's main thread (all `bpy` calls are main-thread-only)
- Capture stdout, stderr, exceptions, serialize back over the same socket

Because it is an addon, not a standalone script, it has full `bpy` access and can manipulate scenes identically to a UI click.

Implementation sketch (the shipping version has more error handling, environment resolution, and bilingual logging):

```python
# bridge-server/__init__.py, simplified
import bpy, socket, threading, json, importlib, sys, io, traceback

class BridgeServerOperator(bpy.types.Operator):
    bl_idname = "bridge.server"
    bl_label = "Bridge Server"

    def execute(self, context):
        threading.Thread(target=self._serve, daemon=True).start()
        return {"FINISHED"}

    def _serve(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 19876))
        s.listen()
        while True:
            conn, _ = s.accept()
            req = json.loads(conn.recv(65536).decode())
            # dispatch req to main thread via bpy.app.timers.register
            bpy.app.timers.register(lambda: self._handle(req, conn), first_interval=0)

    def _handle(self, req, conn):
        # capture stdout, run action, return JSON response
        ...
```

The main-thread dispatch via `bpy.app.timers.register` is the non-obvious piece. Blender's Python API is not thread-safe, so the TCP listener thread cannot call `bpy` directly.

## 4. Pillar 2 — Adobe CEP + ExtendScript

### 4.1 CEP plugin layout

Adobe's Common Extensibility Platform (CEP) lets you ship an HTML + JavaScript panel that runs inside the host app (AE, Premiere, Photoshop, Illustrator), with an ExtendScript (JSX) bridge for calling into the app's DOM. The plugin in this architecture uses CEP for a non-obvious purpose: **running a Node.js TCP server inside the host app**, on a dedicated port per app.

```
bridge-cep/ae/
├── CSXS/manifest.xml          # CEP extension manifest
├── client/                    # Panel UI (minimal; bridge is invisible)
│   ├── index.html
│   ├── main.js                # CSInterface wiring + TCP server bootstrap
│   └── styles.css
├── host/                      # ExtendScript host-side glue
│   ├── host.jsx               # Polyfills, bridge bootstrap, eval entry point
│   └── lib/                   # JSON2 polyfill, shared utilities
└── package.json               # Node.js deps for the server
```

At panel startup:

1. CEP loads the HTML panel
2. The panel spins up a Node.js `net.createServer` on port 19877 (AE) / 19878 (Premiere) / etc.
3. Awaits TCP connections
4. For each JSX payload received, calls `CSInterface.evalScript` and writes the return value back on the socket

Pseudo-code for the CEP panel bootstrap:

```javascript
// client/main.js, simplified
const net = require("net");
const cs = new CSInterface();

net.createServer((socket) => {
  let buf = "";
  socket.on("data", (chunk) => { buf += chunk; });
  socket.on("end", () => {
    cs.evalScript(buf, (result) => {
      socket.write(result);
      socket.end();
    });
  });
}).listen(19877, "127.0.0.1");
```

### 4.2 Why CEP, not UXP or ScriptUI

- **ExtendScript Toolkit**: deprecated by Adobe since CC 2019
- **UXP (new)**: the stated future, but After Effects UXP scripting is still maturing in 2026 and Premiere's UXP layer lags further
- **ScriptUI dialogs**: modal, one-shot, not agent-driveable

CEP is the only path that lets an external process send JSX and read the return value reliably across all four Adobe apps in 2026.

### 4.3 Modular JSX composition pattern

A typical After Effects composition is decomposed as:

```
<project>/
├── config.jsx                 # Typed parameters
├── 00_setup.jsx               # Create project, comp, import footage
├── sc01.jsx                   # Scene 1 layers, keyframes, effects
├── sc02.jsx                   # Scene 2...
├── ...
├── sc23.jsx                   # Scene 23 (in larger comps)
├── 99_postprocess.jsx         # Final render queue, output module, export
├── i18n.jsx                   # Bilingual strings
└── main_execution.jsx         # Orchestrator: #include each sc*.jsx and run
```

Same rationale as the Blender split:

1. "Fix the title text scaling in scene 3" maps to editing `sc03.jsx` alone. ExtendScript has no module system (everything is global), so splitting by file is the only way to get scoped edits.
2. Diffs stay small.
3. Incremental execution: during iteration you can run `00_setup + sc01 + sc02` only, skipping later scenes until they are ready.

## 5. Pillar 3 — Claude Code as operator

In most Claude Code usage, Claude is a pair-programmer. Here Claude runs the show: it owns the render loop, enforces its own safety rules, drives storyboard composition from topic to final MP4 through chained slash commands. The user steers at the semantic level ("add a lower third in scene 3 with this text"); Claude translates to the right bl / ae / storyboard commands.

### 5.1 Slash commands

Slash commands are the vocabulary Claude speaks to the pipeline. Each command is a markdown file with an invocation pattern, argument schema, expected behavior, and a body Claude reads when the command fires.

Grouped by domain:

- **Blender control**: status probes, script execution with optional module reload, full restart
- **Adobe control**: status probes, JSX execution, interactive JSX REPL, full restart
- **Storyboard composition**: scaffold a storyboard from a topic, normalize structure, split long storyboards into scene-sized fragments
- **Validation and audit**: pre-flight JSX checks, self-audit for high-stakes advice, research-quality audits, narration extraction

The main repo has 34 such commands; the subset that is purely workflow-specific (domain research, resource packing, market mapping, cover composition) is part of the paid-work value and is not publicly documented.

### 5.2 Skills (auto-triggering behaviors)

Skills fire when a predicate in their `SKILL.md` frontmatter matches the current context, without the user or Claude invoking them explicitly. Examples from the main repo:

- A validator that fires before JSX is sent to After Effects, catching undeclared globals, missing `beginUndoGroup` / `endUndoGroup` pairs, unsafe `$.evalFile` paths, `app.project.activeItem` null-deref risks
- A config validator enforcing `config.jsx` shape across `sc01.jsx` through `sc23.jsx` to prevent silent drift
- A storyboard formatter normalizing structure on write or edit
- A project navigator that fires on session startup, giving Claude a tour so early turns do not waste budget on `ls` + `find`
- An error diagnostician that translates raw Blender / AE stack traces into root-cause diagnoses

### 5.3 CLAUDE.md conventions

A repo-level `CLAUDE.md` gates Claude's behavior at the session level. Conventions that matter for this kind of pipeline:

- Language match (reply in the language the user asks in)
- No auto-commit without explicit approval
- Commit message style enforced via pre-commit hooks
- Cross-reference conventions (absolute GitHub URLs when pointing at sibling repos)

Lightweight, but the difference between Claude Code behaving like a team member and behaving like a freshman.

## 6. The MCP layer (optional)

### 6.1 Two paths, same destination

There are two ways Claude Code talks to a running Blender:

**Path A, shell-out through CLI wrappers:**

```
Claude Code
  └─ /bl-exec (slash command)
       └─ ./blender_cli.sh exec-script <path>
            └─ Python bridge client → TCP 19876
                 └─ bridge-server addon handles request
```

**Path B, direct MCP tool invocation:**

```
Claude Code
  └─ blender_mcp.exec_script(path, reload=true)  (MCP tool call)
       └─ MCP server → TCP 19876
            └─ bridge-server addon handles request (same as Path A)
```

Both terminate at the same Blender addon. The difference is client-side ergonomics.

### 6.2 Why two paths exist

| Dimension | Path A (CLI) | Path B (MCP) |
| ---- | ---- | ---- |
| Setup cost | Zero, works out of the box | Install MCP server, register in Claude Code settings |
| Latency | 200 to 500 ms overhead (shell start + Python import) | 10 to 30 ms overhead (direct tool call) |
| Observability | Streams to terminal, user sees everything | Goes to Claude's context, less visible |
| Scripting | Easy to pipe between commands | One-shot tool calls, harder to chain |
| Agent preference | Good when user is co-driving | Better when Claude operates independently and latency matters |

### 6.3 MCP server sketch

What the Blender MCP server does, conceptually:

1. On startup, reads Blender host config from `.env` (host, port, WSL2 vs native Windows)
2. Opens and holds a persistent TCP connection to the `bridge-server` addon
3. Exposes tools to Claude: `exec_script`, `exec_code`, `reload_module`, `get_scene_info`, `render_frame`
4. On each tool call, serializes args to JSON, writes over TCP, deserializes the response
5. Surfaces Blender errors as MCP tool errors

The Adobe MCP server has the same shape, pointing at the CEP plugin on port 19877 and wrapping JSX evaluation.

Transport choice: MCP supports stdio, SSE, WebSocket. For local dev, stdio is the simplest (Claude Code spawns the MCP server as a subprocess and talks over pipes, no port allocation, no firewall, no TLS). Remoting to a studio render machine would swap stdio for SSE or WebSocket without changing the bridge-server or CEP plugin layer.

## 7. What would it take to reproduce this

Rough effort estimate for a competent Python engineer starting from this document, with Blender and After Effects already installed:

| Component | Effort | Notes |
| ---- | ---- | ---- |
| Blender bridge-server addon | 2 to 3 days | Socket listener, main-thread dispatch, JSON request schema |
| Blender Python bridge client + CLI | 1 day | `bl/apis/` + `blender_cli.sh` |
| First Blender procedural effect library | 2 to 4 days | Scene setup, materials, keyframes, camera, one Geometry Nodes export |
| CEP bridge plugin for one Adobe app | 3 to 5 days | CSXS manifest, Node.js TCP server, ExtendScript host glue, JSON2 polyfill |
| Adobe Python bridge client + CLI | 1 day | `adobe/apis/` + `adobe_cli.sh` |
| First AE modular composition | 2 to 3 days | config.jsx, 00_setup.jsx, sc01.jsx, main_execution.jsx |
| 5 slash commands covering core operations | 1 day | `.claude/commands/*.md` |
| 1 auto-triggering skill | 1 day | `.claude/skills/*/SKILL.md` with trigger predicate and reference rulebook |
| MCP server for one app | 2 days | Python MCP SDK, TCP wrapper, tool schema |

So roughly 15 to 25 engineer-days for a working single-app version. The production pipeline reached ~100k LOC over ~2,800 commits because it covers 11 Blender effect libraries, 4 Adobe apps, 34 slash commands, 10 skills, 2 MCP servers, WSL2/Windows environment resolution, bilingual i18n, and years of operational polish.

## 8. References

- [Official Model Context Protocol docs](https://modelcontextprotocol.io/)
- [Adobe CEP documentation](https://github.com/Adobe-CEP/CEP-Resources)
- [Blender Python API reference](https://docs.blender.org/api/current/)
- [NodeToPython addon](https://github.com/BrendanParmer/NodeToPython), used to export Geometry / Shader Nodes as Python
- [Hyperframes](https://github.com/heygen-com/hyperframes), the HTML + GSAP counterpart explored in the sibling [sapphire-studios-promo](../sapphire-studios-promo/) demo
