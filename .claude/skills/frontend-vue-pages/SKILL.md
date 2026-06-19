---
name: frontend-vue-pages
description: Create Vue 3 pages for marketplace apps using JobLogic CDN components and Identity Server authentication. Use when building the frontend of a marketplace automation.
argument-hint: <page name and description>
---

# Create a Vue Page for a Marketplace App

Scaffold a new page for: $ARGUMENTS

Marketplace app frontends use **Vue 3 + TypeScript** with the **Composition API** and reuse **JobLogic Web components** loaded from the CDN for a consistent look and feel.

---

## Step 1: Create the View Component

Create `frontend/src/views/<PageName>View.vue`:

```vue
<script setup lang="ts">
import { ref, onMounted } from "vue";
import { apiFetch } from "../api";

// Define TypeScript interface for the data
interface MyItem {
  id: number;
  name: string;
  status: string;
}

// Reactive state
const items = ref<MyItem[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);

// Fetch data from the API (auth headers added automatically)
async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    items.value = await apiFetch<MyItem[]>("/automations/<name>/data");
  } catch (e) {
    error.value = e instanceof Error ? e.message : "Unknown error";
  } finally {
    loading.value = false;
  }
}

onMounted(loadData);
</script>

<template>
  <div class="page">
    <h2>Page Title</h2>

    <p v-if="loading">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>

    <div v-else>
      <!-- Use JobLogic CDN components where available -->
      <table class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td>{{ item.id }}</td>
            <td>{{ item.name }}</td>
            <td>{{ item.status }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page {
  padding: 1rem;
}
.error {
  color: red;
}
</style>
```

---

## Step 2: Add Router Entry

Add the route in `frontend/src/main.ts`:

```typescript
{
  path: '/<page-path>',
  name: '<page-name>',
  component: () => import('./views/<PageName>View.vue'),
  meta: { requiresAuth: true },
}
```

The `requiresAuth: true` meta ensures the auth guard redirects to JobLogic IDP login if not authenticated.

---

## Step 3: Add Navigation

Add a link in `frontend/src/App.vue`:

```vue
<nav>
  <RouterLink to="/">Home</RouterLink>
  <RouterLink to="/<page-path>">Page Name</RouterLink>
</nav>
```

---

## Step 4: API Integration

Use the `apiFetch` wrapper from `frontend/src/api.ts` which automatically includes:

- `Authorization: Bearer <token>` from the IDP
- `X-Tenant-Id: <tenant-id>` extracted from the JWT claims

```typescript
import { apiFetch } from "../api";

// GET request
const data = await apiFetch<MyItem[]>("/automations/<name>/items");

// POST request
const result = await apiFetch<{ success: boolean }>(
  "/automations/<name>/action",
  {
    method: "POST",
    body: JSON.stringify({ itemId: 123 }),
  },
);
```

---

## JobLogic CDN Components

JobLogic Web components are loaded from `https://cdn.joblogic.com/` and available as custom HTML elements in Vue templates.

### Setup in `index.html`

```html
<head>
  <link
    rel="stylesheet"
    href="https://cdn.joblogic.com/components/styles.css"
  />
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
  <script src="https://cdn.joblogic.com/components/bundle.js"></script>
</body>
```

> **Note:** Exact CDN URLs are managed internally and will be provided by the JobLogic team.

### Using Components

Once loaded, JobLogic components are available as custom elements:

```vue
<template>
  <!-- JobLogic page header -->
  <jl-page-header title="My Automation" />

  <!-- JobLogic data table -->
  <jl-data-table :columns="columns" :rows="rows" />

  <!-- JobLogic buttons -->
  <jl-button variant="primary" @click="save">Save</jl-button>
  <jl-button variant="secondary" @click="cancel">Cancel</jl-button>

  <!-- JobLogic form elements -->
  <jl-input v-model="formData.name" label="Name" />
  <jl-select
    v-model="formData.status"
    :options="statusOptions"
    label="Status"
  />
</template>
```

### Registering Custom Elements in Vue

To avoid Vue warnings about unknown custom elements, add to `vite.config.ts`:

```typescript
export default defineConfig({
  plugins: [
    vue({
      template: {
        compilerOptions: {
          isCustomElement: (tag) => tag.startsWith("jl-"),
        },
      },
    }),
  ],
});
```

---

## Styling & Look-and-Feel

- Use JobLogic CDN component classes to match the existing UI
- For custom styling, use `<style scoped>` to avoid CSS leaks
- Stick to the JobLogic colour palette and spacing conventions
- When JobLogic components aren't available for a UI element, use standard HTML with Bootstrap-compatible classes (JobLogic uses Bootstrap internally)

---

## Conventions

- Always use `<script setup lang="ts">` (Composition API)
- Use `ref()` and `reactive()` for state management
- Lazy-load views: `component: () => import('./views/XView.vue')` in the router
- Use scoped styles: `<style scoped>`
- Define TypeScript interfaces for API responses — no `any` types
- File naming: `<PageName>View.vue` for views, `<ComponentName>.vue` for components in `src/components/`
- API calls always go through `apiFetch()` which handles auth automatically

---

## Checklist

- [ ] View component created with `<script setup lang="ts">`
- [ ] TypeScript interfaces defined for data models
- [ ] Route registered in `main.ts` with `meta: { requiresAuth: true }`
- [ ] Navigation link added in `App.vue`
- [ ] API calls use `apiFetch()` wrapper (includes auth headers)
- [ ] JobLogic CDN components used where applicable
- [ ] `jl-` custom element prefix registered in `vite.config.ts`
- [ ] Scoped styles used — no CSS leaks
- [ ] No `any` types — proper TypeScript interfaces
