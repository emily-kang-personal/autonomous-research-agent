# Sandbox image for the Hermes terminal backend (terminal.backend: docker).
# Stock nikolaik/python-nodejs lacks the sqlite3 CLI, which AGENT-INSTRUCTIONS.md
# and run.sh depend on. Build: docker build -f sandbox.Dockerfile -t hermes-research:latest .
FROM nikolaik/python-nodejs:python3.11-nodejs20
RUN apt-get update && apt-get install -y --no-install-recommends sqlite3 && rm -rf /var/lib/apt/lists/*
