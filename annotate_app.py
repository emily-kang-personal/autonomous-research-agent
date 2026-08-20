#!/usr/bin/env python3
"""Annotator UI — the human layer of Docs/annotation-spec.md.

Run:  uv run --with streamlit streamlit run annotate_app.py

Reads annotations/annotations.jsonl + traces/<session_id>.trace.jsonl, shows one pending
datapoint at a time (worst-first), and appends the human verdict as a NEW record on every
click. The app holds only navigation state; the JSONL is the single store.
"""
import getpass
import html as html_mod
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent
ANN = REPO / "annotations" / "annotations.jsonl"
TRACES = REPO / "traces"

FAILURE_TYPES = ["invented", "wrong-source", "stale-source", "gave-up-early", "wrong-value"]
# worst-first ordering for the pending queue (spec §6.2)
VERIFY_ORDER = {"contradicted": 0, "unverifiable": 1, None: 2, "confirmed": 3}

# ---- deep-water instrument theme -------------------------------------------------
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Instrument+Sans:wght@400;500;600&family=Spline+Sans+Mono:wght@400;500&display=swap');

:root{
  --ink:#d7e8ee; --dim:#7fa3b0; --faint:#4a6b78;
  --panel:rgba(13,40,56,.48); --line:rgba(94,234,212,.13);
  --bio:#35e0b8; --bio-soft:rgba(53,224,184,.14);
  --coral:#ff7a70; --coral-soft:rgba(255,122,112,.13);
  --amber:#ffc46b; --amber-soft:rgba(255,196,107,.13);
}
.stApp{
  background:
    radial-gradient(1100px 700px at 88% -12%, rgba(38,196,172,.11), transparent 60%),
    radial-gradient(900px 720px at -12% 112%, rgba(28,120,160,.14), transparent 55%),
    linear-gradient(180deg,#0a1c29 0%,#050e16 68%,#04101c 100%);
}
.stApp::before{ /* slow caustic shimmer, barely there */
  content:""; position:fixed; inset:0; pointer-events:none; z-index:0; opacity:.5;
  background:
    radial-gradient(600px 300px at 30% 20%, rgba(120,255,224,.05), transparent 70%),
    radial-gradient(700px 380px at 75% 65%, rgba(64,180,255,.05), transparent 70%);
  animation: drift 26s ease-in-out infinite alternate;
}
@keyframes drift{ from{transform:translate3d(0,0,0)} to{transform:translate3d(-40px,26px,0)} }

html, body, .stApp, [data-testid="stMarkdownContainer"] p, .stApp label{
  font-family:'Instrument Sans',sans-serif;
}
/* never touch Streamlit's icon glyphs (they're a font, not text) */
[data-testid="stIconMaterial"]{ font-family:'Material Symbols Rounded' !important; }

header[data-testid="stHeader"]{ background:transparent !important; }
.stAppDeployButton{ display:none; }
[data-testid="stAlert"]{ background:var(--panel) !important; border:1px solid var(--line);
  border-radius:10px; backdrop-filter:blur(6px); }
h1,h2,h3{ font-family:'Instrument Serif',serif !important; font-weight:400 !important; letter-spacing:.01em; }
code, pre, textarea, .evidence{ font-family:'Spline Sans Mono',monospace !important; }

[data-testid="stSidebar"]{
  background:linear-gradient(180deg, rgba(10,30,43,.92), rgba(6,17,26,.92));
  border-right:1px solid var(--line); backdrop-filter:blur(8px);
}
[data-testid="stSidebar"] hr{ border-color:var(--line); }

/* datapoint masthead */
.dp-head{ margin:.2rem 0 1.1rem; border-bottom:1px solid var(--line); padding-bottom:.9rem; }
.dp-eyebrow{ font-family:'Spline Sans Mono',monospace; font-size:.72rem; letter-spacing:.22em;
  text-transform:uppercase; color:var(--dim); }
.dp-field{ font-family:'Instrument Serif',serif; font-style:italic; font-size:2.35rem;
  line-height:1.1; color:var(--ink); }
.dp-field b{ color:var(--bio); font-style:normal; font-weight:400; }

/* chips */
.chips{ display:flex; gap:.45rem; flex-wrap:wrap; margin:.35rem 0 .9rem; }
.chip{ font-family:'Spline Sans Mono',monospace; font-size:.74rem; letter-spacing:.05em;
  padding:.28em .75em; border-radius:999px; border:1px solid var(--line);
  color:var(--dim); background:rgba(255,255,255,.02); }
.chip.ok{ color:var(--bio); border-color:rgba(53,224,184,.4); background:var(--bio-soft);
  box-shadow:0 0 14px rgba(53,224,184,.12); }
.chip.bad{ color:var(--coral); border-color:rgba(255,122,112,.4); background:var(--coral-soft); }
.chip.warn{ color:var(--amber); border-color:rgba(255,196,107,.4); background:var(--amber-soft); }

/* value + evidence panels */
.value-panel{ font-family:'Spline Sans Mono',monospace; font-size:1.02rem; color:var(--ink);
  background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:.75em 1em; margin:.2rem 0 .9rem; }
.evidence{ background:rgba(4,14,22,.72); border:1px solid var(--line); border-radius:10px;
  padding:1em 1.1em; font-size:.82rem; line-height:1.55; color:var(--dim);
  white-space:pre-wrap; max-height:340px; overflow-y:auto;
  box-shadow:inset 0 1px 12px rgba(0,0,0,.35); }
.evidence mark{ background:transparent; color:#96ffe3; font-weight:500;
  border-bottom:1px solid rgba(53,224,184,.65); text-shadow:0 0 14px rgba(53,224,184,.55); }
.quote-line{ color:var(--ink); font-style:italic; }

/* verdict buttons */
div[class*="st-key-btn_pass"] button{
  background:var(--bio-soft) !important; color:var(--bio) !important;
  border:1px solid rgba(53,224,184,.5) !important; box-shadow:0 0 16px rgba(53,224,184,.15); }
div[class*="st-key-btn_pass"] button:hover{ box-shadow:0 0 26px rgba(53,224,184,.4); transform:translateY(-1px); }
div[class*="st-key-btn_fail"] button{
  background:var(--coral-soft) !important; color:var(--coral) !important;
  border:1px solid rgba(255,122,112,.45) !important; }
div[class*="st-key-btn_fail"] button:hover{ box-shadow:0 0 26px rgba(255,122,112,.35); transform:translateY(-1px); }
div[class*="st-key-btn_unclear"] button{
  background:var(--amber-soft) !important; color:var(--amber) !important;
  border:1px solid rgba(255,196,107,.45) !important; }
div[class*="st-key-btn_unclear"] button:hover{ box-shadow:0 0 26px rgba(255,196,107,.3); transform:translateY(-1px); }
.stApp button{ transition:all .18s ease !important; border-radius:9px !important; }

[data-testid="stProgress"] > div > div > div{ background:linear-gradient(90deg,#1c9b86,var(--bio)) !important; }
</style>
"""


def chip(text, kind=""):
    return f"<span class='chip {kind}'>{html_mod.escape(str(text))}</span>"


# ---------- store (pure functions, unit-tested by tests/test_annotation_tools.py) ----------

def load_records():
    if not ANN.exists():
        return []
    return [json.loads(l) for l in ANN.read_text().splitlines() if l.strip()]


def record_key(r):
    return (r["company"], r["field"], r["run"]["session_id"])


def pending_records(records):
    """Latest record per key wins; pending = keys whose latest record has human == null."""
    latest = {}
    for r in records:  # file order is chronological (append-only)
        latest[record_key(r)] = r
    pend = [r for r in latest.values() if r.get("human") is None]
    pend.sort(key=lambda r: (VERIFY_ORDER.get(r["machine"].get("verify"), 2), r["field"]))
    return pend, latest


def append_human(base_record, label, failure_type, note):
    rec = dict(base_record)
    rec["human"] = {
        "label": label,
        "failure_type": failure_type,
        "note": note or None,
        "annotator": getpass.getuser(),
        "annotated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    ANN.parent.mkdir(exist_ok=True)
    with ANN.open("a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


# ---------- trace join (spec §6.1: join key = source_url ↔ research_fetch call args) ----------

def _norm_url(u):
    """Join-key normalization: scheme and a leading www. are citation noise
    (the amie run cited startbase.com for a www.startbase.com fetch)."""
    u = (u or "").strip().lower()
    for prefix in ("https://", "http://"):
        if u.startswith(prefix):
            u = u[len(prefix):]
    if u.startswith("www."):
        u = u[4:]
    return u.rstrip("/")


def load_trace(session_id):
    """Return (fetches: {normalized_url: markdown}, searches: [query])."""
    path = TRACES / f"{session_id}.trace.jsonl"
    fetches, searches, use_index = {}, [], {}
    if not path.exists():
        return fetches, searches
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        content = e.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if b.get("type") == "tool_use":
                use_index[b.get("id")] = (b.get("name"), b.get("input") or {})
                if b.get("name") == "research_search":
                    searches.append(b.get("input", {}).get("query", ""))
            elif b.get("type") == "tool_result":
                name, inp = use_index.get(b.get("tool_use_id"), (None, {}))
                if name == "research_fetch" and isinstance(b.get("content"), str):
                    fetches[_norm_url(inp.get("url"))] = b["content"]
    return fetches, searches


def _excerpt(page_text, idx, length, window=400):
    return (page_text[max(0, idx - window):idx],
            page_text[idx:idx + length],
            page_text[idx + length:idx + length + window])


def find_quote(page_text, quote, window=400):
    """Locate quote (exact, then case-insensitive) in fetched text.
    Returns (before, match, after) excerpt or None."""
    if not page_text or not quote:
        return None
    idx = page_text.find(quote)
    if idx < 0:
        idx = page_text.lower().find(quote.lower())
    if idx < 0:
        return None
    return _excerpt(page_text, idx, len(quote), window)


def find_partial(page_text, quote, min_words=3, window=400):
    """Fallback for paraphrased quotes: locate the longest contiguous word-run of
    the quote that appears verbatim in the page. Returns (before, match, after)
    or None. Lets the human judge a non-verbatim quote against the real page
    region instead of a bare 'not found'."""
    if not page_text or not quote:
        return None
    words = quote.split()
    low = page_text.lower()
    for size in range(len(words) - 1, min_words - 1, -1):
        for start in range(len(words) - size + 1):
            chunk = " ".join(words[start:start + size])
            idx = low.find(chunk.lower())
            if idx >= 0:
                return _excerpt(page_text, idx, len(chunk), window)
    return None


# ---------- UI ----------

def main():
    import streamlit as st

    st.set_page_config(page_title="Datapoint Annotator", page_icon="🌊", layout="wide")
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    records = load_records()
    if not records:
        st.warning(f"No records in {ANN}. Run prefill.py after a company run first.")
        st.stop()

    pend_all, latest = pending_records(records)
    runs = sorted({(r["company"], r["run"]["session_id"]) for r in latest.values()})

    with st.sidebar:
        st.markdown("<div class='dp-eyebrow'>ENRICHMENT · GROUND TRUTH</div>"
                    "<h2 style='margin:.1em 0 .6em'>The Annotator</h2>",
                    unsafe_allow_html=True)
        labels = [f"{c} · {s[:15]}…" for c, s in runs]
        pick = st.radio("Company / run", range(len(runs)),
                        format_func=lambda i: labels[i])
        company, session_id = runs[pick]
        mine = [r for r in latest.values()
                if r["company"] == company and r["run"]["session_id"] == session_id]
        done = [r for r in mine if r.get("human")]
        st.progress(len(done) / max(1, len(mine)),
                    text=f"{len(done)}/{len(mine)} annotated")
        if done:
            by_label = {}
            for r in done:
                by_label[r["human"]["label"]] = by_label.get(r["human"]["label"], 0) + 1
            st.caption(" · ".join(f"{k}: {v}" for k, v in sorted(by_label.items())))

        # go back to a previous annotation — re-judging appends a new record (latest wins)
        if st.session_state.pop("_clear_revisit", False):
            st.session_state.pop("revisit_sel", None)
        done_sorted = sorted(done, key=lambda r: r["human"]["annotated_at"], reverse=True)
        revisit_field = st.selectbox(
            "Revisit annotated", [None] + [r["field"] for r in done_sorted],
            format_func=lambda f: "— pending queue —" if f is None else
            f"{f} · {next(r['human']['label'] for r in done_sorted if r['field'] == f)}",
            key="revisit_sel")

    pend = [r for r in pend_all
            if r["company"] == company and r["run"]["session_id"] == session_id]

    if revisit_field is not None:
        rec = latest[(company, revisit_field, session_id)]
        h = rec["human"]
        st.info(f"Revisiting **{revisit_field}** — currently `{h['label']}`"
                + (f" ({h['failure_type']})" if h.get("failure_type") else "")
                + (f" · note: “{h['note']}”" if h.get("note") else "")
                + f" · {h['annotated_at']}. A new verdict appends a fresh record "
                  "(latest wins; history is kept).")
    else:
        if not pend:
            st.success(f"All datapoints for **{company}** ({session_id}) are annotated. 🎉")
            st.stop()
        rec = pend[0]
    agent = rec["agent"]
    machine = rec["machine"]
    fetches, searches = load_trace(session_id)

    st.markdown(
        f"<div class='dp-head'><div class='dp-eyebrow'>datapoint · {company}</div>"
        f"<div class='dp-field'><b>{html_mod.escape(rec['field'])}</b></div></div>",
        unsafe_allow_html=True)
    left, right = st.columns([3, 2])

    with left:
        status_kind = {"found": "ok", "unreachable": "warn", "not_disclosed": ""}
        validate_kind = {"pass": "ok", "fail": "bad"}
        verify_kind = {"confirmed": "ok", "contradicted": "bad", "unverifiable": "warn"}
        v = machine.get("verify")
        st.markdown(
            "<div class='chips'>"
            + chip(f"status · {agent.get('status')}", status_kind.get(agent.get("status"), ""))
            + chip(f"validate · {machine.get('validate')}", validate_kind.get(machine.get("validate"), ""))
            + chip(f"verify · {v or 'not run'}", verify_kind.get(v, ""))
            + "</div>", unsafe_allow_html=True)
        if agent.get("value") is not None:
            st.markdown(f"<div class='value-panel'>"
                        f"{html_mod.escape(json.dumps(agent.get('value'), ensure_ascii=False))}"
                        f"</div>", unsafe_allow_html=True)
        if agent.get("source_url"):
            st.markdown(f"**source:** {agent['source_url']}")
        if agent.get("note"):
            st.markdown(f"**agent note:** {agent['note']}")

        if agent.get("status") == "found":
            page = fetches.get(_norm_url(agent.get("source_url")))
            quote = agent.get("evidence_quote", "")
            st.markdown(f"<div class='quote-line'>“{html_mod.escape(quote)}”</div>",
                        unsafe_allow_html=True)
            if page is None:
                st.error("⛔ source_url matches NO research_fetch call in the trace — "
                         "the agent cites a page it never read (invention flag).")
            else:
                hit = find_quote(page, quote)
                partial = None if hit else find_partial(page, quote)
                if hit:
                    st.markdown("✅ Quote is **verbatim** on the fetched page:")
                elif partial:
                    st.warning("⚠️ quote is NOT verbatim (SPEC requires exact page text) — "
                               "closest matching region shown below.")
                    hit = partial
                else:
                    st.warning("⚠️ quote NOT found in the fetched page text at all — "
                               "possible full paraphrase, or truncation (results are "
                               "capped at 50k chars). Check the source link before "
                               "calling it invented.")
                if hit:
                    before, match, after = (html_mod.escape(s) for s in hit)
                    st.markdown(
                        f"<div class='evidence'>…{before}<mark>{match}</mark>{after}…</div>",
                        unsafe_allow_html=True)
        else:
            st.info("Non-`found` field — judge whether giving up was right. "
                    "Searches the agent ran this session:")
            for q in searches:
                st.markdown(f"- `{q}`")

    with right:
        st.markdown("### Verdict")
        # key inputs to the record so they reset when the next datapoint loads
        # (unkeyed widgets persist across reruns — the note would carry over)
        rk = f"{rec['company']}|{rec['field']}|{rec['run']['session_id']}"
        ftype = st.selectbox("failure_type (required for Fail)", FAILURE_TYPES,
                             index=None, placeholder="pick if failing…",
                             key=f"ftype|{rk}")
        note = st.text_area("note (required for Unclear)", height=80,
                            key=f"note|{rk}")
        def _submit(label, failure_type):
            append_human(rec, label, failure_type, note)
            st.session_state["_clear_revisit"] = True  # back to the queue after judging
            st.rerun()

        c1, c2, c3 = st.columns(3)
        if c1.button("Pass", use_container_width=True, key="btn_pass"):
            _submit("pass", None)
        if c2.button("Fail", use_container_width=True, key="btn_fail"):
            if not ftype:
                st.error("Pick a failure_type first.")
            else:
                _submit("fail", ftype)
        if c3.button("Unclear", use_container_width=True, key="btn_unclear"):
            if not note.strip():
                st.error("Unclear requires a note.")
            else:
                _submit("unclear", None)
        st.caption(f"{len(pend)} pending · every click appends to "
                   f"annotations/annotations.jsonl immediately")


if __name__ == "__main__":
    main()
