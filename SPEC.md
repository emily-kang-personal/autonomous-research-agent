# Autonomous Company Research Agent — Spec

The stable **WHAT**: what the system does and what correct output is. (PLAN.md is the
HOW/sequencing; this is the contract.) Canonical machine-readable pieces live in
`catalog.md` (datapoints) and `schema.json` (output shape) — referenced here, never
duplicated.

## 1. Purpose

Enrich a queue of companies against a defined datapoint catalog, fully cited, unattended —
never inventing a value. Every filled datapoint traces to a public page that states it.

## 2. Inputs

- **Company queue** — `queue.db` `companies` table: `name`, `website_hint`, `status`
  (`waiting | in_progress | done | failed`), `claimed_at`, `completed_at`, `note`.
- **Datapoint catalog** — `catalog.md` (canonical: each field's type, authoritative source
  class, collection rule). 13 fields today; the catalog is the single source of truth.

## 3. Affordances — the agent's capability surface

The agent's behavior is bounded entirely by this. The negative space (what it *can't* do)
is as much a part of the contract as the tools.

### 3a. Tools (the action space)

- **`research_search(query) -> text`** — Firecrawl `/v2/search` via the vault broker.
  Returns a numbered list of `{title, url, description}`. Broker-allowlisted hosts only;
  fail-closed (no proxy/CA → refuses); 1–10 results.
- **`research_fetch(url) -> text`** — Firecrawl `/v2/scrape`, fresh (`maxAge:0`), via the
  broker. Returns a header `{source_url, title, status_code, fetched_at}` + page markdown
  (≤60k chars). **`fetched_at` is TOOL-STAMPED UTC — the only trustworthy "now" the agent
  has.** Public pages only (paywall/login → fails); errors raise with a 407/403 broker
  decoder message.
- **`read_file(path) -> text`** — reads anywhere in the repo EXCEPT credential files
  (`.env`, `auth.json` are read-blocked by Hermes).
- **`write_file(path, content)`** — HARD-BLOCKED outside the repo (`HERMES_WRITE_SAFE_ROOT`).
  The only place artifacts are written.

### 3b. Environment & boundaries

- **Network:** ONLY broker-allowlisted hosts. No direct internet.
- **Filesystem:** read = repo minus credential files; write = repo only.
- **No shell / terminal** — the agent cannot run commands; that is the driver's job.
- **No sub-agent delegation** (V1).
- **Memory:** working memory = the growing conversation within one invocation. No long-term
  memory (V1).

### 3c. Runtime

Harness Hermes (native tool-calling loop) · model DeepSeek V4 Pro · `max_turns` 60 ·
reasoning `medium` · toolset `-t research,file`. One agent invocation per company.

## 4. Output contract

Per company, the agent writes two files (see `schema.json` for the exact JSON shape):

- **`results/<slug>.json`** — `{company, generated_at, datapoints}`. `datapoints` is an
  object with all 13 catalog fields. Each field is an envelope:
  `{status, value?, source_url?, evidence_quote?, retrieved_at?, note?}`.
  - **`found`** requires `value` + `source_url` + `evidence_quote` (exact ≤1-sentence text
    from the page — a checkable handle, re-verified later) + `retrieved_at` (the tool's
    `fetched_at`, copied verbatim).
  - **`unreachable`** — a source should exist but couldn't be read; `note` records the URL
    tried.
  - **`not_disclosed`** — no public source states it. (Never "it isn't so.")
- **`dossiers/<slug>.md`** — human-readable table of the 13 fields (value, outcome, source),
  generated from the JSON.
- **`results/<slug>.verify.json`** — independent verify verdicts (§10). Never merged into the
  agent's own output; that separation is the independence.

## 5. Behavioral rules / invariants

- **Never invent a value.** A guess recorded as `found` is the worst possible failure.
- **Cite from the authoritative source class** (catalog column 3); the cited page must
  actually state the value.
- **Public web only** — no logins, paywalls, or LinkedIn.
- **Tool-stamped timestamps only.** `retrieved_at` and top-level `generated_at` come from a
  tool/driver, never model-written — the model does not know the time and will hallucinate
  it.
- **Degrade, never crash.** One bad field never stops a company; one bad company never stops
  the run.
- **Reason free, record structured.** Do NOT force structured output on the model's
  *reasoning* — free reasoning (weighing sources, reconciling conflicts, holding
  uncertainty) is where research judgment happens; forcing it into JSON produces confident
  wrong answers. DO force structure on the *output record* — each datapoint is committed in
  a schema-defined shape (tool-guaranteed, not free-text JSON). Force the output shape,
  never the thinking.

## 6. Failure semantics

- **Tool error** → retry; after two failures, mark the field `unreachable` (never crash).
- **`max_turns` hit** → write the JSON with whatever is filled; the driver marks the company
  `failed` if no valid file exists.
- **Broker/token failure** → every fetch fails → an all-`unreachable` result. Schema-valid
  but suspicious — caught by the §7 guard.
- **Crash mid-company** → the queue reclaims the stale claim; at most one company is lost.

## 7. Run model / orchestration

`run.sh` is the driver and holds the shell (the agent does not): reclaim stale claims →
claim one company (sqlite) → invoke the agent (research + write two files) → `validate.py` →
mark `done`/`failed` (sqlite). Resume-after-crash via queue state; unattended.

- **`generated_at` is driver-stamped** (real UTC), not model-written.
- **Guard:** a company whose result has **0 `found` fields** is flagged suspicious (likely a
  broker/plumbing failure), not silently marked `done`.

## 8. Security model

- **Keys never live on the Mac** — the agent holds placeholders; the vault broker injects
  real keys in flight.
- **Egress = the broker's service allowlist**, deny-by-default.
- **Writes jailed to the repo**; reads block credential files.
- **Local-today gap (accepted):** without a container, shell and reads are not jailed —
  closed by the docker/Daytona move (next phase). Writes and egress ARE bounded today.

## 9. Observability

Every tool call — every query and fetched URL the model chose — is captured in the profile's
`state.db` (`messages` table, incl. `tool_calls`). This is the audit trail: the record of
the agent's real, autonomous choices.

- Live: `hermes logs -f --session <id>`.
- After: `hermes sessions export --format trace` (HF Agent Trace Viewer) / `--format html`.

Inspecting what the agent actually did is part of the contract, not optional.

## 10. Verification & acceptance

- **`validate.py`** — deterministic gate: schema, types, enums, ranges, and that `found`
  carries value + source_url + evidence_quote + retrieved_at.
- **`verify.sh`** — independent cite-check on a FRESH context (never the researching
  session), one verdict per `found` field: `confirmed` / `contradicted` (quote not on the
  page — the invention catch) / `unverifiable` (couldn't re-fetch after retries — a
  human-review flag, never a silent pass/fail).
- **Acceptance:** every `found` value carries a re-checkable source; output validates; a
  mid-run kill resumes cleanly.

**Evaluation model — evaluate the DATAPOINT, not the trajectory (decision).** A closed
question set (the catalog) + per-datapoint provenance (`source_url` + `evidence_quote`)
means each datapoint is an independently checkable unit — so we do NOT attempt trajectory
"failure attribution" (finding the first decisive error step in a many-turn, many-source
run — a hard, unsolved research frontier). The error-analysis flywheel:
1. **Analyze** — sample real datapoints across companies and read them.
2. **Measure** — categorize failures by FIELD (which datapoint fails often) and by TYPE
   (invented / wrong-source / stale-source / gave-up-early / wrong-value — `stale-source`:
   the cited page really states the value, but a fresher public source supersedes it; the
   agent trusted one article without cross-checking recency. First observed in the amie
   run, 2026-08-20). The datapoint is the annotation
   unit — never the conversation.
3. **Improve** — change the prompt/tools; re-measure against the categorized failures.
4. **Regression** — freeze evaluators (e.g. verify.sh, per-field checks) so a fix for one
   failure mode doesn't reintroduce another.
Evals are *earned* through this loop (human review + annotation of ~100 real datapoints),
not generated. The trace is a **drill-down diagnostic** used only on datapoints that
already failed output-level analysis (to learn *why*), never the primary eval.

## 11. Constraints & non-goals

- **Model constraint:** the reasoning model is DeepSeek or Kimi (client requirement; hard).
- **No paid data vendors** for the client deliverable (public web only). Own-use may differ.
- **Non-goals:** not real-time; not a chatbot; does not verify claims it cannot re-fetch;
  does not corroborate across sources in V1 (single-source + cite-check only).
