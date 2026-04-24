# Stack

## Backend

| Layer | Choice | Why |
|---|---|---|
| Web framework | FastAPI | Async-first, dependency injection for RBAC middleware, OpenAPI out of the box |
| ORM | SQLAlchemy 2.x | Mature relationship model, async support matches FastAPI |
| Migrations | Alembic | Schema versioning tied to SQLAlchemy metadata, production-safe up/down |
| Primary DB | PostgreSQL 16 + pgvector | One database for relational + vector, metadata filters in SQL, no separate vector service to run |
| Cache | Redis | Session store, conversation scratchpad, per-tenant rollups for billing |
| RAG | LangChain | Loader / splitter / retriever abstractions that are actually needed, not a framework-for-the-sake-of-it |
| LLM providers | OpenAI + Anthropic | Dual provider so tenants can pick by cost, latency, or capability |
| Realtime | python-socketio + websockets | SocketIO for chat streaming in `app`, raw WebSocket service for plain events in `ws` |

## Frontend

| Layer | Choice | Why |
|---|---|---|
| Framework | Next.js 15 App Router | Server components for SEO-visible pages, client islands for the chat UI |
| Bundler | Turbopack | Faster cold start than webpack during dev, default in Next 15 |
| UI primitives | Shadcn UI + Radix | Accessible, unstyled, owned in-repo, no runtime lock-in |
| Styling | Tailwind CSS 4 | Utility-first, matches Shadcn defaults |
| State | Redux Toolkit + React Query | RTK for long-lived UI state, React Query for server data with cache + invalidation |
| Realtime client | socket.io-client | Pairs with python-socketio on the backend |

## Infra

| Layer | Choice | Why |
|---|---|---|
| Containers | Docker Compose | Local dev + single-host prod, three services wired via internal DNS |
| Auth | JWT | Stateless, tenant_id + role encoded in claims, short-lived access token + refresh |
| Observability | Logging (structured JSON) + per-service health endpoints | Simple baseline, no vendor lock |
| Proxy | Optional HTTP proxy sidecar | Only in deployment regions where the OpenAI API is geo-blocked, disabled in dev |

## Three billing models, explicit tradeoffs

| Model | Hard cap? | Upfront cash? | Typical buyer |
|---|---|---|---|
| `pay_per_use` | no | no | B2B SaaS, billed monthly off accrued cost |
| `prepaid` | yes (balance hits zero) | yes | Self-serve tiers, controls blast radius of runaway scripts |
| `monthly_limit` | yes (reset monthly) | no | Internal platforms with fixed budget per tenant |

All three share one `token_usage` ledger. The billing model is a
property of the tenant record, not a separate code path.
