#!/usr/bin/env python3
"""Offline tests for the annotation layer (prefill.py + annotate_app.py pure functions).
Runs against the REAL amie fixture (results/amie.json + traces/<session>.trace.jsonl).
Fails loudly; exits non-zero on any failure; never skips — a missing fixture is a FAIL."""
import json, os, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
import annotate_app as app

SESSION = "20260820_042851_6906fb"
TRACE = REPO / "traces" / f"{SESSION}.trace.jsonl"
RESULT = REPO / "results" / "amie.json"

fails = []
def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond: fails.append(name)

# --- 0. fixtures are prerequisites — absent means FAIL, not skip ---
check("fixture: results/amie.json exists", RESULT.exists())
check(f"fixture: traces/{SESSION}.trace.jsonl exists (run prefill.py)", TRACE.exists())
if fails:
    sys.exit(1)

# --- 1. pending_records: latest-wins + worst-first ordering ---
def rec(field, verify, human=None):
    return {"company": "c", "field": field,
            "run": {"session_id": "s", "generated_at": None},
            "agent": {"status": "found"},
            "machine": {"validate": "pass", "verify": verify}, "human": human}

records = [
    rec("a_confirmed", "confirmed"),
    rec("b_contradicted", "contradicted"),
    rec("c_null", None),
    rec("d_done", "contradicted"),                      # pending at first…
    rec("d_done", "contradicted", {"label": "fail"}),   # …then annotated: latest wins
]
pend, latest = app.pending_records(records)
check("latest-wins: annotated field not pending", all(r["field"] != "d_done" for r in pend))
check("pending count", len(pend) == 3)
check("worst-first: contradicted before null before confirmed",
      [r["field"] for r in pend] == ["b_contradicted", "c_null", "a_confirmed"])

# --- 2. append_human writes one JSONL line with a stamped human block ---
orig_ann = app.ANN
with tempfile.TemporaryDirectory() as td:
    app.ANN = Path(td) / "ann.jsonl"
    out = app.append_human(rec("x", None), "fail", "invented", "note here")
    lines = app.ANN.read_text().splitlines()
    check("append_human: exactly one line", len(lines) == 1)
    saved = json.loads(lines[0])
    check("append_human: label + failure_type persisted",
          saved["human"]["label"] == "fail" and saved["human"]["failure_type"] == "invented")
    check("append_human: annotated_at is stamped ISO-8601",
          saved["human"]["annotated_at"].startswith("20"))
app.ANN = orig_ann

# --- 3. trace join against the REAL amie trace ---
fetches, searches = app.load_trace(SESSION)
check("trace: research_fetch results extracted", len(fetches) >= 5)
check("trace: research_search queries extracted", len(searches) >= 1)
check("trace: amie.so homepage fetched", app._norm_url("https://amie.so/") in fetches)

doc = json.loads(RESULT.read_text())
found = {f: e for f, e in doc["datapoints"].items() if e.get("status") == "found"}
check("fixture: has found fields", len(found) > 0)

joined = {f: fetches.get(app._norm_url(e["source_url"])) for f, e in found.items()}
check("join: every found source_url matches a research_fetch (no invention in amie run)",
      all(v is not None for v in joined.values()))
# total_funding_usd cites startbase.com but the agent fetched www.startbase.com —
# the join must normalize www./scheme or this legit citation false-flags as invention
check("join: www.-prefix mismatch still joins (total_funding_usd)",
      joined["total_funding_usd"] is not None)

# tagline's quote is verbatim on amie.so — exact match must locate it
check("find_quote: verbatim quote located (tagline)",
      app.find_quote(joined["tagline"], found["tagline"]["evidence_quote"]) is not None)
# hq_location's quote is stitched ("Amie GmbH, Adalbertstraße…" vs the page's
# "Amie GmbH (…), located at Adalbertstraße…") — exact must fail, partial must hit
hq = found["hq_location"]
check("find_quote: stitched quote correctly NOT exact (hq_location)",
      app.find_quote(joined["hq_location"], hq["evidence_quote"]) is None)
partial = app.find_partial(joined["hq_location"], hq["evidence_quote"])
check("find_partial: stitched quote's real page region located (hq_location)",
      partial is not None and "Adalbertstra" in partial[1])
# website's quote is a pure description of the page, not text on it — both must fail
check("find_quote: paraphrased quote correctly NOT found (website)",
      app.find_quote(joined["website"], found["website"]["evidence_quote"]) is None)
check("find_quote: empty inputs return None", app.find_quote("", "x") is None)

# --- 4. prefill verdict parsing: a broken doc maps failures to fields ---
sys.path.insert(0, str(REPO))
import prefill
with tempfile.TemporaryDirectory() as td:
    bad = json.loads(RESULT.read_text())
    bad["datapoints"]["founding_year"]["value"] = "not-an-int"
    p = Path(td) / "bad.json"
    p.write_text(json.dumps(bad))
    v = prefill.validate_verdicts(p, prefill.catalog_fields())
    check("validate_verdicts: broken field fails", v["founding_year"] == "fail")
    check("validate_verdicts: intact field passes", v["website"] == "pass")

print()
if fails:
    print(f"{len(fails)} FAILED"); sys.exit(1)
print("all annotation-tool tests passed")
