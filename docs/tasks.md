# GymPlanner Improvement Tasks

Date: 2025-08-23

The following enumerated checklist outlines actionable improvements for GymPlanner. Items are ordered to establish a sensible execution flow: establish foundations, model the data/domain, implement core planning and LLM integration, build the UI, add configuration/observability, improve code quality and tests, set up CI/CD, and finalize documentation and release processes.

### Foundation & Repository Hygiene
1. [ ] Define supported Python version (e.g., 3.11) and document it in README and a runtime file (e.g., .python-version) or pyproject classifiers.
2. [x] Create a standard .gitignore (Python, Streamlit, venv/conda, IDEs) and commit.
3. [ ] Add a LICENSE file (e.g., MIT or Apache-2.0) and reflect it in README.
4. [ ] Introduce a pyproject.toml with project metadata (name, version, authors) and tool configurations (ruff/black/mypy/pytest).
5. [ ] Decide on dependency management strategy (requirements.txt with pinning vs. pyproject-managed) and document it.
6. [x] Populate runtime dependencies (Streamlit, LangGraph, Pydantic v2, Groq SDK, python-dotenv or pydantic-settings, pandas, typing-extensions) with pinned versions.
7. [ ] Add a dev dependency set (pytest, pytest-cov, ruff, black, mypy, types-requests, pip-tools or uv) and document install instructions.
8. [x] Add conda-env.yml that matches README instructions (channels, dependencies) or update README to reflect the chosen env manager.
9. [x] Add .env.example with GROQ_API_KEY and other relevant variables (e.g., APP_ENV, LOG_LEVEL) and reference in README.
10. [x] Populate app/__init__.py with __version__ and convenient exports where appropriate.

### Data Layer (exrx_catalog.json)
11. [x] Define a Pydantic model (Exercise) that matches the JSON catalog shape (id, name, exrx_url, primary_muscles, function, equipment, type, enriched).
12. [ ] Add JSON Schema for Exercise (and optional Catalog) to validate the dataset independent of code.
13. [ ] Implement a data loader utility (app/data/loader.py) that validates, normalizes fields (IDs, enums), and caches the parsed catalog.
14. [ ] Create enums/constants for muscles, functions, equipment, exercise type to avoid magic strings.
15. [ ] Implement fast lookup indexes (by function, muscle, equipment) to support planners efficiently.
16. [ ] Add a script (scripts/validate_data.py) to validate exrx_catalog.json against the schema and models; integrate in CI.
17. [ ] Add unit tests for data loader, schema validation, and normalization logic using a small fixture subset of the catalog.

### Domain Modeling & Planner Core
18. [ ] Define domain models: UserProfile (experience, goals, available_days, injuries), Constraints, DayPlan, ExerciseBlock, SetScheme.
19. [x] Implement allowed_list builder to filter catalog based on constraints (equipment availability, injuries, preferences).
20. [x] Implement plan_generate to assemble multi-day programs balancing movement patterns (push/pull/legs/full-body) and volume.
21. [x] Implement validate step to check plan constraints (volume caps, muscle group frequency, exercise diversity) with clear errors.
22. [ ] Implement repair step to iteratively fix validation failures (swap exercises, adjust volume) with deterministic fallback.
23. [ ] Add reproducibility controls (random seed) for deterministic plan generation when LLM is not used.
24. [x] Provide CSV and Markdown exporters for any generated plan (app/exporters/csv.py and app/exporters/markdown.py).

### LLM & LangGraph Integration
25. [x] Define strict Pydantic schemas for all graph node inputs/outputs and produce JSON schema for LLM structured outputs.
26. [x] Implement a LangGraph graph with nodes (allowed_list → plan_generate → validate → repair) wired with typed boundaries.
27. [x] Integrate Groq SDK with structured output parsing, retries, and timeouts; surface helpful error messages.
28. [x] Add configuration flags to run in "local only" mode (no LLM) vs. "LLM-assisted" mode.
29. [ ] Implement rate limiting and exponential backoff with jitter for LLM calls.
30. [ ] Cache LLM intermediate results (e.g., allowed list rationales) keyed by inputs to save costs and time.

### Streamlit UI
31. [x] Create app/streamlit_app.py with a clean, multipage-ready layout (inputs sidebar, preview, download buttons).
32. [x] Add state management for inputs and generated plans; persist seed and last plan.
33. [x] Implement CSV/Markdown download buttons using the exporter utilities.
34. [x] Add input validation and helpful UI error messages (e.g., when no exercises match constraints).
35. [ ] Add a lightweight theming and responsive layout for common screen sizes.

### Configuration, Logging, and Error Handling
36. [x] Implement centralized settings via pydantic-settings (app/config.py) loading from environment and .env.
37. [ ] Set up structured logging (JSON or key-value) with app-wide logger and configurable log level.
38. [ ] Define a custom exception hierarchy (e.g., DataValidationError, PlanningError, LLMError) and handle them in UI and services.
39. [ ] Add tracing/diagnostics hooks (optional) for LangGraph node execution times and decisions.

### Code Quality & Maintenance
40. [ ] Enforce code style with Ruff and Black; add configuration in pyproject and format existing code.
41. [ ] Add MyPy type checking with sensible strictness; annotate public interfaces and core modules.
42. [ ] Introduce pre-commit hooks (ruff, black, mypy, pytest -q on changed files) and document usage.
43. [x] Organize package modules: app/models, app/data, app/services (planning), app/llm, app/exporters, app/ui.
44. [ ] Add docstrings and module-level documentation for public APIs and domain concepts.

### Testing Strategy
45. [ ] Configure pytest.ini or pyproject test settings (testpaths, markers, filterwarnings).
46. [ ] Build unit tests for models, data loader, planner steps, and exporters.
47. [ ] Add integration tests for the end-to-end planning pipeline (local-only mode).
48. [ ] Add contract tests for LLM structured outputs using recorded fixtures or mock clients.
49. [ ] Collect coverage with pytest-cov and set a minimum threshold (e.g., 80%).

### CI/CD
50. [ ] Add GitHub Actions workflow to run lint, type check, tests, and data validation on pushes and PRs.
51. [ ] Cache dependencies in CI and produce test reports and coverage artifacts.
52. [ ] Add a workflow to build a Streamlit-compatible artifact or container image (optional).

### Performance & Reliability
53. [ ] Profile critical code paths (catalog filtering, plan generation) and optimize hotspots.
54. [x] Introduce caching for expensive operations (in-memory or disk) with clear invalidation.
55. [ ] Add timeouts and circuit breakers around external calls (Groq) to keep the UI responsive.

### Security & Compliance
56. [ ] Ensure all inputs (UI and LLM) are validated and sanitized; guard against prompt injection impacts on structured outputs.
57. [x] Store secrets only in environment variables; never commit actual keys; verify .env is gitignored.
58. [ ] Review data licensing for ExRx references and include proper attribution in the app and README.
59. [ ] Render Markdown safely (sanitize/allowlist) in Streamlit to avoid XSS via user-provided text.

### Documentation & Developer Experience
60. [x] Update README to match actual files and commands; include quickstart, troubleshooting, and screenshots/GIF.
61. [ ] Add an ARCHITECTURE.md with diagrams of data flow and LangGraph node wiring.
62. [ ] Provide a CONTRIBUTING.md (dev setup, style guide, testing, release steps).
63. [ ] Add a CHANGELOG.md following Keep a Changelog and Semantic Versioning.
64. [ ] Document a minimal roadmap in ROADMAP.md with future features and priorities.

### Future Enhancements (Optional Roadmap)
65. [ ] Add persistence for user profiles and saved plans (local file or lightweight DB).
66. [ ] Implement exercise enrichment (auto-tagging, difficulty, substitutions) and store in a derived cache.
67. [ ] Add i18n support for UI labels and plan outputs.
68. [ ] Explore lightweight analytics (opt-in) for feature usage to guide priorities.
69. [ ] Package as a CLI for batch plan generation separate from Streamlit UI.
