# Annotation Spec — per-datapoint pass/fail ground truth

The durable record of human eval decisions for the SPEC §10 error-analysis flywheel.
The **datapoint is the annotation unit** (never the conversation/trajectory). This file
defines where annotations live, their exact shape, and the lifecycle that produces them.

## 1. Three layers — only one is human-written

| Layer | Artifact | Who writes it | Lifetime |
|---|---|---|---|
| Machine verdicts | `validate.py` exit status; `results/<slug>.verify.json` | tools, every run | regenerated — never hand-edited |
| **Human annotations** | `annotations/annotations.jsonl` | human, via the annotator UI | **durable, append-only, git-versioned** |
| Annotator UI | `annotate_app.py` (Streamlit, local) | generated view | disposable — holds NO state |

The UI is a *render* of layers 1+2 plus a writer of `human` blocks — and it is swappable
(Streamlit today; anything tomorrow) precisely BECAUSE the store contract is fixed. Any
decision recorded only in a view (page state, localStorage, screenshot) is lost by design;
decisions go in the JSONL or they didn't happen.

## 2. Store

`annotations/annotations.jsonl` — one JSON object per line, append-only, committed to git.

JSONL (not SQLite) because this file **is the eval dataset**: it gets diffed, grepped,
reviewed in PRs, and eventually frozen as the regression set. Run-state stays in `queue.db`;
ground truth stays in git.

## 3. Record identity: `(company, field, run)`

One record judges **one field of one company as produced by one specific agent invocation**.

- `company` — the queue slug (matches `results/<slug>.json`).
- `field` — one of the 13 catalog fields (`validate.py` `REQUIRED_FIELDS`).
- `run` — the specific invocation, **keyed by the Hermes `session_id` alone**.
  `generated_at` is carried in the record as informational context but is NOT part of the
  key: today it is model-written and untrustworthy (the first successful run,
  `20260820_042851_6906fb`, wrote a suspiciously-round `generated_at` ~9 min before the
  real finish, because the raw CLI command bypassed `run.sh` and `run.sh` does not yet
  driver-stamp it). Per-field `retrieved_at` IS trustworthy — it's tool-stamped by
  `research_fetch`'s `fetched_at`.

`run` is load-bearing: companies get re-run, and an annotation is a judgment of one
*attempt*, not of the company. Without the run binding, a re-run would silently invalidate
existing labels. Keying by all three means old annotations stay true forever and a fresh
run simply gets fresh pending records.

## 4. Record shape

```json
{
  "company": "acme",
  "field": "founding_year",
  "run": {
    "session_id": "20260820_042851_6906fb",
    "generated_at": "2026-08-20T11:30:00Z"
  },
  "agent": {
    "status": "found",
    "value": 2019,
    "source_url": "https://acme.com/about",
    "evidence_quote": "Founded in 2019 by ...",
    "retrieved_at": "2026-08-19T14:52:10Z"
  },
  "machine": {
    "validate": "pass",
    "verify": "contradicted"
  },
  "human": {
    "label": "fail",
    "failure_type": "invented",
    "note": "quote not on the page; year only appears in a third-party blog",
    "annotator": "emily",
    "annotated_at": "2026-08-20T18:02:11Z"
  }
}
```

### Field semantics

- **`agent`** — a verbatim SNAPSHOT of the datapoint envelope from `results/<slug>.json`.
  Snapshotting (not referencing) makes each record self-contained: the eval dataset
  survives `results/*.json` being overwritten by the next run.
- **`machine.validate`** — `pass | fail`, from `validate.py` on the result file (fail =
  this field appeared in its violation output).
- **`machine.verify`** — `confirmed | contradicted | unverifiable`, copied from
  `results/<slug>.verify.json`; `null` for non-`found` fields (verify.sh only cite-checks
  `found`). NOTE: `verify.sh` is specified in SPEC §10 but not built yet — until it exists,
  `machine.verify` is `null` everywhere and annotation triage falls back to field order.
  The verify prefill is what makes the human pass FAST (jump straight to `contradicted`),
  so build verify.sh before demo-day annotation.
- **`human.label`** — `pass | fail | unclear`. The ground-truth call. `unclear` exists on
  purpose: forcing a binary call on genuinely ambiguous datapoints corrupts the dataset.
- **`human.failure_type`** — SPEC §10 taxonomy, only when `label` is `fail`:
  `invented | wrong-source | stale-source | gave-up-early | wrong-value`.
  `stale-source` (added 2026-08-20 from the amie run): the cited page really states the
  value, but a fresher source supersedes it — the single-source-trust failure mode.
  Distinct from `wrong-source` (wrong source class) and `wrong-value` (misread page).
- **`human.note`** — optional free text; required for `unclear`.
- **`human.annotated_at`** — stamped by the annotator UI (real clock), never typed.
- A **pending** record is one with `"human": null` — prefilled at run end, waiting for
  a human.

## 5. Rules / invariants

- **Append-only.** A changed mind is a NEW record for the same `(company, field, run)`;
  latest `annotated_at` wins on read. Never edit or delete lines.
- **All 13 fields get a record per run** — not just `found`. A `not_disclosed` that was
  actually public is the `gave-up-early` failure mode, catchable only by a human.
- **Machine artifacts are never hand-edited.** Disagreement with `machine.verify` is
  expressed via `human.label`, which doubles as a measurement of verify.sh itself
  (precision/recall of the automated cite-check against human ground truth).
- **Humans write only the `human` block.** Everything else is prefilled by tooling.

## 6. Lifecycle

1. **Prefill** — after `run.sh` finishes a company, `prefill.py` appends 13 pending
   records (machine verdicts filled, `human: null`) and exports the session trace.
   Trace source: `hermes sessions export --format trace --session-id <id>` — full
   `research_fetch` page markdown survives export, BUT single tool results are capped
   (`tool_output.max_bytes: 50000`; `research_fetch` also truncates at 60k chars). So:
   a quote missing from the trace *text* is possibly just truncation — render it as
   "quote not shown (truncated)", never as an invention flag. The invention flag is
   ONLY a `source_url` that matches no `research_fetch` call (URLs live in call args,
   which are never truncated).
2. **Annotate** — `annotate_app.py` (local Streamlit: `streamlit run annotate_app.py`)
   walks pending records worst-first (`contradicted`, then `unverifiable`, then the rest),
   one datapoint per screen: the envelope, machine badges, the `evidence_quote`
   highlighted inside the fetched page markdown from the trace (join key `source_url` ↔
   `research_fetch` call args; truncation caveat above), and a source link. Buttons:
   Pass / Fail (+ failure-type picker) / Unclear (+ required note) → append the record,
   auto-advance. Sidebar: company/run picker with pending counts. Designed to be FAST —
   the demo-video ending: a run finishes, a few clicks, done.
3. **Measure** — aggregate the JSONL: failure counts by FIELD × by TYPE (SPEC §10 step 2).
4. **Freeze** — at ~100 annotated records, tag the file as the regression set; evaluator
   changes are thereafter scored against it.

## 7. Non-goals

- No trajectory-level annotation (per SPEC §10, failure attribution over many-turn runs is
  explicitly out of scope; the trace is drill-down context only).
- No annotation UI with its own storage — the JSONL is the single store. The Streamlit
  app keeps only ephemeral navigation state (`st.session_state`); every judgment is an
  immediate JSONL append, so killing the app mid-pass loses nothing.
