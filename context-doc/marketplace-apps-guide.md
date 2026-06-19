# Marketplace Apps Guide

## Overview

Marketplace apps are standalone applications with a Vue 3 frontend and FastAPI backend, authenticated via the **JobLogic Identity Server**. They can run standalone or be **embedded as iframes** inside `go.joblogic.com`.

Unlike backend and JS-injected automations (which are single-tenant), marketplace apps are **multi-tenant** — the tenant ID comes from the IDP JWT token after user login.

## Architecture

```
[Vue 3 Frontend :5173] → [FastAPI Backend :8000] → [Joblogic exec-jicro]
          ↓
  [JobLogic IDP (developer.joblogic.com)]
```

## Authentication: OAuth2 Authorization Code + PKCE

### 1. Register on developer.joblogic.com

Go to `https://developer.joblogic.com` and fill out the application registration form. You receive:
- **Client ID** — used by the Vue frontend
- **Authority URL** — the JobLogic Identity Server base URL

### 2. Frontend Auth Setup

Use `oidc-client-ts` for the OAuth2 flow:

```bash
cd frontend && npm install oidc-client-ts
```

Create `frontend/src/auth.ts` with:
- `UserManager` configured with `response_type: 'code'` (Authorization Code + PKCE)
- `signinRedirect()` / `signinRedirectCallback()` for login flow
- Helper to extract `tenant_id` from JWT claims

### 3. Route Guard

Add `meta: { requiresAuth: true }` to protected routes and implement a `beforeEach` guard that checks for a valid user session.

### 4. API Calls

Use the `apiFetch()` wrapper in `frontend/src/api.ts` which automatically includes:
- `Authorization: Bearer <token>` from the IDP
- `X-Tenant-Id: <tenant-id>` extracted from JWT claims

### 5. Backend JWT Validation

The FastAPI backend validates the JWT token and extracts the tenant ID using `get_tenant_id` from the SDK:

```python
from joblogic_sdk.auth import get_tenant_id

# Use as a FastAPI dependency:
@router.get("/data")
async def get_data(tenant_id: str = Depends(get_tenant_id)):
    # tenant_id is extracted from the X-Tenant-Id header
    ...
```

## JobLogic CDN Components

Marketplace apps reuse JobLogic Web components from `https://cdn.joblogic.com/` for consistent UI.

### Setup

Include CSS and JS in `frontend/index.html`:

```html
<link rel="stylesheet" href="https://cdn.joblogic.com/components/styles.css" />
<script src="https://cdn.joblogic.com/components/bundle.js"></script>
```

> **Note:** Exact CDN URLs are managed internally and will be provided by the team.

### Vue Integration

Register the `jl-` prefix as custom elements in `vite.config.ts`:

```typescript
vue({
  template: {
    compilerOptions: {
      isCustomElement: (tag) => tag.startsWith('jl-'),
    },
  },
})
```

Then use them in templates:

```vue
<jl-page-header title="My App" />
<jl-data-table :columns="columns" :rows="rows" />
<jl-button variant="primary" @click="save">Save</jl-button>
```

## iframe Embedding

Marketplace apps can be embedded inside `go.joblogic.com` as iframes.

### Server-side headers

Add CSP headers in `backend/main.py`:

```python
response.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://go.joblogic.com"
```

### Parent-child communication

Use `postMessage` for communication between the iframe and the parent JobLogic page:

```typescript
// Send to parent
window.parent.postMessage({ type: 'event', data: {} }, 'https://go.joblogic.com')

// Listen from parent
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://go.joblogic.com') return
  // Handle message
})
```

## Environment Variables

```env
# Frontend (.env)
VITE_IDP_AUTHORITY=<authority-url>
VITE_IDP_CLIENT_ID=<client-id>
VITE_IDP_REDIRECT_URI=http://localhost:5173/callback
VITE_IDP_SCOPES=openid profile

# Backend (.env)
IDP_CLIENT_ID=<client-id>
IDP_AUTHORITY=<authority-url>
```
