# multi-tenant-rag-saas

A public architecture sketch of a multi-tenant Retrieval-Augmented
chat SaaS: three-service FastAPI backend, Next.js 15 dual frontend,
PostgreSQL + pgvector for vectors, Redis for sessions, real-time
streaming over WebSocket / Socket.IO, and LLM token accounting with
three billing models.

Subdirectory of [freelance-demos](https://github.com/ForeverDreamer/freelance-demos).
Reference architecture for "build me a ChatGPT for my customers"
briefs on Upwork.

## Why this is interesting

Most "chat over your docs" demos stop at a single-user CLI or a
single-tenant toy. Production SaaS briefs need three things those
demos skip.

- **Tenant isolation with a clean permission model**: super_admin
  (system) / tenant_admin (per-customer) / user (end-user), so an
  agency can resell the platform without cross-tenant data bleed.
- **LLM cost accounting at request level**: every chat call records
  input + output tokens per tenant + user + model, with three billing
  modes (pay-per-use, prepaid balance, monthly cap).
- **A real vector store**: pgvector + LangChain, not a flat JSON file.
  Metadata filters enforce tenant scope on every query.

See `docs/architecture.md` for the full data flow and
`src/admin/services/token_tracker.py` for the token-accounting shape.

## What this sketch shows

| Capability | Where |
|---|---|
| Microservice boundaries (app / admin / ws) | `src/app/main.py`, `src/admin/main.py`, `src/ws/main.py` |
| Three-tier RBAC | `src/share/models.py` (`User.effective_role`) |
| LLM token tracker with async HTTP reporting | `src/admin/services/token_tracker.py` |
| pgvector-backed RAG pipeline | `docs/architecture.md` §3 |
| Next.js 15 chat UI with streaming | `src/frontend/app/chat/page.tsx` |
| Three billing models | `src/admin/main.py` billing router |

## What this sketch does NOT include

This is a capability sketch, not a deployable system. The stubs
under `src/` are skeletons with `TODO: see private repo` markers.
A full paid delivery adds.

- Working Alembic migrations with real schemas (tenants, users,
  conversations, messages, token_usage, billing_accounts)
- Production Docker Compose with an optional HTTP proxy sidecar for
  regions where the OpenAI API is geo-blocked
- Complete admin panel (user management, billing dashboards,
  document ingestion UI, usage analytics per tenant)
- Document loaders for DOCX / XLSX / HTML / Confluence / Google Drive
- Streaming with backpressure, retry, and partial-response recovery
- Stripe / LemonSqueezy payment integration on top of the three
  billing models
- Audit logs, rate limits per tenant plan, abuse detection
- Observability: token cost dashboards, retrieval quality traces,
  latency SLOs per service

If any of those matter for your project, that is the paid work.

## Stack

Backend: FastAPI, SQLAlchemy, Alembic, PostgreSQL + pgvector, Redis,
LangChain, OpenAI + Anthropic providers, python-socketio, WebSockets.

Frontend: Next.js 15 (App Router, Turbopack), React 19, TypeScript,
Tailwind CSS 4, Shadcn UI + Radix, Redux Toolkit, React Query,
socket.io-client.

Infra: Docker Compose, Alembic migrations, JWT auth, environment-based
proxy switching (direct in dev, HTTP proxy in regions where the
OpenAI API is blocked).

## License

MIT. Fork, read, learn freely.

## Custom builds

For your own tenant model, billing rules, embedding provider,
deployment target, or corpus ingestion, reach out on Upwork: <https://www.upwork.com/freelancers/~0140562708001afd27>
