#!/usr/bin/env python3
"""Schema validation for enrichment output. Dependency-free on purpose.

Usage: python3 validate.py results/<slug>.json
Exit 0 = valid. Exit 1 = invalid, with every violation printed (so the agent
can repair in one pass instead of one error at a time). Never silently passes:
a missing file or unparseable JSON is a loud failure.
"""
import json, sys

REQUIRED_FIELDS = [
    "website", "tagline", "pricing_model", "lowest_paid_price_usd",
    "platforms", "founding_year", "hq_location", "funding_status",
    "last_update_signal",
    "google_calendar_integration", "target_user",
    "total_funding_usd", "founders_background",
]
STATUSES = {"found", "unreachable", "not_disclosed"}
PRICING_ENUM = {"free", "freemium", "paid_only", "subscription"}
FUNDING_ENUM = {"bootstrapped", "funded", "acquired", "not_disclosed"}
PLATFORM_ENUM = {"mac", "ios", "windows", "android", "web", "linux"}

def fail(msgs):
    for m in msgs:
        print(f"INVALID: {m}")
    sys.exit(1)

if len(sys.argv) != 2:
    fail(["usage: validate.py <file.json>"])

try:
    doc = json.load(open(sys.argv[1]))
except Exception as e:
    fail([f"cannot parse JSON: {e}"])

errors = []
if not doc.get("company"):
    errors.append("missing top-level 'company'")
if not doc.get("generated_at"):
    errors.append("missing top-level 'generated_at'")

dp = doc.get("datapoints")
if not isinstance(dp, dict):
    fail(errors + ["missing or non-object 'datapoints'"])

for field in REQUIRED_FIELDS:
    if field not in dp:
        errors.append(f"datapoints.{field}: missing entirely")
        continue
    entry = dp[field]
    if not isinstance(entry, dict):
        errors.append(f"datapoints.{field}: must be an object")
        continue
    status = entry.get("status")
    if status not in STATUSES:
        errors.append(f"datapoints.{field}.status: '{status}' not in {sorted(STATUSES)}")
        continue
    if status == "found":
        if "value" not in entry or entry["value"] in (None, ""):
            errors.append(f"datapoints.{field}: status=found but no value")
        src = entry.get("source_url", "")
        if not isinstance(src, str) or not src.startswith(("http://", "https://")):
            errors.append(f"datapoints.{field}: status=found but source_url missing/invalid — a found value without a source is a failed delivery")
        # evidence_quote: the checkable handle verify.sh string-searches against the page.
        eq = entry.get("evidence_quote")
        if not isinstance(eq, str) or not eq.strip():
            errors.append(f"datapoints.{field}: status=found but no evidence_quote (the exact sentence from the page that states the value)")
        # retrieved_at: TOOL-stamped (research_fetch fetched_at), never model-written.
        ra = entry.get("retrieved_at")
        if not isinstance(ra, str) or not ra.strip():
            errors.append(f"datapoints.{field}: status=found but no retrieved_at (copy the fetched_at the research_fetch tool returned)")
        v = entry.get("value")
        if field == "pricing_model" and v not in PRICING_ENUM:
            errors.append(f"datapoints.pricing_model.value: '{v}' not in {sorted(PRICING_ENUM)}")
        if field == "funding_status" and v not in FUNDING_ENUM:
            errors.append(f"datapoints.funding_status.value: '{v}' not in {sorted(FUNDING_ENUM)}")
        if field == "platforms":
            if not isinstance(v, list) or not v or not set(v) <= PLATFORM_ENUM:
                errors.append(f"datapoints.platforms.value: must be non-empty subset of {sorted(PLATFORM_ENUM)}, got {v!r}")
        if field == "founding_year":
            if not isinstance(v, int) or not (1990 <= v <= 2026):
                errors.append(f"datapoints.founding_year.value: must be integer 1990-2026, got {v!r}")
        if field == "google_calendar_integration" and not isinstance(v, bool):
            errors.append(f"datapoints.google_calendar_integration.value: must be true/false, got {v!r}")
        if field == "total_funding_usd":
            if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
                errors.append(f"datapoints.total_funding_usd.value: must be number >= 0 (USD), got {v!r}")
        if field == "founders_background":
            if not isinstance(v, str) or not v.strip() or len(v.split()) > 60:
                errors.append(f"datapoints.founders_background.value: must be non-empty string <= 60 words, got {v!r}")

unknown = set(dp) - set(REQUIRED_FIELDS)
if unknown:
    errors.append(f"unknown datapoints present: {sorted(unknown)}")

if errors:
    fail(errors)
print("VALID")
