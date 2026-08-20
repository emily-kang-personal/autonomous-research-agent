#!/usr/bin/env python3
"""Live tests through the Agent Vault broker. Requires the profile .env sourced.
Fails loudly if the broker/services aren't reachable — it never skips, because a
missing prerequisite here means the run itself would fail.

Run:
  set -a; . ~/.hermes/profiles/autonomous-research-agent/.env; set +a
  ~/.hermes/hermes-agent/venv/bin/python tests/test_research_tools_live.py
"""
import importlib.util, os, sys, json, urllib3

PLUGIN = os.path.expanduser(
    "~/.hermes/profiles/autonomous-research-agent/plugins/research-tools/__init__.py")
spec = importlib.util.spec_from_file_location("rt", PLUGIN)
rt = importlib.util.module_from_spec(spec); spec.loader.exec_module(rt)

for req in ("HTTPS_PROXY","REQUESTS_CA_BUNDLE","AGENT_VAULT_TOKEN"):
    if not os.environ.get(req):
        print(f"FAIL: {req} not set — source the profile .env first. This test does NOT skip.")
        sys.exit(1)

fails = []
def check(name, cond, extra=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}  {extra}")
    if not cond: fails.append(name)

# 1. research_search returns real, shaped results with URLs
try:
    out = rt._search("Amie calendar app", 3)
    check("live search returns results with a URL", "http" in out and "amie" in out.lower(), out[:80])
except Exception as e:
    check("live search returns results with a URL", False, str(e)[:120])

# 2. research_fetch returns markdown + a real source_url, status 200
try:
    out = rt._fetch("https://amie.so")
    check("live fetch returns source_url + markdown",
          "source_url: http" in out and "status_code: 200" in out and len(out) > 200, f"len={len(out)}")
except Exception as e:
    check("live fetch returns source_url + markdown", False, str(e)[:120])

# 3. DENIAL REGRESSION: a host with NO service row MUST be blocked by the broker (deny intact)
tok=os.environ["AGENT_VAULT_TOKEN"]; ca=os.environ["REQUESTS_CA_BUNDLE"]
ph=urllib3.make_headers(proxy_basic_auth=f"{tok}:")
pm=urllib3.ProxyManager("http://100.76.10.7:14322", proxy_headers=ph, ca_certs=ca)
try:
    r=pm.request("GET","https://example.com", timeout=12, retries=False)
    check("broker DENIES a non-allowlisted host (deny intact)", r.status == 403, f"status={r.status}")
except urllib3.exceptions.MaxRetryError as e:
    # a 403 CONNECT surfaces as ProxyError — that is also a pass (denied)
    check("broker DENIES a non-allowlisted host (deny intact)", "403" in str(e), "ProxyError(403)")

# 4. OpenRouter model call reaches DeepSeek
try:
    r=pm.request("POST","https://openrouter.ai/api/v1/chat/completions",
      body=json.dumps({"model":"deepseek/deepseek-v4-pro",
        "messages":[{"role":"user","content":"reply with only the word OK"}],"max_tokens":5}).encode(),
      headers={"Content-Type":"application/json"}, timeout=30, retries=False)
    ok = r.status==200 and "OK" in json.loads(r.data)["choices"][0]["message"]["content"]
    check("openrouter model call reaches DeepSeek", ok, f"status={r.status}")
except Exception as e:
    check("openrouter model call reaches DeepSeek", False, str(e)[:120])

print(f"\n{'ALL PASSED' if not fails else str(len(fails))+' FAILED: '+', '.join(fails)}")
sys.exit(1 if fails else 0)
