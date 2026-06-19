---
name: create-js-injected-automation
description: Create a JavaScript-injected automation that adds custom components to JobLogic Web pages. Covers page inspection via Playwright MCP, JS file authoring, and the backend API endpoint.
argument-hint: <description of the component or feature to inject and which JobLogic page>
---

# Create a JavaScript-Injected Automation

Build a JS-injected automation for: $ARGUMENTS

JS-injected automations add **custom UI components** to existing pages on `go.joblogic.com`. The workflow is:

1. **Inspect** the target page using the **Playwright MCP** to understand the DOM structure
2. **Author** a JavaScript file that injects your component into the page
3. **Upload** the JS file to the JobLogic CDN (manual — one-time)
4. **Create a backend endpoint** that the injected JS calls for data / actions

Once the JS file is on the CDN, it is **not updated** — the injection is a one-time development step.

The backend runs as a **single-tenant** automation (tenant ID from `.env`).

---

## Step 1: Inspect the Target Page with Playwright MCP

Use the **Playwright MCP** tools (available to the AI agent) to navigate to the target page and capture the DOM structure. This is a dev-time activity — Playwright is NOT installed as a code dependency.

### 1a. Navigate to the page

Use the Playwright MCP to:

- Open a browser and navigate to `https://go.joblogic.com/<target-page>`
- Wait for the page to fully load
- Take a screenshot to see the current layout

### 1b. Inspect the DOM

Use the Playwright MCP to:

- Snapshot the DOM structure of the area where the component should be injected
- Identify the **parent selector** (where your component will be added)
- Identify the **injection method** (`appendChild`, `insertBefore`, `insertAdjacentHTML`)
- Note any **existing IDs or classes** to avoid conflicts
- Determine the **page URL pattern** to scope the injection

### 1c. Use Chrome DevTools MCP (optional)

For additional insight, use the Chrome DevTools MCP to:

- Inspect network requests on the target page
- Check existing JavaScript for potential conflicts
- Examine CSS classes used by JobLogic for style matching

---

## Step 2: Author the JavaScript File

Create the JS file that will be hosted on the JobLogic CDN.

### 2a. File structure

Create `js/<automation-name>.js`:

```javascript
(function () {
  "use strict";

  // Only run on the target page
  if (!window.location.pathname.includes("<target-path>")) return;

  // Configuration
  var API_BASE = "<your-automation-api-url>/api/automations/<name>";

  // Wait for the target element to exist
  function waitForElement(selector, callback) {
    var el = document.querySelector(selector);
    if (el) {
      callback(el);
      return;
    }
    var observer = new MutationObserver(function (mutations, obs) {
      el = document.querySelector(selector);
      if (el) {
        obs.disconnect();
        callback(el);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true });
  }

  // Create and inject the component
  function injectComponent(parentElement) {
    var container = document.createElement("div");
    container.id = "jl-<automation-name>";
    container.style.cssText = "/* match JobLogic styling */";

    container.innerHTML = [
      '<div class="panel panel-default">',
      '  <div class="panel-heading"><h4>Your Component Title</h4></div>',
      '  <div class="panel-body" id="jl-<automation-name>-content">',
      "    <p>Loading…</p>",
      "  </div>",
      "</div>",
    ].join("");

    parentElement.appendChild(container);

    // Fetch data from the backend
    loadData();
  }

  // Call the backend API
  function loadData() {
    fetch(API_BASE + "/data")
      .then(function (res) {
        return res.json();
      })
      .then(function (data) {
        var content = document.getElementById("jl-<automation-name>-content");
        if (content) {
          content.innerHTML = "<p>" + JSON.stringify(data) + "</p>";
        }
      })
      .catch(function (err) {
        console.error("[<automation-name>] API error:", err);
      });
  }

  // Start injection
  waitForElement("<parent-selector>", injectComponent);
})();
```

### 2b. Key conventions

- **IIFE** — always wrap in `(function(){ ... })()` to avoid global scope pollution
- **Vanilla JS** — do not use frameworks; the file must be lightweight
- **Defensive** — check the page URL before running; use `waitForElement` to handle async DOM
- **Styling** — use inline styles or match existing JobLogic CSS classes (`panel`, `btn`, etc.)
- **API calls** — use `fetch()` to call your backend endpoint

---

## Step 3: Upload to JobLogic CDN

This is a **manual process**:

1. The JS file is uploaded to `https://cdn.joblogic.com/`
2. Coordinate with the DevOps team for the upload
3. Once uploaded, the script is automatically loaded on the relevant JobLogic page

> **Note:** CDN URL details are managed internally. The exact path will be provided during deployment.

---

## Step 4: Create the Backend Endpoint

The injected JavaScript calls a backend API for data and actions. This is built like a webhook automation backend.

### 4a. Create the route

Create `backend/routes/<automation_name>.py`:

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from joblogic_sdk.jicro import JicroClient, JicroError
from joblogic_sdk.config import get_settings

router = APIRouter(prefix="/automations/<name>", tags=["<name>"])

settings = get_settings()


class DataResponse(BaseModel):
    # Define response fields
    items: list[dict] = []


@router.get("/data", response_model=DataResponse)
async def get_data():
    """Endpoint called by the injected JavaScript."""
    try:
        async with JicroClient() as client:
            result = await client.execute(
                tenant_id=settings.tenant_id,
                service_name="<service>",
                message_signature="<MessageMsg>",
                payload={},
            )
            return DataResponse(items=result.get("items", []))
    except JicroError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)


@router.post("/action")
async def perform_action(payload: dict):
    """Endpoint for user interactions from the injected component."""
    try:
        async with JicroClient() as client:
            result = await client.execute(
                tenant_id=settings.tenant_id,
                service_name="<service>",
                message_signature="<ActionMsg>",
                payload=payload,
            )
            return result
    except JicroError as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
```

### 4b. CORS configuration

Since the JS runs on `go.joblogic.com` but calls your API, you need CORS headers. Update `backend/main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://go.joblogic.com",   # Add this for JS injection
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 4c. Register the route

In `backend/main.py`:

```python
from backend.routes.<automation_name> import router as <name>_router
app.include_router(<name>_router, prefix="/api")
```

---

## Step 5: Testing

### 5a. Test the backend

```bash
cd backend && uvicorn main:app --reload --port 8000
```

Open `http://localhost:8000/docs` and test the `/data` and `/action` endpoints.

### 5b. Test the injection via Playwright MCP

Use the **Playwright MCP** to verify the injection works:

1. Navigate to the target page on `go.joblogic.com`
2. Read the contents of `js/<automation-name>.js`
3. Evaluate the JS code on the page via Playwright MCP
4. Take a screenshot to verify the component renders correctly
5. Use Chrome DevTools MCP to verify the backend API calls succeed

---

## Checklist

- [ ] Inspected target page with Playwright MCP — identified parent selector and injection point
- [ ] JavaScript file authored with IIFE pattern, no global scope pollution
- [ ] JS uses `fetch()` to call the backend API
- [ ] Backend endpoint created with Pydantic models
- [ ] CORS configured for `go.joblogic.com`
- [ ] Tenant ID from env / config (not hardcoded)
- [ ] Used MCP tools to discover Jicro messages
- [ ] Used `JicroClient` for all Joblogic calls
- [ ] Route registered in `backend/main.py`
- [ ] Added notification decorator and audit logging
- [ ] Tested backend via Swagger UI
- [ ] Tested injection with Playwright MCP
- [ ] JS file ready for manual CDN upload (one-time)
