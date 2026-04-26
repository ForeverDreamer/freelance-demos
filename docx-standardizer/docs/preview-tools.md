# Previewing .docx files in VS Code

Two complementary extensions cover the two questions you actually ask
when working on this pipeline:

> 1. "Does this file *look* right?"
> 2. "Is this file *structurally* right?"

| Extension | Renderer | Strength | Use it to answer |
|---|---|---|---|
| [Office Viewer](https://marketplace.visualstudio.com/items?itemName=cweijan.vscode-office) (`cweijan.vscode-office`) | [docxjs](https://github.com/VolodymyrBaydalka/docxjs) | Visual fidelity — mimics Word's rendering | "Does this file *look* right?" |
| [Docx/ODT Viewer](https://marketplace.visualstudio.com/items?itemName=ShahilKumar.docxreader) (`shahilkumar.docxreader`) | [Mammoth.js](https://github.com/mwilliamson/mammoth.js) | Semantic fidelity — only emits `<h1>`/`<h2>` for actual Heading styles | "Is this file *structurally* right?" |

Both are webview-only (no native deps), Remote-WSL compatible, free.

## Why both, not one

docxjs reproduces what a reader *sees* — font sizes, weights, layout —
even when the source document used hand-rolled formatting instead of
proper styles. That is what your end users care about.

Mammoth.js refuses to fake structure. It only promotes a paragraph to
`<h1>` if the source applied the **Heading 1** style. If the author
just made the title big and bold, Mammoth renders it as a `<p>` and
the outline pane shows **No headings found**.

For a project whose whole purpose is to rebuild documents with
consistent `Title` / `Heading 1` / `Heading 2` / `Normal` / `Table Grid`
styles from `master.docx`, that "refusal" is the most useful signal
either tool gives you.

## Workflow

**On `input/*.docx` — pre-pipeline lint:**

Open with Docx Reader. If the outline is empty or sparse, the source
document is exactly the kind of unstructured input this pipeline is
designed to fix — confirms the work is needed, and tells you which
sections the LLM step has to reconstruct from prose.

**On `output/*.docx` — post-pipeline verification:**

Open with Docx Reader. Outline should now list every section name
defined in `schema.py`'s `StandardizedDocument`. If a section is
missing from the outline, `rebuild.py` did not apply the style
correctly — that is a bug, not a content issue.

Open the same file with Office Viewer to confirm the result also looks
acceptable to a human reader (font hierarchy, table grid lines,
spacing).

## Switching between viewers

VS Code shows the picker on first open. To switch later:

1. With the file open, `Ctrl+Shift+P` → **Reopen Editor With...**
2. Pick the other viewer

Office Viewer is the wins-by-default choice (alphabetically earlier
viewType among two `priority: default` registrations). Leave it that
way; reach for Docx Reader specifically when you want the structural
check.

## Installation

Both are in the workspace extensions list at
`video_creation_x/.vscode/extensions.list`. Run
`video_creation_x/.vscode/sync-extensions.sh` to install.

Or one-off:

```bash
code --install-extension cweijan.vscode-office
code --install-extension shahilkumar.docxreader
```
