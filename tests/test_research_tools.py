#!/usr/bin/env python3
"""Offline contract + parsing tests for the research-tools plugin.
No network. Loads the live plugin module and drives its helpers with fakes.
Fails loudly; exits non-zero on any failure; never skips."""
import importlib.util, os, sys, json

PLUGIN = os.path.expanduser(
    "~/.hermes/profiles/autonomous-research-agent/plugins/research-tools/__init__.py")
spec = importlib.util.spec_from_file_location("rt", PLUGIN)
rt = importlib.util.module_from_spec(spec); spec.loader.exec_module(rt)

CA = os.path.expanduser("~/.hermes/agent-vault-ca.pem")
fails = []
def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if not cond: fails.append(name)

# --- 1. FAIL-CLOSED CONTRACT: _broker_pool must refuse unsafe configs ---
def refuses(env, needle):
    for k in ("HTTPS_PROXY","https_proxy","REQUESTS_CA_BUNDLE","AGENT_VAULT_TOKEN","FIRECRAWL_API_KEY"):
        os.environ.pop(k, None)
    os.environ.update(env)
    try:
        rt._broker_pool(); return False
    except RuntimeError as e:
        return needle.lower() in str(e).lower()

check("refuse when no proxy",
      refuses({"REQUESTS_CA_BUNDLE":CA,"AGENT_VAULT_TOKEN":"av_x","FIRECRAWL_API_KEY":"__firecrawl_key__"}, "HTTPS_PROXY"))
check("refuse when CA missing/not a file",
      refuses({"HTTPS_PROXY":"http://p","REQUESTS_CA_BUNDLE":"/nope","AGENT_VAULT_TOKEN":"av_x","FIRECRAWL_API_KEY":"__firecrawl_key__"}, "CA"))
check("refuse when no vault token",
      refuses({"HTTPS_PROXY":"http://p","REQUESTS_CA_BUNDLE":CA,"FIRECRAWL_API_KEY":"__firecrawl_key__"}, "AGENT_VAULT_TOKEN"))
check("refuse a REAL-looking fc- key on the Mac",
      refuses({"HTTPS_PROXY":"http://p","REQUESTS_CA_BUNDLE":CA,"AGENT_VAULT_TOKEN":"av_x","FIRECRAWL_API_KEY":"fc-real"}, "real"))

# positive: valid placeholder config builds a pool
for k in ("HTTPS_PROXY","https_proxy","REQUESTS_CA_BUNDLE","AGENT_VAULT_TOKEN","FIRECRAWL_API_KEY"): os.environ.pop(k, None)
os.environ.update({"HTTPS_PROXY":"http://tok@100.76.10.7:14322","REQUESTS_CA_BUNDLE":CA,
                   "AGENT_VAULT_TOKEN":"av_x","FIRECRAWL_API_KEY":"__firecrawl_key__"})
try:
    pool, key = rt._broker_pool()
    check("valid placeholder config builds a pool", key == "__firecrawl_key__")
except Exception as e:
    check(f"valid placeholder config builds a pool ({e})", False)

# --- 2. PARSING: monkeypatch _post with fixtures copied from the REAL API shapes seen 2026-08-19 ---
SEARCH_FIXTURE = {"success": True, "data": {"web": [
    {"title":"Amie - AI Note Taker","url":"https://amie.so/","description":"AI personal assistant."},
    {"title":"Amie on the App Store","url":"https://apps.apple.com/us/app/id1548277133","description":"Todos, calendar."},
]}}
SCRAPE_FIXTURE = {"success": True, "data": {
    "markdown":"# Amie\n\nRun your workday on autopilot.",
    "metadata":{"title":"Amie - AI Note Taker","url":"https://amie.so/","statusCode":200}}}

_orig_post = rt._post
rt._post = lambda path, body: SEARCH_FIXTURE
out = rt._search("amie", 2)
check("search: includes result titles", "Amie - AI Note Taker" in out)
check("search: includes result URLs", "https://amie.so/" in out)

rt._post = lambda path, body: SCRAPE_FIXTURE
out = rt._fetch("https://amie.so")
check("fetch: emits source_url header line", "source_url: https://amie.so/" in out)
check("fetch: includes the page markdown", "Run your workday on autopilot" in out)
check("fetch: includes status_code", "status_code: 200" in out)
rt._post = _orig_post

# fetch must reject a non-absolute URL before any network
try:
    rt._fetch("amie.so"); check("fetch: rejects non-http URL", False)
except RuntimeError as e:
    check("fetch: rejects non-http URL", "absolute" in str(e).lower())

# --- 3. ERROR DECODER: fake urllib3 responses -> friendly messages ---
class FakeResp:
    def __init__(self, status, data): self.status=status; self.data=data
def fake_pool(status, data):
    def _bp():
        class P:
            def request(self,*a,**k): return FakeResp(status, data)
        return P(), "__firecrawl_key__"
    return _bp
rt._broker_pool = fake_pool(407, b'')
try: rt._post("/search", {}); check("decoder: 407 mentions proxy auth", False)
except RuntimeError as e: check("decoder: 407 mentions proxy auth", "407" in str(e) and "auth" in str(e).lower())
rt._broker_pool = fake_pool(403, b'{"error":"service_disabled"}')
try: rt._post("/search", {}); check("decoder: 403 surfaces broker body", False)
except RuntimeError as e: check("decoder: 403 surfaces broker body", "service_disabled" in str(e))

print(f"\n{'ALL PASSED' if not fails else str(len(fails))+' FAILED: '+', '.join(fails)}")
sys.exit(1 if fails else 0)
