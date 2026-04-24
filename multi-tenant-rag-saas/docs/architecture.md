# Architecture

## 1. Service boundaries

Three independent services behind a single reverse proxy.

| Service | Port | Responsibilities |
|---|---|---|
| `app` (core) | 8001 | Chat endpoints, RAG retrieval, JWT auth, SocketIO streaming integrated |
| `admin` | 8002 | Tenant + user + role management, token usage tracking, billing, document ingestion, embedding tracker |
| `ws` | 8003 | Plain WebSocket service for real-time events (notifications, presence) |

Services share a `share/` package with SQLAlchemy models, DB session
factory, and Redis client. They communicate with each other over
internal HTTP APIs (`app` to `admin` for token accounting), not
shared in-process state.

## 2. Request lifecycle: chat with RAG

1. Client opens WebSocket to `/ws/chat`, sends a user message.
2. `app` service authenticates the JWT, pulls `tenant_id` and
   `user_id` from claims, loads conversation history from Redis
   and Postgres.
3. `app` queries pgvector in the tenant's namespace, top-k with
   metadata filter `{tenant_id: <id>}`. Cosine similarity,
   `top_k=8`, optional re-ranker pass.
4. `app` builds the prompt, streams LLM completion via OpenAI or
   Anthropic SDK, yields tokens back on the WebSocket as they land.
5. On stream close, `app` POSTs
   `{tenant_id, user_id, model, input_tokens, output_tokens}`
   to `admin` at `/api/v1/internal/token-usage`, async,
   non-blocking.
6. `admin` records the usage row, updates per-tenant rollups,
   enforces the tenant's billing model: hard-cap if monthly_limit
   exceeded, debit balance if prepaid, accrue cost if pay-per-use.

## 3. RAG ingestion

Documents uploaded to `admin`, chunked (paragraph-aware, overlap),
embedded via OpenAI `text-embedding-3-small` (or swappable via
config), stored in pgvector with
`{tenant_id, doc_id, chunk_idx, source}` metadata. Embedding token
usage is tracked in the same `token_usage` table, tagged
`op=embed`.

## 4. Permission model

Three effective roles, enforced as a middleware at the router layer.

- `super_admin`: `is_system_user=True`, sees all tenants, used for
  platform operations only.
- `tenant_admin`: scoped by `tenant_id`, manages users, billing,
  and documents inside their tenant.
- `user`: scoped by `tenant_id`, can chat and manage their own
  sessions and documents.

Routes declare required role via a FastAPI dependency. Cross-tenant
reads are rejected at the DB session layer, not just at the router,
so mistakes at the application layer cannot bleed data.

## 5. Infra notes

- Dev: direct connections to OpenAI / Anthropic, single
  docker-compose stack for Postgres + Redis + three services +
  frontend.
- Prod in regions where the OpenAI API is geo-blocked: a sidecar
  HTTP proxy in a companion compose stack exposes
  `http://vpn-proxy:8118`. The `app` service reads `OPENAI_PROXY`
  env and routes the LLM SDK through it. Dev has
  `PROXY_ENABLED=false`.
