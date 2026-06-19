# JavaScript Injection Guide

## Overview

JavaScript-injected automations add custom components to existing pages on `go.joblogic.com` by hosting a JS file on the JobLogic CDN. When a customer loads the target page, the script runs and injects the component into the DOM.

## How It Works

1. A JavaScript file is authored and uploaded to `https://cdn.joblogic.com/`
2. JobLogic Web loads the script on the relevant page
3. The script inspects the current URL, and if it matches the target page, injects the custom component
4. The component calls a backend API (your automation endpoint) for data and user actions

## Development Workflow

### 1. Page Inspection with Playwright MCP

The **Playwright MCP** is a dev-time tool available to the AI agent. It is used to inspect `go.joblogic.com` pages and understand the DOM structure — it is **not** a code dependency.

The AI agent uses Playwright MCP to:
- Navigate to `go.joblogic.com/<target-page>`
- Wait for the page to fully load
- Snapshot the DOM structure of the area where the component should be injected
- Take screenshots for visual reference

Additionally, the **Chrome DevTools MCP** can be used to inspect network requests, CSS, and existing JavaScript on the page.

From the inspection, identify:
- The **parent selector** (where to inject)
- The **injection method** (`appendChild`, `insertBefore`, `insertAdjacentHTML`)
- **Existing IDs/classes** to avoid conflicts
- The **URL pattern** to scope the injection

### 2. JavaScript Authoring

Write a vanilla JS file using the IIFE (Immediately Invoked Function Expression) pattern:

```javascript
(function () {
  "use strict";

  // Only run on the target page
  if (!window.location.pathname.includes("<target-path>")) return;

  var API_BASE = "<your-api-url>/api/automations/<name>";

  function waitForElement(selector, callback) {
    var el = document.querySelector(selector);
    if (el) { callback(el); return; }
    var observer = new MutationObserver(function (_, obs) {
      el = document.querySelector(selector);
      if (el) { obs.disconnect(); callback(el); }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  function injectComponent(parent) {
    var container = document.createElement("div");
    container.id = "jl-<automation-name>";
    container.innerHTML = '<div class="panel panel-default">...</div>';
    parent.appendChild(container);
    loadData();
  }

  function loadData() {
    fetch(API_BASE + "/data")
      .then(function (r) { return r.json(); })
      .then(function (data) { /* render data */ })
      .catch(function (err) { console.error("[<name>]", err); });
  }

  waitForElement("<parent-selector>", injectComponent);
})();
```

**Key conventions:**
- Always use IIFE — no global scope pollution
- Vanilla JavaScript only — no frameworks
- Check the page URL before injecting
- Use `MutationObserver`-based `waitForElement` for async DOM readiness
- Use `fetch()` for API calls to the backend
- Match existing JobLogic CSS classes (`panel`, `btn`, `table`, etc.)

### 3. CDN Upload

The JavaScript file is uploaded to `https://cdn.joblogic.com/` **manually**. Coordinate with the DevOps / platform team for the upload.

### 4. Backend Endpoint

The injected JS calls a FastAPI backend endpoint. This follows the same pattern as a webhook automation:

- Create `backend/routes/<automation_name>.py` with route handlers
- The backend uses `JicroClient` for Joblogic service calls
- Tenant ID from env var `TENANT_ID` (single-tenant)
- CORS must be configured to allow `https://go.joblogic.com`

### 5. Testing

Use the **Playwright MCP** to test the injection by evaluating the JS code on the target page and taking a screenshot to verify it renders correctly. Use **Chrome DevTools MCP** to check that API calls to the backend succeed.

Test the backend endpoints separately via Swagger UI at `http://localhost:8000/docs`.

## CORS

Since the injected JS runs on `go.joblogic.com` but calls your API on a different domain, CORS headers are required. Add `https://go.joblogic.com` to the allowed origins in `backend/main.py`.

## File Organization

```
├── js/                         # JavaScript files for CDN upload
│   └── <automation-name>.js
├── backend/routes/             # Backend API endpoints
│   └── <automation_name>.py
```
