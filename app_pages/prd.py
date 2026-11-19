"""PRD page: renders docs/PRD.md."""

from app_pages.docs import ROOT, render_markdown

render_markdown(ROOT / "docs" / "PRD.md")
