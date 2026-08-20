#!/usr/bin/env python3
"""Prefill pending annotation records for one company run. Dependency-free on purpose.

Usage: python3 prefill.py <slug> --session-id <hermes-session-id> [--trace <trace.jsonl>]

Per Docs/annotation-spec.md: appends one pending record per catalog field to
annotations/annotations.jsonl (machine verdicts filled, human: null) and places the
session trace at traces/<session_id>.trace.jsonl for the annotator UI.
Idempotent: fields that already have a record for (company, field, session_id) are
skipped. A missing prerequisite is a loud failure, never a silent skip.
"""
import argparse, json, shutil, subprocess, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent
ANN = REPO / "annotations" / "annotations.jsonl"
TRACES = REPO / "traces"


def catalog_fields():
    # schema.json is the canonical field list (SPEC: catalog.md/schema.json, never duplicated)
    schema = json.loads((REPO / "schema.json").read_text())
    return schema["properties"]["datapoints"]["required"]


def validate_verdicts(result_path, fields):
    """Run validate.py; map each field to pass/fail from its violation lines."""
    proc = subprocess.run(
        [sys.executable, str(REPO / "validate.py"), str(result_path)],
        capture_output=True, text=True,
    )
    out = proc.stdout + proc.stderr
    if proc.returncode == 0:
        return {f: "pass" for f in fields}
    verdicts = {f: ("fail" if f"datapoints.{f}" in out else "pass") for f in fields}
    # top-level violations (company/generated_at/datapoints) don't map to a field;
    # surface them so a broken file never prefills quietly
    unmapped = [l for l in out.splitlines() if l.startswith("INVALID") and "datapoints." not in l]
    for l in unmapped:
        print(f"WARNING: file-level validation failure (not attributed to a field): {l}")
    return verdicts


def verify_verdicts(slug, fields):
    p = REPO / "results" / f"{slug}.verify.json"
    if not p.exists():
        return {f: None for f in fields}  # verify.sh not run — spec allows null
    doc = json.loads(p.read_text())
    return {f: doc.get(f, {}).get("verdict") if isinstance(doc.get(f), dict) else doc.get(f)
            for f in fields}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slug")
    ap.add_argument("--session-id", required=True)
    ap.add_argument("--trace", help="existing trace export to copy into traces/")
    args = ap.parse_args()

    result_path = REPO / "results" / f"{args.slug}.json"
    if not result_path.exists():
        sys.exit(f"FATAL: {result_path} does not exist — nothing to prefill")
    doc = json.loads(result_path.read_text())
    fields = catalog_fields()

    TRACES.mkdir(exist_ok=True)
    trace_dst = TRACES / f"{args.session_id}.trace.jsonl"
    if args.trace:
        shutil.copyfile(args.trace, trace_dst)
    elif not trace_dst.exists():
        sys.exit(
            f"FATAL: no trace at {trace_dst} and no --trace given. Export one:\n"
            f"  hermes sessions export --format trace --session-id {args.session_id} {trace_dst}"
        )

    validate_v = validate_verdicts(result_path, fields)
    verify_v = verify_verdicts(args.slug, fields)

    ANN.parent.mkdir(exist_ok=True)
    existing = set()
    if ANN.exists():
        for line in ANN.read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            existing.add((r["company"], r["field"], r["run"]["session_id"]))

    appended = 0
    with ANN.open("a") as f:
        for field in fields:
            key = (args.slug, field, args.session_id)
            if key in existing:
                continue
            record = {
                "company": args.slug,
                "field": field,
                "run": {"session_id": args.session_id,
                        "generated_at": doc.get("generated_at")},
                "agent": doc["datapoints"].get(field, {"status": "missing"}),
                "machine": {"validate": validate_v[field], "verify": verify_v[field]},
                "human": None,
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            appended += 1

    skipped = len(fields) - appended
    print(f"prefilled {appended} pending records for {args.slug} "
          f"(session {args.session_id}); {skipped} already existed; trace: {trace_dst}")


if __name__ == "__main__":
    main()
