---
paths:
  - "frontend/**"
---

# Frontend Development Rules

- **Framework**: Vue 3 with TypeScript and Vite
- **Always use `<script setup lang="ts">`** (Composition API, not Options API)
- **State management**: Use `ref()` and `reactive()` from Vue
- **Routing**: Lazy-load views with `() => import(...)` in the router. Protected routes use `meta: { requiresAuth: true }`.
- **API calls**: Use `apiFetch()` from `src/api.ts` which includes `Authorization` and `X-Tenant-Id` headers automatically. Calls go to `/api/...` — Vite proxies to the backend on port 8000.
- **Authentication**: Marketplace apps use `oidc-client-ts` for OAuth2 Authorization Code + PKCE via JobLogic Identity Server. Auth service lives in `src/auth.ts`.
- **JobLogic CDN components**: Load CSS/JS from `https://cdn.joblogic.com/` in `index.html`. Use `jl-` prefixed custom elements in templates. Register the `jl-` prefix as custom elements in `vite.config.ts`.
- **iframe embedding**: If the app is embedded in `go.joblogic.com`, use `postMessage` for parent-child communication. Only accept messages from `https://go.joblogic.com`.
- **Styles**: Use `<style scoped>` to avoid CSS leaks
- **File naming**: `<PageName>View.vue` for views in `src/views/`, `<ComponentName>.vue` for components in `src/components/`
- **Types**: Define TypeScript interfaces for API responses
- **No `any` types**: Use proper typed interfaces — avoid `any` where possible
