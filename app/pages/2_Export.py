from __future__ import annotations

import streamlit as st

from app.services.export import to_csv, to_markdown

st.set_page_config(page_title="Export Plan", page_icon="📤")

st.title("Export (Deprecated)")

st.info("Exports now live under the generated plan on the main page. Use the Download CSV/Markdown buttons shown beneath your plan.")
