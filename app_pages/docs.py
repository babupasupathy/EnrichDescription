"""Render repo Markdown in Streamlit, with local images (st.markdown can't load repo paths)."""

import re
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
IMAGE = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)\s]+)\)\s*$", re.M)


def render_markdown(path: Path, sections: list[str] | None = None) -> None:
    """Render a Markdown file; with `sections`, only those "## " sections, in that order."""
    text = path.read_text()
    if sections:
        parts = {p.split("\n", 1)[0].strip(): "## " + p for p in re.split(r"^## ", text, flags=re.M)[1:]}
        text = "\n\n".join(parts[s] for s in sections if s in parts)
    pos = 0
    for m in IMAGE.finditer(text):
        st.markdown(text[pos:m.start()])
        src = m["src"]
        if src.startswith("http"):
            st.image(src, caption=m["alt"])
        else:
            st.image(str((path.parent / src).resolve()), caption=m["alt"])
        pos = m.end()
    st.markdown(text[pos:])
