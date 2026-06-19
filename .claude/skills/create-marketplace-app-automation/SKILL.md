---
name: create-marketplace-app-automation
description: Create a marketplace application with a Vue 3 frontend, FastAPI backend, and JobLogic Identity Server authentication. Use for standalone apps that can be embedded in JobLogic via iframe.
argument-hint: <description of the marketplace app>
---

# Create a Marketplace App Automation

Build a marketplace application for: $ARGUMENTS

Marketplace apps are **standalone applications** with:

- **Vue 3 + TypeScript** frontend (port 5173)
- **FastAPI** backend (port 8000)
- **JobLogic Identity Server** authentication (OAuth2 Authorization Code + PKCE)
- **Multi-tenant** — tenant ID comes from the IDP token after user login

These apps can be **embedded as iframes** inside `go.joblogic.com` or run standalone.

---

## Step 1: Register on developer.joblogic.com

Before writing code, register the application:

1. Go to `https://developer.joblogic.com`
2. Fill out the application registration form with:
   - **Application name**
   - **Redirect URI**: `http://localhost:5173/callback` (dev) and the production URL
   - **Scopes**: as required by the app
3. You will receive:
   - `client_id`
   - `authority` URL (JobLogic Identity Server)
4. Store these in `.env`:

```env
IDP_CLIENT_ID=<your-client-id>
IDP_AUTHORITY=<authority-url>
IDP_REDIRECT_URI=http://localhost:5173/callback
IDP_SCOPES=openid profile
```

---

## Step 2: Frontend — Vue 3 with OAuth2 PKCE

### 2a. Install auth dependencies

```bash
cd frontend && npm install oidc-client-ts
```

### 2b. Create auth service

Create `frontend/src/auth.ts`:

```typescript
import { UserManager, WebStorageStateStore } from "oidc-client-ts";

const settings = {
  authority: import.meta.env.VITE_IDP_AUTHORITY,
  client_id: import.meta.env.VITE_IDP_CLIENT_ID,
  redirect_uri: import.meta.env.VITE_IDP_REDIRECT_URI,
  response_type: "code",
  scope: import.meta.env.VITE_IDP_SCOPES || "openid profile",
  userStore: new WebStorageStateStore({ store: window.sessionStorage }),
};

export const userManager = new UserManager(settings);

export async function getUser() {
  return await userManager.getUser();
}

export async function login() {
  await userManager.signinRedirect();
}

export async function handleCallback() {
  return await userManager.signinRedirectCallback();
}

export async function logout() {
  await userManager.signoutRedirect();
}

export async function getAccessToken(): Promise<string | null> {
  const user = await getUser();
  return user?.access_token ?? null;
}

export function getTenantId(user: any): string {
  // Extract tenant_id from the JWT claims
  return user?.profile?.tenant_id ?? "";
}
```

### 2c. Add Vite env variables

Create `frontend/.env`:

```env
VITE_IDP_AUTHORITY=<authority-url>
VITE_IDP_CLIENT_ID=<client-id>
VITE_IDP_REDIRECT_URI=http://localhost:5173/callback
VITE_IDP_SCOPES=openid profile
```

### 2d. Create callback view

Create `frontend/src/views/CallbackView.vue`:

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { handleCallback } from "../auth";

const router = useRouter();
const error = ref<string | null>(null);

onMounted(async () => {
  try {
    await handleCallback();
    router.push("/");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Authentication failed";
  }
});
</script>

<template>
  <div>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-else>Completing sign-in…</p>
  </div>
</template>

<style scoped>
.error {
  color: red;
}
</style>
```

### 2e. Add route guard and callback route

Update `frontend/src/main.ts`:

```typescript
import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import { getUser, login } from "./auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "home",
      component: () => import("./views/HomeView.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/callback",
      name: "callback",
      component: () => import("./views/CallbackView.vue"),
    },
  ],
});

// Auth guard — redirect to IDP login if not authenticated
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth) {
    const user = await getUser();
    if (!user || user.expired) {
      await login();
      return false;
    }
  }
});

const app = createApp(App);
app.use(router);
app.mount("#app");
```

### 2f. Use auth in API calls

Create a typed fetch wrapper in `frontend/src/api.ts`:

```typescript
import { getAccessToken, getUser, getTenantId } from "./auth";

const API_BASE = "/api";

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = await getAccessToken();
  const user = await getUser();
  const tenantId = user ? getTenantId(user) : "";

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      "X-Tenant-Id": tenantId,
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }

  return response.json();
}
```

---

## Step 3: Frontend — JobLogic CDN Components

Marketplace apps reuse **JobLogic Web components** loaded from the CDN to keep a consistent look and feel.

### 3a. Include CDN links in `index.html`

```html
<head>
  <!-- JobLogic component styles -->
  <link
    rel="stylesheet"
    href="https://cdn.joblogic.com/components/styles.css"
  />
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
  <!-- JobLogic component scripts -->
  <script src="https://cdn.joblogic.com/components/bundle.js"></script>
</body>
```

> **Note:** Exact CDN URLs will be provided by the JobLogic team. The above are placeholders.

### 3b. Use JobLogic components in Vue

JobLogic components are available as custom HTML elements once the CDN script is loaded. Use them directly in Vue templates:

```vue
<template>
  <jl-page-header title="My Automation" />
  <jl-data-table :columns="columns" :rows="rows" />
  <jl-button variant="primary" @click="handleAction">Run Action</jl-button>
</template>
```

---

## Step 4: Backend — JWT Token Validation

### 4a. Token validation and tenant extraction

Use `get_tenant_id` from `joblogic_sdk.auth`:

```python
from joblogic_sdk.auth import get_tenant_id
```

This extracts the tenant ID from the `X-Tenant-Id` header (set by the frontend) and raises an `HTTPException` if the header is missing.

### 4b. Create routes with tenant extraction

```python
from fastapi import APIRouter, Depends, HTTPException, Request
from joblogic_sdk.jicro import JicroClient, JicroError
from joblogic_sdk.auth import get_tenant_id

router = APIRouter(prefix="/automations/<name>", tags=["<name>"])


@router.get("/data")
async def get_data(request: Request):
    tenant_id = get_tenant_id(request)
    try:
        async with JicroClient() as client:
            result = await client.execute(
                tenant_id=tenant_id,
                service_name="<service>",
                message_signature="<MessageMsg>",
                payload={},
            )
            return result
    except JicroError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
```

---

## Step 5: Register the Route in `backend/main.py`

```python
from backend.routes.<automation_name> import router as <name>_router
app.include_router(<name>_router, prefix="/api")
```

---

## Step 6: iframe Embedding

Marketplace apps can be embedded in `go.joblogic.com` via iframe.

### 6a. Configure CSP / frame headers

In `backend/main.py`, allow framing from JobLogic:

```python
from fastapi.middleware.trustedhost import TrustedHostMiddleware

@app.middleware("http")
async def add_frame_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "ALLOW-FROM https://go.joblogic.com"
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self' https://go.joblogic.com"
    return response
```

### 6b. Parent-iframe communication (if needed)

```typescript
// In the Vue app — send messages to the parent JobLogic page
window.parent.postMessage(
  { type: "automation-ready", data: {} },
  "https://go.joblogic.com",
);

// Listen for messages from the parent
window.addEventListener("message", (event) => {
  if (event.origin !== "https://go.joblogic.com") return;
  // Handle messages from JobLogic
});
```

---

## Checklist

- [ ] App registered on `developer.joblogic.com` — have `client_id` and `authority`
- [ ] Frontend: `oidc-client-ts` installed, auth service created
- [ ] Frontend: Callback view + route guard implemented
- [ ] Frontend: API fetch wrapper includes `Authorization` + `X-Tenant-Id` headers
- [ ] Frontend: JobLogic CDN components included in `index.html`
- [ ] Backend: JWT token validation middleware
- [ ] Backend: Routes extract tenant ID from headers (multi-tenant)
- [ ] CORS configured for the app domain AND `go.joblogic.com`
- [ ] iframe headers set if embedding is required
- [ ] Used MCP tools for Jicro message discovery
- [ ] Used `JicroClient` for all Joblogic calls
- [ ] Added notification decorator and audit logging
- [ ] Tested via Swagger UI and browser
