#!/usr/bin/env python3
"""Generic data fetcher: materialize a task file for any env that implements fetch().

Usage:
  python3 eval/fetch.py --env gsm8k --n 60 --out eval/data/gsm8k_test.jsonl
  python3 eval/fetch.py --env searchqa --n 80
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import envs as envs_pkg  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True)
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    env = envs_pkg.get_env(args.env)
    out = args.out or str(pathlib.Path(__file__).parent / "data" / ("%s.jsonl" % args.env))
    if not hasattr(env, "fetch"):
        print("env %s has no fetch(); provide a task file manually" % args.env)
        return
    env.fetch(args.n, out)


if __name__ == "__main__":
    main()
