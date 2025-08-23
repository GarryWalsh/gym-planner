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
- Download buttons (CSV, Markdown, PDF) appear under the generated plan on the main page (Export page is deprecated and hidden from the sidebar).
- If GROQ_API_KEY is set, LLM generate/validate/repair are used with structured outputs; otherwise the app falls back to the local planner/validator.


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
