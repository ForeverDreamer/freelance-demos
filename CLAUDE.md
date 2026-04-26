# CLAUDE.md

Guidance for Claude Code when working inside `freelance-demos`.

## Repo scope

Public monorepo of capability demos backing the Upwork profile at
<https://www.upwork.com/freelancers/~0140562708001afd27>. Each subdirectory
is a self-contained demo with its own `README.md`, tests, and MIT license.

Operational metadata, case files, bidding playbooks, and Claude tooling
for bidding workflows live in the private sibling repo `freelance-ops`,
not here. This repo holds **only** the public demo code that prospective
Upwork clients can see and run.

## Repo conventions

- Each demo subdirectory is fully self-contained: own `README.md`,
  dependency manifest, `tests/`, and runnable entry point. No
  cross-subdirectory imports.
- Sample data under `sample_data/` is synthetic only. No real client data.
- Demos publish 60-70% of the full paid scope. The gap is documented
  in a `## What this demo does NOT do` (or equivalent) section in the
  subdirectory `README.md`.
- Python demos use [uv](https://docs.astral.sh/uv/) for dependency
  management.

## Upwork profile link is mandatory in every README

**Rule**: every subdirectory `README.md`, plus the root `README.md`,
must contain a `## Custom builds` section (or equivalent contact section
when the demo is a one-off submission rather than a generic capability
demo) that links to:

```
https://www.upwork.com/freelancers/~0140562708001afd27
```

**Why**: this repo exists to drive Upwork lead conversion. A subdirectory
README without the contact link breaks the funnel for any visitor who
landed there directly (search, GitHub topic browsing, deep link from a
cover letter).

**Pattern** (copy from [`file-organizer/README.md`](file-organizer/README.md)
lines 162-165):

```markdown
## Custom builds

For your specific project, folder map, rule set, production deployment,
or ongoing maintenance, reach out on Upwork: <https://www.upwork.com/freelancers/~0140562708001afd27>

## License

MIT. Fork, read, learn freely.
```

Place the `## Custom builds` section immediately before `## License`. If
the demo is a one-off submission for a specific client (e.g.
`sapphire-studios-promo`), keep the section but reframe the wording
toward extensions of that specific brief, still linking the same URL.

## When scaffolding a new demo subdirectory

Reuse the structure of an existing subdirectory like `file-organizer/`:

1. `README.md` with sections: intro paragraph, Why this is interesting,
   How to run, What this demo does NOT do, **Custom builds (with the
   Upwork URL above)**, License.
2. `pyproject.toml` for Python demos (uv-managed) or equivalent manifest.
3. `tests/` and a runnable entry point.
4. Add a row for the new subdirectory to the root `README.md` Demos
   table.
5. Verify the new subdirectory `README.md` contains the Upwork profile
   URL before declaring the scaffold done. This check is part of the
   scaffold contract, not optional.

## General rules inherited from `freelance-ops`

- Never auto-commit. Wait for the user's explicit `提交修改` /
  `commit and push` before running `git commit` or `git push`.
- Reply in the language the user asks in.
- No em dashes (`—`) in markdown body. Use commas or periods instead.
