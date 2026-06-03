#!/usr/bin/env python3
"""Materialize a small SearchQA task stream from the HF datasets-server REST API.

No `datasets` lib needed. Writes eval/data/searchqa_val.jsonl with rows:
  {"id": <key>, "question": str, "context": str, "answers": [str, ...]}

Usage: python3 eval/fetch_searchqa.py --n 80 [--split validation] [--ctx 5000]
"""
import argparse
import json
import pathlib
import time
import urllib.request

DATASET = "lucadiliello/searchqa"
BASE = "https://datasets-server.huggingface.co/rows"


def fetch_page(split, offset, length):
    url = "%s?dataset=%s&config=default&split=%s&offset=%d&length=%d" % (
        BASE, DATASET.replace("/", "%2F"), split, offset, length
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=80)
    ap.add_argument("--split", default="validation")
    ap.add_argument("--ctx", type=int, default=5000, help="truncate context chars")
    ap.add_argument("--out", default=str(pathlib.Path(__file__).parent / "data" / "searchqa_val.jsonl"))
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows, offset = [], 0
    while len(rows) < args.n:
        length = min(100, args.n - len(rows))
        page = fetch_page(args.split, offset, length)
        batch = page.get("rows", [])
        if not batch:
            break
        for entry in batch:
            row = entry.get("row", {})
            ans = row.get("answers") or []
            if isinstance(ans, str):
                ans = [ans]
            rec = {
                "id": row.get("key") or row.get("id") or ("row-%d" % offset),
                "question": row.get("question", ""),
                "context": (row.get("context", "") or "")[: args.ctx],
                "answers": [a for a in ans if a],
            }
            if rec["question"] and rec["answers"]:
                rows.append(rec)
            offset += 1
        time.sleep(0.3)

    with out.open("w", encoding="utf-8") as f:
        for r in rows[: args.n]:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("wrote %d tasks -> %s" % (min(len(rows), args.n), out))


if __name__ == "__main__":
    main()
