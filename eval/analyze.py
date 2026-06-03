#!/usr/bin/env python3
"""Render the prequential learning curve from curve.csv as ASCII (no matplotlib).

Usage: python3 eval/analyze.py eval/out/haiku24/curve.csv [--metric preq_em]
"""
import argparse
import collections
import csv
import pathlib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("curve")
    ap.add_argument("--metric", default="preq_em", choices=["preq_em", "preq_f1"])
    ap.add_argument("--width", type=int, default=50)
    args = ap.parse_args()

    rows = list(csv.DictReader(pathlib.Path(args.curve).open()))
    by_method = collections.OrderedDict()
    for r in rows:
        by_method.setdefault(r["method"], []).append(r)

    print("\nPrequential %s vs task index (cumulative mean EM, test-then-train)\n" % args.metric)
    glyph = {"no_memory": ".", "ours_full": "#", "ace": "o", "skillopt": "x"}
    for m, rs in by_method.items():
        g = glyph.get(m, "*")
        print("  %-12s  legend '%s'" % (m, g))
    print()

    n = min(len(rs) for rs in by_method.values())
    for i in range(n):
        line = [" "] * (args.width + 1)
        cells = []
        for m, rs in by_method.items():
            v = float(rs[i][args.metric])
            col = int(round(v * args.width))
            line[col] = glyph.get(m, "*")
            cells.append((m, v))
        label = "  ".join("%s=%.2f" % (m[:4], v) for m, v in cells)
        print("t%-2d |%s| %s" % (i, "".join(line), label))
    print("    0%s1.0" % ("".ljust(args.width - 3)))

    print("\nFinal cumulative cost / bullets:")
    for m, rs in by_method.items():
        last = rs[-1]
        print("  %-12s cost=$%.4f  bullets=%s  %s=%.3f"
              % (m, float(last["cum_cost_usd"]), last["n_bullets"], args.metric, float(last[args.metric])))
    print()


if __name__ == "__main__":
    main()
