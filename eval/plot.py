#!/usr/bin/env python3
"""Pure-Python SVG plots from an eval run dir (no matplotlib).

Reads <outdir>/runs/<method>_seed<k>/tasks.jsonl, aggregates across seeds
(mean + min/max band), and writes:
  <outdir>/fig_learning_curve.svg   prequential EM vs task index
  <outdir>/fig_acc_vs_cost.svg      prequential EM vs cumulative cost (C2 axes)

Generic over methods — new baselines are picked up automatically.

Usage: python3 eval/plot.py eval/out/haiku24
"""
import argparse
import collections
import json
import pathlib

COLORS = {
    "no_memory": "#888888",
    "ours_full": "#1f77b4",
    "ours_mem": "#17becf",
    "episodic": "#2ca02c",
    "ace": "#ff7f0e",
    "external_optimizer": "#9467bd",
    "skillopt": "#9467bd",
}
ORDER = ["no_memory", "external_optimizer", "skillopt", "ace", "episodic", "ours_mem", "ours_full"]
LABEL = {
    "no_memory": "no-memory (lower bound)",
    "ours_full": "ours-full (episodic+distilled+gated skill)",
    "ours_mem": "ours-mem (distilled retrieval)",
    "episodic": "episodic (raw exemplars)",
    "ace": "ACE (single-tier playbook)",
    "external_optimizer": "external optimizer (offline)",
    "skillopt": "SkillOpt (offline)",
}


def running_mean(vals):
    out, s = [], 0.0
    for i, v in enumerate(vals):
        s += v
        out.append(s / (i + 1))
    return out


def load(outdir):
    runs = pathlib.Path(outdir) / "runs"
    data = collections.defaultdict(list)  # method -> list of per-seed dicts
    for d in sorted(runs.glob("*_seed*")):
        name = d.name
        method, seed = name.rsplit("_seed", 1)
        tf = d / "tasks.jsonl"
        if not tf.exists():
            continue
        rows = [json.loads(l) for l in tf.read_text().splitlines() if l.strip()]
        if not rows:
            continue
        data[method].append({
            "preq_em": running_mean([r["em"] for r in rows]),
            "cum_cost": [r["cum_cost_usd"] for r in rows],
            "em": [r["em"] for r in rows],
        })
    return data


def agg(seed_series, key):
    n = min(len(s[key]) for s in seed_series)
    mean, lo, hi = [], [], []
    for i in range(n):
        vals = [s[key][i] for s in seed_series]
        mean.append(sum(vals) / len(vals))
        lo.append(min(vals))
        hi.append(max(vals))
    return mean, lo, hi


# ---------- minimal SVG ----------
def _svg_open(w, h):
    return ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
            'font-family="Helvetica,Arial,sans-serif">' % (w, h),
            '<rect width="%d" height="%d" fill="white"/>' % (w, h)]


def _line(x1, y1, x2, y2, color="#333", w=1, dash=None):
    d = ' stroke-dasharray="%s"' % dash if dash else ""
    return '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="%s"%s/>' % (
        x1, y1, x2, y2, color, w, d)


def _text(x, y, s, size=12, color="#222", anchor="start", weight="normal"):
    return '<text x="%.1f" y="%.1f" font-size="%d" fill="%s" text-anchor="%s" font-weight="%s">%s</text>' % (
        x, y, size, color, anchor, weight, s)


def _poly(pts, color, w=2):
    p = " ".join("%.1f,%.1f" % xy for xy in pts)
    return '<polyline points="%s" fill="none" stroke="%s" stroke-width="%s"/>' % (p, color, w)


def _band(top, bot, color):
    pts = top + bot[::-1]
    p = " ".join("%.1f,%.1f" % xy for xy in pts)
    return '<polygon points="%s" fill="%s" fill-opacity="0.13" stroke="none"/>' % (p, color)


def chart(data, xkey, title, xlabel, out, ymax=1.0):
    W, H = 720, 460
    L, R, T, B = 70, 230, 46, 56
    pw, ph = W - L - R, H - T - B
    # x-domain
    if xkey == "cum_cost":
        xmax = max(max(agg(series, "cum_cost")[0]) for series in data.values()) * 1.02 or 1.0
        def X(v): return L + pw * (v / xmax)
    else:
        xmax = max(len(agg(series, "preq_em")[0]) for series in data.values()) - 1 or 1
        def X(i): return L + pw * (i / xmax)
    def Y(v): return T + ph * (1 - v / ymax)

    svg = _svg_open(W, H)
    svg.append(_text(L, 26, title, size=16, weight="bold"))
    # grid + y ticks
    for k in range(0, 6):
        v = ymax * k / 5
        y = Y(v)
        svg.append(_line(L, y, L + pw, y, "#e8e8e8", 1))
        svg.append(_text(L - 8, y + 4, "%.1f" % v, size=11, anchor="end", color="#666"))
    svg.append(_line(L, T, L, T + ph, "#333", 1))
    svg.append(_line(L, T + ph, L + pw, T + ph, "#333", 1))
    svg.append(_text(L + pw / 2, H - 16, xlabel, size=12, anchor="middle"))
    svg.append(_text(18, T + ph / 2, "prequential EM", size=12, anchor="middle",
                     ) .replace("<text", '<text transform="rotate(-90 18 %.1f)"' % (T + ph / 2)))

    # x ticks
    if xkey == "cum_cost":
        for k in range(0, 6):
            v = xmax * k / 5
            svg.append(_text(X(v), T + ph + 18, "$%.2f" % v, size=10, anchor="middle", color="#666"))
    else:
        step = max(1, int(round((xmax) / 6)))
        i = 0
        while i <= xmax:
            svg.append(_text(X(i), T + ph + 18, "%d" % i, size=10, anchor="middle", color="#666"))
            i += step

    # series
    leg_y = T + 6
    for m in [x for x in ORDER if x in data] + [x for x in data if x not in ORDER]:
        series = data[m]
        color = COLORS.get(m, "#333")
        mean, lo, hi = agg(series, "preq_em")
        if xkey == "cum_cost":
            xv = agg(series, "cum_cost")[0]
        else:
            xv = list(range(len(mean)))
        top = [(X(xv[i]), Y(hi[i])) for i in range(len(mean))]
        bot = [(X(xv[i]), Y(lo[i])) for i in range(len(mean))]
        if len(series) > 1:
            svg.append(_band(top, bot, color))
        svg.append(_poly([(X(xv[i]), Y(mean[i])) for i in range(len(mean))], color, 2.4))
        # legend
        svg.append(_line(L + pw + 14, leg_y, L + pw + 36, leg_y, color, 3))
        svg.append(_text(L + pw + 42, leg_y + 4, "%s (%.3f)" % (LABEL.get(m, m), mean[-1]),
                         size=11, color="#222"))
        leg_y += 20

    svg.append("</svg>")
    pathlib.Path(out).write_text("\n".join(svg), encoding="utf-8")
    print("wrote", out)


SHORT = {"no_memory": "no-mem", "external_optimizer": "external", "ace": "ACE",
         "skillopt": "SkillOpt", "ours_full": "ours-full", "ours_mem": "ours-mem",
         "episodic": "episodic"}


def bars(data, title, out):
    """Grouped bars: final prequential EM per method, with per-seed dots + cost label."""
    methods = [m for m in ORDER if m in data] + [m for m in data if m not in ORDER]
    W, H = 660, 460
    L, R, T, B = 64, 24, 56, 70
    pw, ph = W - L - R, H - T - B
    n = len(methods)
    slot = pw / n
    bw = slot * 0.5

    def Y(v):
        return T + ph * (1 - v)

    svg = _svg_open(W, H)
    svg.append(_text(L, 26, title, size=16, weight="bold"))
    for k in range(0, 6):
        v = k / 5.0
        y = Y(v)
        svg.append(_line(L, y, L + pw, y, "#e8e8e8", 1))
        svg.append(_text(L - 8, y + 4, "%.1f" % v, size=11, anchor="end", color="#666"))
    svg.append(_line(L, T, L, T + ph, "#333", 1))
    svg.append(_line(L, T + ph, L + pw, T + ph, "#333", 1))
    svg.append(_text(16, T + ph / 2, "final EM", size=12, anchor="middle").replace(
        "<text", '<text transform="rotate(-90 16 %.1f)"' % (T + ph / 2)))

    for i, m in enumerate(methods):
        series = data[m]
        ems = [running_mean(s["em"])[-1] for s in series]
        em = sum(ems) / len(ems)
        cost = sum(s["cum_cost"][-1] for s in series) / len(series)
        cx = L + slot * (i + 0.5)
        color = COLORS.get(m, "#333")
        svg.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" fill-opacity="0.85"/>'
                   % (cx - bw / 2, Y(em), bw, T + ph - Y(em), color))
        for e in ems:  # per-seed dots
            svg.append('<circle cx="%.1f" cy="%.1f" r="3.2" fill="#222"/>' % (cx, Y(e)))
        svg.append(_text(cx, Y(em) - 8, "%.3f" % em, size=12, anchor="middle", weight="bold"))
        svg.append(_text(cx, T + ph + 18, SHORT.get(m, m), size=12, anchor="middle"))
        svg.append(_text(cx, T + ph + 34, "$%.2f" % cost, size=10, anchor="middle", color="#666"))
        svg.append(_text(cx, T + ph + 48, "%.2f EM/$" % (em / cost if cost else 0), size=9,
                         anchor="middle", color="#999"))
    svg.append("</svg>")
    pathlib.Path(out).write_text("\n".join(svg), encoding="utf-8")
    print("wrote", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--title", default="", help="benchmark name shown in titles")
    args = ap.parse_args()
    data = load(args.outdir)
    if not data:
        print("no runs found in", args.outdir)
        return
    name = args.title or pathlib.Path(args.outdir).name
    seeds = max(len(v) for v in data.values())
    out = pathlib.Path(args.outdir)
    chart(data, "idx",
          "Prequential learning curve (%s, %d seed%s)" % (name, seeds, "s" if seeds > 1 else ""),
          "task index in stream", str(out / "fig_learning_curve.svg"))
    chart(data, "cum_cost",
          "Accuracy vs cumulative cost (%s)" % name,
          "cumulative cost (USD, incl. self-evolution / training)",
          str(out / "fig_acc_vs_cost.svg"))
    bars(data, "Final accuracy by method (%s, %d seeds)" % (name, seeds),
         str(out / "fig_final_bars.svg"))


if __name__ == "__main__":
    main()
