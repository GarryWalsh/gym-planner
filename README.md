# Gym Planner — Streamlit × LangGraph × Groq (MVP)

This MVP generates a multi-day gym plan using a local exercise catalog (ExRx-linked) and a small LangGraph pipeline. Plans can be downloaded as CSV/Markdown.

## Stack
- **Streamlit** UI (sliders, selectors) — multipage-ready.  
- **LangGraph** agent loop: `allowed_list → plan_generate → validate → (repair)` with strict JSON schemas.  
- **Groq** Structured Outputs for future LLM steps (JSON Schema enforced).  
- **Pydantic** models for all inputs/outputs.  

Docs:
- Streamlit CLI/config & multipage apps.  
- LangGraph nodes/edges & Graph API.  
- Groq Structured Outputs + Python SDK.  
- Pydantic BaseModel.  
*(See inline citations in the main response.)*

## Running the app
```bash
conda env create -f conda-env.yml
conda activate gymplanner
copy .env.example .env    # or: cp .env.example .env
# Optional: add GROQ_API_KEY to .env for LLM jobs; local mode works without it.
```

Start the server:
- Windows/PowerShell
  ```powershell
  .\scripts\run_app.ps1 -Headless
  # or specify address/port
  .\scripts\run_app.ps1 -Address 127.0.0.1 -Port 8501 -Headless
  ```
- macOS/Linux (bash)
  ```bash
  chmod +x scripts/run_app.sh
  ./scripts/run_app.sh 127.0.0.1 8501 --headless
  ```

Notes:
- Download buttons (CSV, Markdown, PDF) appear under the generated plan on the main page. The old Export page has been removed.
- If GROQ_API_KEY is set, LLM generate/validate/repair are used with structured outputs; otherwise the app falls back to the local planner/validator.
- Look for the ℹ️ Info popover near the header to learn how LLMs are used in this app, and the 🧠 Summary popover for a clear explanation of your plan.


## Tests

Run the test suite from the project root:

- Windows/macOS/Linux:
  - python -m pytest -q

Quick smoke only:
  - pytest -q tests/test_smoke.py


## Reattach Git (VCS)

If your IDE shows “Not under VCS” but this project should track the GitHub repo, use these scripts to (re)attach the working directory to the remote:

- Windows (PowerShell):
  - .\scripts\git_attach.ps1 -RemoteUrl "https://github.com/GarryWalsh/gym-planner" -Branch main

- macOS/Linux (bash):
  - chmod +x scripts/git_attach.sh
  - ./scripts/git_attach.sh "https://github.com/GarryWalsh/gym-planner" main

Verify:
- git remote -v   # should show origin https://github.com/GarryWalsh/gym-planner
- git status -sb  # should show branch and status

JetBrains IDE tip:
- If the project still shows as not under VCS after running the script, re-map the VCS:
  - Settings/Preferences → Version Control → + Add the project root and set VCS to Git, or
  - VCS menu → Enable Version Control Integration… → Git.
- Restarting the IDE can also help it pick up the .git folder.


## Groq model compatibility

- The app uses exactly the model specified in GROQ_MODEL. There is no automatic aliasing or multi-model fallback.
- If GROQ_MODEL is unset, the default used is: llama-3.1-70b-specdec.
- Ensure your chosen model supports Groq JSON Schema structured outputs. Recommended: llama-3.1-70b-specdec or llama-3.1-8b-instant.
- If the specified model is invalid, decommissioned, or unsupported for JSON Schema, the UI will show the exact error returned by Groq. Update GROQ_MODEL accordingly (see https://console.groq.com/docs/models).


## Authentication (Auth0 + Persistent Login Cookie)

The app gates all functionality behind a login screen. You can use either:
- Auth0 Universal Login (Google and other identity providers), or
- a simple DEV password gate for local development.

### Quick start (DEV login)
1) Copy .env.example to .env
2) Set a local password (no quotes):
   - DEV_LOGIN_PASSWORD=your_local_password
3) Run the app. You’ll see a simple password prompt. On success, you will be automatically signed in.

A signed cookie will be created so you won’t have to log in every time you refresh the page (see “Cookie persistence” below).

### Auth0 setup
1) Create an application in Auth0 (Regular Web Application is fine).
2) Note your Auth0 Domain and Client ID/Secret from the application settings.
3) Add your Streamlit app URL to Allowed Callback URLs. For example:
   - Local: http://localhost:8501
   - Render/Cloud: https://your-app.onrender.com (use your actual URL)
4) Configure the app environment (via .env or Streamlit Secrets):
   - AUTH0_DOMAIN=your-tenant.eu.auth0.com
   - AUTH0_CLIENT_ID=...
   - AUTH0_CLIENT_SECRET=...
   - AUTH0_CALLBACK_URL=https://your-app-url
   - Optional (recommended): AUTH_COOKIE_SECRET=<random-long-string>

Start the app and click “Sign in with Auth0 (Google, etc.)”. After auth, you will be redirected back and signed in.

### Cookie persistence (no more logging in every refresh)
- On a successful login (Auth0 or DEV), the app issues a short JWT-like, HMAC-SHA256 signed token and stores it in a browser cookie named gp_auth.
- On future visits, a tiny client-side snippet promotes that cookie to a temporary ?auth=... query param so the server can verify the signature and expiration and silently sign you in.
- The cookie contains only minimal user info (sub, name, provider) and an expiration (default 30 days). No tokens from Auth0 are stored.
- To protect integrity, set AUTH_COOKIE_SECRET in your environment or Streamlit secrets; otherwise we fall back to AUTH0_CLIENT_SECRET or DEV_LOGIN_PASSWORD.
- Attributes: path=/; SameSite=Lax; Secure (on HTTPS). This cookie is not HttpOnly because it’s set in the browser; it is signed and time-limited. Avoid storing sensitive data in it.

To “log out”, clear the gp_auth cookie from your browser (or change AUTH_COOKIE_SECRET / DEV_LOGIN_PASSWORD to invalidate existing cookies). You can also add a UI button to clear the cookie if you wish.

### Where to set secrets
- Local .env (picked up by pydantic-settings):
  - AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_CALLBACK_URL
  - DEV_LOGIN_PASSWORD (for DEV gate)
  - AUTH_COOKIE_SECRET (HMAC for cookie signing)
- Streamlit Cloud/Render: add the same keys to the service’s environment or Streamlit Secrets.

Security note: This is an MVP-friendly approach suitable for low-risk use cases. For production, consider a proper backend session store with HttpOnly cookies.