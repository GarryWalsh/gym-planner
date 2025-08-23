from __future__ import annotations

import streamlit as st

from app.services.export import to_csv, to_markdown

st.set_page_config(page_title="Export Plan", page_icon="📤")

st.title("Export")

plan = st.session_state.get("plan")
if plan is None:
    st.info("No plan in session. Generate a plan on the main page first.")
else:
    csv_bytes = to_csv(plan)
    md_text = to_markdown(plan)
    st.download_button("Download CSV", data=csv_bytes, file_name="gym_plan.csv", mime="text/csv")
    st.download_button("Download Markdown", data=md_text, file_name="gym_plan.md", mime="text/markdown")
