# Tests

Discipline: dependency-light, every failure printed, non-zero exit on any failure,
**no skip-on-missing-prerequisite** — a missing token/proxy makes a test FAIL loudly,
never "skip".

Run with the Hermes profile venv, from the repo root:

```bash
# A) offline — contract + parsing + error decoder (no network)
~/.hermes/hermes-agent/venv/bin/python tests/test_research_tools.py

# B) live — through the Agent Vault broker (source the profile .env first)
set -a; . ~/.hermes/profiles/autonomous-research-agent/.env; set +a
~/.hermes/hermes-agent/venv/bin/python tests/test_research_tools_live.py
```

- `test_research_tools.py` — offline. Fail-closed contract (refuses no-proxy / bad-CA /
  no-token / real-looking `fc-` key), response parsing against fixtures copied from the
  real Firecrawl v2 shapes, and the 407/403 broker error decoder. **13 checks.**
- `test_research_tools_live.py` — network, through the broker. Real search + fetch shape,
  the **deny regression** (a non-allowlisted host must 403 — proves the egress boundary),
  and DeepSeek reachability via OpenRouter.

## C) Agent-behavioral (manual, run in Hermes) — does the AGENT actually use the tools?

The two files above prove the tool CODE works. This proves the agent CALLS them and cites
real URLs (not hallucinated). See PLAN.md "Tests for the research tools" §C for the full
steps; in brief:

1. One-shot forcing tool use:
   `autonomous-research-agent chat -q "Using ONLY research_search and research_fetch ... find Amie's website and pricing model, give the source_url for each fact ..." --in <repo>`
2. Prove the tools fired (not hallucinated), from the profile state.db:
   `sqlite3 ~/.hermes/profiles/autonomous-research-agent/state.db "SELECT tool_name, COUNT(*) FROM messages WHERE session_id=(SELECT id FROM sessions ORDER BY rowid DESC LIMIT 1) AND role='assistant' AND tool_calls IS NOT NULL GROUP BY tool_name;"`
   PASS = research_search / research_fetch appear with count >= 1.
3. Every cited URL must be one the agent really fetched (anti-fabrication) — list the URLs
   passed to research_fetch in that session and confirm each cited source_url is among them.
