#!/bin/bash
# Creates and seeds the work queue. Rerunnable: drops nothing, skips existing rows.
set -euo pipefail
cd "$(dirname "$0")"

sqlite3 queue.db <<'SQL'
CREATE TABLE IF NOT EXISTS companies (
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  website_hint TEXT,
  status TEXT NOT NULL DEFAULT 'waiting',  -- waiting | in_progress | done | failed
  claimed_at TEXT,
  completed_at TEXT,
  note TEXT
);

INSERT OR IGNORE INTO companies (name, website_hint) VALUES
  ('Fantastical', 'flexibits.com'),
  ('Notion Calendar', 'notion.com'),
  ('Amie', 'amie.so'),
  ('Vimcal', 'vimcal.com'),
  ('Morgen', 'morgen.so'),
  ('Akiflow', 'akiflow.com'),
  ('Sunsama', 'sunsama.com'),
  ('Structured', 'structured.app');
SQL

echo "Queue state:"
sqlite3 -header -column queue.db "SELECT id, name, status FROM companies ORDER BY id;"
