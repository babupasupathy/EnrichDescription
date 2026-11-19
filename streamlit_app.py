"""EnrichDescription Streamlit UI (PRD: F1 input, F8 results UI)."""

import asyncio
import os
import queue
import threading
import time
import uuid

import openai
import streamlit as st

# Streamlit Community Cloud keeps secrets in st.secrets; expose them as env vars for
# pydantic-settings and LangSmith. Locally, a .env file is used instead.
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str):
            os.environ.setdefault(_k.upper(), _v)
except FileNotFoundError:
    pass

from langgraph.types import Command  # noqa: E402

from enrich import rules  # noqa: E402
from enrich.config import get_settings  # noqa: E402
from enrich.workflow import ModelUnavailable, build_graph  # noqa: E402

RUNS_PER_HOUR = 10
RUN_TIMEOUT_S = 300
# What runs after each step finishes (shown while waiting), and the line left once it's done.
NEXT_STEP = {
    None: "Checking category and marketplace rules",
    "classify": "Reading product details",
    "extract_attributes": "Fetching top listings (Amazon takes 1-2 minutes)",
    "fetch_listings": "Filtering to relevant listings",
    "filter_listings": "Writing listings and checking marketplace rules",
}
DONE = {
    "classify": "Checked category and marketplace rules",
    "extract_attributes": "Read product details",
    "fetch_listings": "Fetched top listings",
    "filter_listings": "Filtered to relevant listings",
    "generate": "Wrote and checked listings",
}
REASON_TAGS = ["Wrong keywords", "Wrong tone", "Missing details", "Too long"]

st.set_page_config(page_title="EnrichDescription", page_icon="🏷️", layout="centered")
settings = get_settings()


@st.cache_resource(show_spinner="Loading marketplace rules...")
def graph():
    try:
        rules.get_index()  # Embed the rules once at startup, not on the first user's run.
    except Exception:
        pass  # The workflow warns and carries on without them.
    return build_graph()


@st.cache_resource
def event_loop() -> asyncio.AbstractEventLoop:
    # One long-lived loop for the whole app. asyncio.run() per click would close its loop
    # afterwards, but langchain-openai shares one pooled HTTP client across calls, so the
    # next run would reuse connections tied to the closed loop ("Event loop is closed").
    loop = asyncio.new_event_loop()
    threading.Thread(target=loop.run_forever, daemon=True, name="enrich-loop").start()
    return loop


def ss():
    return st.session_state


async def stream_graph(arg, config, events: queue.Queue) -> dict:
    """Run the graph, sending step and note events to the UI thread; returns what ainvoke would."""
    final, interrupts = {}, ()
    async for mode, chunk in graph().astream(arg, config,
                                             stream_mode=["updates", "custom", "values"]):
        if mode == "values":
            final = chunk
        elif mode == "custom":
            events.put(("note", chunk))
        else:
            for node in chunk:
                if node == "__interrupt__":
                    interrupts = chunk[node]
                else:
                    events.put(("done", node))
    return {**final, "__interrupt__": list(interrupts)} if interrupts else final


def run_with_progress(arg, config, first_step: str):
    events: queue.Queue = queue.Queue()
    future = asyncio.run_coroutine_threadsafe(
        asyncio.wait_for(stream_graph(arg, config, events), RUN_TIMEOUT_S), event_loop())
    start, step, lines = time.time(), first_step, []
    with st.status(step, expanded=True) as status:
        while True:
            try:
                kind, value = events.get(timeout=0.5)
            except queue.Empty:
                if future.done():
                    break
                status.update(label=f"{step}... {time.time() - start:.0f}s")
                continue
            line = f"· {value}" if kind == "note" else f"✓ {DONE.get(value, value)}"
            st.write(line)
            lines.append(line)
            if kind == "done":
                step = NEXT_STEP.get(value, step)
        try:
            result = future.result()
        except BaseException:
            status.update(label=f"Stopped after {time.time() - start:.0f}s", state="error")
            raise
        label = ("A few details needed" if "__interrupt__" in result
                 else f"Done in {time.time() - start:.0f}s")
        status.update(label=label, state="complete", expanded=False)
    ss().progress = (label, lines)  # Shown again above the results after the page reruns.
    return result


def run_graph(payload, resume: bool = False):
    run_id = uuid.uuid4()
    config = {"configurable": {"thread_id": ss().thread_id}, "run_id": run_id,
              "run_name": "enrich-listing"}
    arg = Command(resume=payload) if resume else payload
    first = "Reading your answers" if resume else NEXT_STEP[None]
    try:
        ss().result = run_with_progress(arg, config, first)
    except TimeoutError:
        st.error(f"This run took more than {RUN_TIMEOUT_S // 60} minutes and was stopped. "
                 "Please try again; repeat runs are faster because listings are cached.")
        st.stop()
    except openai.APIStatusError as e:
        # Streamlit Cloud redacts exception text; the API's own message holds no secrets
        # and says what to fix (credits, key, no available host).
        st.error(f"The model provider returned an error ({e.status_code}): {e.message}")
        st.stop()
    except ModelUnavailable as e:
        st.error(str(e))
        st.stop()
    ss().run_id = str(run_id)


def allowed_to_run() -> bool:
    now = time.time()
    ss().run_times = [t for t in ss().get("run_times", []) if now - t < 3600]
    if len(ss().run_times) >= RUNS_PER_HOUR:
        return False
    ss().run_times.append(now)
    return True


def send_feedback(key: str, score=None, value=None, comment: str | None = None) -> None:
    """Star ratings and edits go to LangSmith as eval data (PRD: Decisions)."""
    if not os.environ.get("LANGSMITH_API_KEY") or "run_id" not in ss():
        return
    try:
        from langsmith import Client
        Client().create_feedback(ss().run_id, key=key, score=score, value=value, comment=comment)
    except Exception as e:  # feedback must never break the page
        st.toast(f"Couldn't save feedback: {e}")


# --- F1: input ----------------------------------------------------------------------------
st.title("EnrichDescription")
st.caption("Describe your product once. Get a listing for each marketplace, based on what "
           "top sellers do, and checked against each marketplace's rules.")

with st.form("input"):
    description = st.text_area(
        "Product description", max_chars=settings.max_input_chars, height=180,
        placeholder="e.g. Green floral wrap dress, midi length, flutter sleeves, rayon, sizes S-XL")
    marketplaces = st.multiselect("Marketplaces", ["amazon", "ebay"], default=["amazon", "ebay"],
                                  format_func=lambda m: {"amazon": "Amazon", "ebay": "eBay"}[m])
    submitted = st.form_submit_button("Generate listings", type="primary")

if submitted:
    if not description.strip() or not marketplaces:
        st.warning("Add a description and choose at least one marketplace.")
    elif not allowed_to_run():
        st.warning(f"Demo limit: {RUNS_PER_HOUR} runs per hour. Please try again later.")
    else:
        ss().thread_id = str(uuid.uuid4())
        run_graph({"description": description, "marketplaces": marketplaces})
        # Redraw from the top so the details form always sits in the same slot. Otherwise the
        # progress box above it shifts the form down, and on the next run Streamlit shows the
        # old copy faded underneath while the run is working.
        st.rerun()

result = ss().get("result")
if not result:
    st.stop()

# --- F3: ask once for missing attributes ----------------------------------------------------
if "__interrupt__" in result:
    ask = result["__interrupt__"][0].value
    st.info("A few details are missing. Add them so the listings are complete.")
    with st.form("missing"):
        answers = {a: st.text_input(a.replace("_", " ").capitalize()) for a in ask["missing"]}
        if st.form_submit_button("Continue", type="primary"):
            run_graph(answers, resume=True)
            st.rerun()
    st.stop()

# --- F2 outcomes ----------------------------------------------------------------------------
for reason in (result.get("blocked") or {}).values():
    st.error(reason)
if result.get("status") == "prohibited":
    st.stop()
if result.get("status") == "unsupported":
    st.info(result["message"])
    st.stop()
for w in result.get("warnings", []):
    st.warning(w)

# --- F8: results ----------------------------------------------------------------------------
if "progress" in ss():
    label, lines = ss().progress
    with st.status(label, state="complete", expanded=False):
        for line in lines:
            st.write(line)
results = result.get("results", {})
tabs = st.tabs([m.title() if m != "ebay" else "eBay" for m in results])
for tab, (market, out) in zip(tabs, results.items()):
    with tab:
        listing = out["listing"]
        st.caption(f"Based on {out['competitor_count']} relevant competitor listings.")

        st.markdown(f"**Title** · {len(listing['title'])} characters")
        st.code(listing["title"], language=None, wrap_lines=True)
        if listing["bullets"]:
            st.markdown("**Bullets**")
            st.code("\n".join(f"• {b}" for b in listing["bullets"]), language=None,
                    wrap_lines=True)
        st.markdown(f"**Description** · {len(listing['description'])} characters")
        st.code(listing["description"], language=None, wrap_lines=True)
        st.markdown("**Keywords**")
        st.code(", ".join(listing["keywords"]), language=None, wrap_lines=True)

        if out["issues"]:
            with st.expander(f"Rules check: {len(out['issues'])} warning(s)", expanded=True):
                for i in out["issues"]:
                    st.markdown(f"- **{i['rule']}** ({i['field']}): {i['detail']}")
        else:
            st.success("Passed the rules check.")

        with st.expander("Patterns used from top listings"):
            p = listing["patterns"]
            st.markdown("**Top keywords:** " + ", ".join(p["top_keywords"]))
            st.markdown("**Title structure:** " + p["title_structure"])
            st.markdown("**What buyers mention:** " + "; ".join(p["buyer_review_themes"]))

        if out.get("rules_used"):
            with st.expander(f"Marketplace rules applied ({len(out['rules_used'])})"):
                for r in out["rules_used"]:
                    st.markdown(f"- [{r['heading']}]({r['source']})")

        with st.expander("Edit this listing"):
            edited = st.text_area("Your final version", key=f"edit-{market}", height=220,
                                  value=f"{listing['title']}\n\n{listing['description']}")
            if st.button("Save my edits", key=f"save-{market}"):
                send_feedback("final_edit", value={"marketplace": market, "text": edited})
                st.toast("Saved. Thanks!")

        # North-star metric: one-tap star rating (PRD: Success metrics)
        st.markdown("**How good is this listing?**")
        stars = st.feedback("stars", key=f"stars-{ss().run_id}-{market}")
        if stars is not None:
            score = stars + 1
            tags = []
            if score <= 3:
                tags = st.pills("What was wrong?", REASON_TAGS, selection_mode="multi",
                                key=f"tags-{ss().run_id}-{market}") or []
            sent_key = f"sent-{ss().run_id}-{market}-{score}-{len(tags)}"
            if not ss().get(sent_key):
                send_feedback("stars", score=score / 5,
                              value={"marketplace": market, "stars": score, "tags": tags})
                ss()[sent_key] = True
