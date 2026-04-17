# Widgetly Cloud REST API (Synthetic)

## Authentication

All API requests must include a bearer token in the `Authorization`
header. Tokens are issued per project from the dashboard under
`Settings > API Keys`.

```
Authorization: Bearer wc_live_a1b2c3d4e5f6...
```

Tokens do not expire automatically. Revoke a token by deleting it from
the dashboard; revocation takes effect within 60 seconds.

## Endpoints

### Create Widget

```
POST /v1/widgets
Content-Type: application/json

{
  "name": "example",
  "color": "blue",
  "size": 42
}
```

Returns `201 Created` with the created widget including a server
assigned `id` and `created_at` timestamp.

### List Widgets

```
GET /v1/widgets?limit=50&cursor=<opaque>
```

Paginated with opaque cursors. Maximum `limit` is 200. Omitting
`cursor` returns the first page.

### Get Widget

```
GET /v1/widgets/{id}
```

Returns `404 Not Found` if the widget does not exist or is not
accessible to the authenticated project.

### Delete Widget

```
DELETE /v1/widgets/{id}
```

Soft-deletes the widget. Soft-deleted widgets are permanently removed
after 30 days.

## Errors

Errors use standard HTTP status codes and a JSON body:

```
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Too many requests",
    "retry_after": 12
  }
}
```

Common codes:

- `invalid_request`, 400
- `unauthorized`, 401
- `forbidden`, 403
- `not_found`, 404
- `rate_limit_exceeded`, 429
- `server_error`, 500

The `retry_after` field is only present on 429 responses and indicates
the number of seconds to wait before retrying.

## Webhooks

Register webhook endpoints under `Settings > Webhooks`. Events are
delivered with an HMAC-SHA256 signature in the `X-Widgetly-Signature`
header. The signing secret is shown once at webhook creation time.
