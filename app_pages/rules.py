"""Marketplace rules page: the own-words summaries the RAG retrieves from."""

import streamlit as st

from enrich.rules import RULES_DIR, parse_rules_file

st.title("Marketplace rules")
st.caption("Our own-words summaries of each marketplace's listing policies. The app retrieves "
           "the most relevant ones for each product and shows which it applied. Not legal "
           "advice; each rule links to its source.")

files = sorted(RULES_DIR.glob("*.md"))
names = {"amazon": "Amazon", "ebay": "eBay"}
for tab, path in zip(st.tabs([names.get(p.stem, p.stem) for p in files]), files):
    with tab:
        for r in parse_rules_file(path):
            with st.expander(r.heading):
                st.write(r.text)
                if r.source:
                    st.markdown(f"[Source]({r.source})")
