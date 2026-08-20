#!/bin/bash
# Driver for the shell-free research agent.
#
# THE TRUST BOUNDARY: this script (Emily's code) holds the shell — sqlite3 (queue) and
# python3 (validate.py). The AGENT never gets a terminal. Per company, the driver:
#   claim (sqlite) -> invoke agent (research + write 2 files, no shell) -> validate -> mark.
# The agent's toolset is `-t research,file` only. See AGENT-FUNDAMENTALS.md §5/§8 and
# PLAN.md "The driver model".
#
# Usage:
#   ./run.sh              # process the whole queue on the profile default model
#   MODEL=deepseek/deepseek-v4-flash ./run.sh   # cheaper model for iteration
#   MODEL=moonshotai/kimi-k3 ./run.sh           # the one K3 run (confirm slug via `hermes model list`)
set -euo pipefail
cd "$(dirname "$0")"
export PATH="$HOME/.local/bin:$HOME/.hermes/bin:$PATH"

REPO="$(pwd)"
AGENT="autonomous-research-agent"          # the profile alias wrapper (-> hermes -p ...)
MODEL="${MODEL:-}"                          # empty = profile default (deepseek-v4-pro)
MAX_TURNS="${MAX_TURNS:-60}"
REASONING="${REASONING:-medium}"
model_flag=(); [ -n "$MODEL" ] && model_flag=(-m "$MODEL")

# --- reclaim stale claims from a crashed run (host holds the shell) ---
sqlite3 queue.db "UPDATE companies SET status='waiting', note='reclaimed stale' \
  WHERE status='in_progress' AND claimed_at < datetime('now','-20 minutes');"
echo "== queue at start =="
sqlite3 -header -column queue.db "SELECT status, COUNT(*) AS n FROM companies GROUP BY status;"

while :; do
  # claim ONE company atomically; capture name + website_hint (pipe-separated)
  row=$(sqlite3 queue.db "UPDATE companies SET status='in_progress', claimed_at=datetime('now') \
    WHERE id=(SELECT id FROM companies WHERE status='waiting' ORDER BY id LIMIT 1) \
    RETURNING name || '|' || COALESCE(website_hint,'');")
  [ -z "$row" ] && { echo "== queue empty =="; break; }

  name="${row%%|*}"
  hint="${row#*|}"
  slug="$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]' | tr ' ' '-' | tr -cd 'a-z0-9-')"
  echo ""; echo "== $name  (slug: $slug) =="
  start=$(python3 -c 'import time;print(int(time.time()))')

  # assemble the agent prompt: static instructions + the THIS RUN block, via stdin.
  # The agent researches + writes the two files. No shell, no queue, no validate.
  {
    cat AGENT-INSTRUCTIONS.md
    printf '\n\nCompany: %s\nWebsite hint: %s\nWrite JSON to: results/%s.json\nWrite dossier to: dossiers/%s.md\n' \
      "$name" "$hint" "$slug" "$slug"
  } | "$AGENT" chat --query-file - -Q --yolo \
        -t research,file --max-turns "$MAX_TURNS" --reasoning "$REASONING" \
        "${model_flag[@]}" --in "$REPO" || echo "  (agent invocation returned non-zero — continuing)"

  # --- validate + mark (host holds the shell) ---
  end=$(python3 -c 'import time;print(int(time.time()))')
  secs=$((end - start))
  if [ -f "results/$slug.json" ] && python3 validate.py "results/$slug.json"; then
    sqlite3 queue.db "UPDATE companies SET status='done', completed_at=datetime('now'), \
      note='ok (${secs}s)' WHERE name='$name';"
    echo "  DONE  ${secs}s"
  else
    sqlite3 queue.db "UPDATE companies SET status='failed', \
      note='no valid results/$slug.json (${secs}s)' WHERE name='$name';"
    echo "  FAILED  ${secs}s  (missing or invalid results/$slug.json)"
  fi
done

echo ""; echo "== end of run =="
sqlite3 -header -column queue.db "SELECT name, status, note FROM companies ORDER BY id;"
echo "-- datapoint outcomes across all done companies --"
python3 - <<'PY'
import json, glob, collections
c = collections.Counter()
for f in glob.glob("results/*.json"):
    try:
        dp = json.load(open(f)).get("datapoints", {})
        for v in dp.values():
            c[v.get("status","?")] += 1
    except Exception:
        pass
for k in ("found","unreachable","not_disclosed"):
    print(f"  {k}: {c.get(k,0)}")
PY
