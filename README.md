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
- Export page is available at the top-right “Pages” menu (2_Export).
- If GROQ_API_KEY is set, LLM generate/validate/repair are used with structured outputs; otherwise the app falls back to the local planner/validator.


## Tests

Run the quick checks from the project root:

- Windows/macOS/Linux:
  - python -m scripts.smoke_test
  - python -m scripts.extended_tests
