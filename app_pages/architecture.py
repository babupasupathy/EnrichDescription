"""Architecture page: the diagrams and stack from the PRD, plus the live LangGraph steps."""

import streamlit as st

from app_pages.docs import ROOT, render_markdown

st.title("Architecture")
render_markdown(ROOT / "docs" / "PRD.md",
                sections=["Architecture and tech stack", "User flow", "Functional requirements"])

st.markdown("## Workflow graph")
st.caption("The LangGraph steps the app runs, drawn from the code.")
st.graphviz_chart("""
digraph {
  rankdir=TB; node [shape=box, style="rounded", fontname="Inter, sans-serif"];
  start [label="Seller description", shape=oval];
  classify [label="classify\\ncheap model + rules RAG\\nprohibited? supported category?"];
  extract [label="extract_attributes\\ncheap model"];
  ask [label="Ask seller once\\nfor missing details", shape=note];
  fetch [label="fetch_listings\\nMCP: eBay Browse API, Amazon via Rainforest"];
  filter [label="filter_listings\\nmid model"];
  generate [label="generate\\ntop model + rules RAG\\ncompliance check, one fix pass"];
  stop [label="Stop with a message", shape=oval];
  done [label="Listing per marketplace", shape=oval];
  start -> classify; classify -> stop [label="prohibited everywhere\\nor unsupported"];
  classify -> extract; extract -> ask [style=dashed]; ask -> extract [style=dashed];
  extract -> fetch -> filter -> generate -> done;
}
""")
