#!/usr/bin/env python3
"""Phase-0 orchestrator: run methods x seeds, aggregate the prequential curve.

Prequential accuracy at task i = mean EM over tasks 1..i (test-then-train), then
averaged across seeds. Also reports cumulative cost (the C2 x-axis).

Usage:
  python3 eval/run.py --tasks eval/data/searchqa_val.jsonl --n 10 \
      --methods no_memory,ours_full --seeds 0 --outdir eval/out/smoke
"""
import argparse
import json
import os
import pathlib
import subprocess
import sys

CODE_DIR = pathlib.Path(__file__).resolve().parents[1]


def run_one(tasks, n, method, seed, outdir, train_n=12, env_name="searchqa",
            protocol="prequential", test_n=0, stratify_key="", induce_every=16,
            deploy_workers=1, acquire_mode="sequential", learn_workers=4,
            repair_turns=0, repair_methods="ours", verify_mode="self_both",
            agentic=False, agentic_max_turns=20, native_skills="", batch_size=1,
            retrieval="agentic", gate_signal="oracle", credit_signal="oracle",
            reflect_signal="oracle", gate_audit=False,
            memory_mode="native", skill_turns=4, skill_tools="Skill,Read",
            permission_mode="bypassPermissions", gate_sample=0, skill_load="fixed",
            consolidate_mode="incremental"):
    home = pathlib.Path(outdir) / "runs" / ("%s_seed%d" % (method, seed)) / "home"
    home.mkdir(parents=True, exist_ok=True)
    out = pathlib.Path(outdir) / "runs" / ("%s_seed%d" % (method, seed)) / "tasks.jsonl"
    env = dict(os.environ)
    env.setdefault("NATIVE_EVOLVE_CLAUDE_BIN", os.environ.get("NATIVE_EVOLVE_CLAUDE_BIN", "claude"))
    cmd = [
        sys.executable, str(CODE_DIR / "eval" / "prequential.py"),
        "--tasks", tasks, "--env", env_name, "--n", str(n), "--method", method,
        "--seed", str(seed), "--protocol", protocol, "--train_n", str(train_n),
        "--test_n", str(test_n),
        "--stratify_key", stratify_key, "--induce_every", str(induce_every),
        "--deploy_workers", str(deploy_workers),
        "--acquire_mode", acquire_mode, "--learn_workers", str(learn_workers),
        "--repair_turns", str(repair_turns), "--repair_methods", repair_methods,
        "--verify_mode", verify_mode,
        "--agentic_max_turns", str(agentic_max_turns), "--native_skills", native_skills,
        "--batch_size", str(batch_size), "--retrieval", retrieval,
        "--gate_signal", gate_signal, "--credit_signal", credit_signal,
        "--reflect_signal", reflect_signal,
        "--memory_mode", memory_mode, "--skill_turns", str(skill_turns),
        "--skill_tools", skill_tools, "--permission_mode", permission_mode,
        "--gate_sample", str(gate_sample), "--skill_load", skill_load,
        "--consolidate_mode", consolidate_mode,
        "--home", str(home), "--out", str(out),
    ]
    if agentic:
        cmd.append("--agentic")
    if gate_audit:
        cmd.append("--gate_audit")
    subprocess.run(cmd, env=env, check=True)
    return [json.loads(l) for l in out.read_text().splitlines() if l.strip()]


def running_mean(vals):
    out, s = [], 0.0
    for i, v in enumerate(vals):
        s += v
        out.append(s / (i + 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--env", default="searchqa")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--methods", default="no_memory,ours_full")
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--outdir", default="results/smoke")
    ap.add_argument("--protocol", choices=["prequential", "frozen"], default="prequential",
                    help="prequential: online learning curve. frozen: acquire->gate->FREEZE->"
                         "held-out test headline (SkillOpt-style; measures reuse).")
    ap.add_argument("--train_n", type=int, default=12,
                    help="train/rollout split size (frozen acquisition + external offline-train). SB=80.")
    ap.add_argument("--test_n", type=int, default=0,
                    help="frozen: held-out test size (0=all remaining after train). SB=280.")
    ap.add_argument("--stratify_key", default="",
                    help="stratify splits on this task field (instruction_type for SB, type for hotpotqa).")
    ap.add_argument("--induce_every", type=int, default=16,
                    help="ours_full: gated skill consolidation every K acquisition tasks (0=off).")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel (method,seed) RUNS. Learning phases are internally sequential; "
                         "seeds/methods are independent so they parallelize safely.")
    ap.add_argument("--max_concurrency", type=int, default=16,
                    help="target max concurrent claude requests across the whole launch (e.g. 64). "
                         "Within a run the no-writes deploy phase fans out to "
                         "max_concurrency//workers.")
    ap.add_argument("--acquire_mode", choices=["sequential", "serving"], default="sequential",
                    help="sequential: strict prequential learning. serving: serve concurrently "
                         "against the live store + async background reflection (real-deployment "
                         "model; parallelizes the learning phase too).")
    ap.add_argument("--learn_workers", type=int, default=4,
                    help="serving: background reflection worker pool size.")
    ap.add_argument("--repair_turns", type=int, default=0,
                    help="max conditional repair rounds per task (0=single-shot). Fires only on a "
                         "reference-free env.verify rejection; valid at frozen-test time. SEPARATE "
                         "LABELED LEVER (design (a)): default 0 = OFF; MEMORY claims are read off this "
                         "repair=0 column. Study repair via the explicit memory x repair 2x2.")
    ap.add_argument("--repair_methods", default="ours",
                    help="when --repair_turns>0, which methods get the repair lever: 'ours' (the "
                         "repair-ON cell; baselines single-shot), 'all' (for the clean 2x2), or a comma "
                         "list ('no_memory' = apparatus-only ablation). Repair is NOT part of memory.")
    ap.add_argument("--verify_mode", choices=["oracle", "self", "self_exec", "self_both"], default="self_both",
                    help="repair-loop signal: self_both (DEFAULT, DATASET-AGNOSTIC: run BOTH exec + LLM "
                         "semantic self-critique; clean execution AUTHORITATIVE so critique is advisory), "
                         "self (route to one channel by code-block), self_exec (exec channel only), or "
                         "oracle (per-env, dataset-AWARE ceiling; pass explicitly to reproduce the oracle map).")
    ap.add_argument("--agentic", action="store_true",
                    help="agentic solve: target runs multi-turn with Read/Write/Bash/Skill in a "
                         "gold-isolated per-task sandbox (writes+runs+repairs its own code). Env must "
                         "implement agentic_attempt (SpreadsheetBench does).")
    ap.add_argument("--agentic_max_turns", type=int, default=20,
                    help="agentic: hard cap on agent turns per task (claude --max-turns).")
    ap.add_argument("--native_skills", default="",
                    help="comma list of engine/skills/ names to install as discoverable skills in the "
                         "agent sandbox (e.g. self-verify-and-repair). '' = bare-agentic ablation.")
    ap.add_argument("--batch_size", type=int, default=1,
                    help="bounded-staleness parallel prequential: solve B tasks concurrently per memory "
                         "snapshot, learn between batches (speedup ~B, memory staleness <= B). 1 = sequential.")
    ap.add_argument("--retrieval", choices=["lexical", "agentic"], default="agentic",
                    help="distilled-memory retrieval for ours_mem/ours_full. agentic (DEFAULT, native "
                         "Claude Code paradigm): the MODEL selects relevant items from a presented index "
                         "(+1 claude call/task, ledger-billed). lexical: bag-of-words top-k (pre-2026-06-06 "
                         "behavior; pass explicitly to reproduce older runs).")
    ap.add_argument("--gate_signal", choices=["reffree", "oracle"], default="oracle",
                    help="skill-promotion GATE signal. oracle (DEFAULT, back-compat): GOLD env.score "
                         "(measurement ceiling, not deploy-available). reffree: deploy-faithful "
                         "self_verify A/B (no gold). Run both for the precision-law-for-gating A/B.")
    ap.add_argument("--credit_signal", choices=["reffree", "oracle"], default="oracle",
                    help="episodic-success + bullet-CREDIT signal. oracle (DEFAULT): GOLD em. reffree: "
                         "self_verify ok (deploy-available, no gold).")
    ap.add_argument("--reflect_signal", choices=["reffree", "oracle"], default="oracle",
                    help="Reflector evidence. oracle (DEFAULT): GOLD collect_evidence (incl. N3). "
                         "reffree: reference-free verdict + repair trace (no gold; loses N3).")
    ap.add_argument("--gate_audit", action="store_true",
                    help="precision-law-for-gating audit: log BOTH gate signals (oracle vs reffree) on "
                         "the SAME val A/B answers to home/gate_audit.json (live decision = --gate_signal).")
    ap.add_argument("--memory_mode", choices=["inject", "native"], default="native",
                    help="HOW memory+skills reach the agent. native (DEFAULT, deploy-faithful): discoverable "
                         ".claude/skills, agent invokes, credit = what it invoked. inject: legacy force-injected "
                         "text block (+ --retrieval). See prequential --memory_mode.")
    ap.add_argument("--skill_turns", type=int, default=4,
                    help="native: claude --max-turns for the Skill-enabled solve (default 4).")
    ap.add_argument("--skill_tools", default="Skill,Read",
                    help="native: allowed tools (claude --allowedTools). Default 'Skill,Read'; for code "
                         "self-test envs (ARC) use 'Skill,Read,Write,Edit,Bash'. Same for all arms.")
    ap.add_argument("--permission_mode", default="bypassPermissions",
                    help="native/agentic: claude --permission-mode (default 'bypassPermissions' for headless).")
    ap.add_argument("--gate_sample", type=int, default=0,
                    help="pooled gate: cap each candidate skill's A/B set to this many episode-tasks "
                         "(0=all). Bounds cost when induce proposes MULTIPLE skills.")
    ap.add_argument("--skill_load", choices=["fixed", "native"], default="fixed",
                    help="tier-2 skill delivery: fixed (DEFAULT) = harness injects ALL active skills "
                         "deterministically; native = agent discovers them in the catalog.")
    ap.add_argument("--consolidate_mode", choices=["incremental", "pooled"], default="incremental",
                    help="incremental (DEFAULT) = add skills from new memory only, vs existing library; "
                         "pooled (legacy) = re-induce over the whole bullet pool each time.")
    args = ap.parse_args()

    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    pathlib.Path(args.outdir).mkdir(parents=True, exist_ok=True)

    # results[method][seed] = list of per-task rows
    jobs = [(m, s) for m in methods for s in seeds]
    results = {m: {} for m in methods}
    deploy_workers = max(1, args.max_concurrency // max(1, args.workers))
    print("concurrency: workers=%d runs x deploy_workers=%d => peak ~%d concurrent claude requests"
          % (args.workers, deploy_workers, args.workers * deploy_workers))

    def _call(m, s):
        return run_one(args.tasks, args.n, m, s, args.outdir, args.train_n, args.env,
                       args.protocol, args.test_n, args.stratify_key,
                       args.induce_every, deploy_workers, args.acquire_mode, args.learn_workers,
                       args.repair_turns, args.repair_methods, args.verify_mode,
                       args.agentic, args.agentic_max_turns, args.native_skills, args.batch_size,
                       args.retrieval, args.gate_signal, args.credit_signal, args.reflect_signal,
                       args.gate_audit, args.memory_mode, args.skill_turns, args.skill_tools,
                       args.permission_mode, args.gate_sample, args.skill_load,
                       args.consolidate_mode)
    if args.workers <= 1:
        for m, s in jobs:
            results[m][s] = _call(m, s)
    else:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
            fut = {ex.submit(_call, m, s): (m, s) for m, s in jobs}
            for f in concurrent.futures.as_completed(fut):
                m, s = fut[f]
                results[m][s] = f.result()

    # aggregate prequential accuracy + cost, averaged across seeds
    curve_path = pathlib.Path(args.outdir) / "curve.csv"
    summary = {}
    with curve_path.open("w", encoding="utf-8") as f:
        f.write("method,task_idx,preq_em,preq_f1,cum_cost_usd,n_bullets\n")
        for m in methods:
            per_seed_em, per_seed_f1, per_seed_cost, per_seed_bul = [], [], [], []
            for s in seeds:
                rows = results[m][s]
                per_seed_em.append(running_mean([r["em"] for r in rows]))
                per_seed_f1.append(running_mean([r["f1"] for r in rows]))
                per_seed_cost.append([r["cum_cost_usd"] for r in rows])
                per_seed_bul.append([r["n_bullets"] for r in rows])
            n = min(len(x) for x in per_seed_em)
            for i in range(n):
                em = sum(es[i] for es in per_seed_em) / len(seeds)
                f1 = sum(es[i] for es in per_seed_f1) / len(seeds)
                cost = sum(es[i] for es in per_seed_cost) / len(seeds)
                bul = sum(es[i] for es in per_seed_bul) / len(seeds)
                f.write("%s,%d,%.4f,%.4f,%.6f,%.2f\n" % (m, i, em, f1, cost, bul))
            # first-half vs second-half raw EM (learning signal within the stream)
            def half_means(seed_idx):
                ems = [r["em"] for r in results[m][seeds[seed_idx]]]
                mid = max(1, len(ems) // 2)
                first = sum(ems[:mid]) / mid
                second = sum(ems[mid:]) / max(1, len(ems) - mid)
                return first, second
            firsts = [half_means(i)[0] for i in range(len(seeds))]
            seconds = [half_means(i)[1] for i in range(len(seeds))]
            summary[m] = {
                "final_preq_em": round(sum(es[-1] for es in per_seed_em) / len(seeds), 4),
                "final_preq_f1": round(sum(es[-1] for es in per_seed_f1) / len(seeds), 4),
                "first_half_em": round(sum(firsts) / len(seeds), 4),
                "second_half_em": round(sum(seconds) / len(seeds), 4),
                "total_cost_usd": round(sum(cs[-1] for cs in per_seed_cost) / len(seeds), 4),
                "final_bullets": round(sum(bs[-1] for bs in per_seed_bul) / len(seeds), 2),
            }

    (pathlib.Path(args.outdir) / "summary.json").write_text(json.dumps(summary, indent=2))
    headline_n = min((len(results[m][s]) for m in methods for s in seeds), default=0)
    print("\n==================== PHASE-0 SUMMARY ====================")
    if args.protocol == "frozen":
        print("protocol=frozen  train=%d test=%d(headline)  methods=%s  seeds=%s"
              % (args.train_n, headline_n, methods, seeds))
        emlabel = "testEM"
    else:
        print("protocol=prequential  tasks=%d  methods=%s  seeds=%s" % (args.n, methods, seeds))
        emlabel = "preqEM"
    print("%-12s %8s %8s %9s %9s %10s %8s"
          % ("method", emlabel, "F1", "1stHalf", "2ndHalf", "cost_usd", "bullets"))
    for m in methods:
        s = summary[m]
        print("%-12s %8.3f %8.3f %9.3f %9.3f %10.4f %8.1f"
              % (m, s["final_preq_em"], s["final_preq_f1"], s["first_half_em"],
                 s["second_half_em"], s["total_cost_usd"], s["final_bullets"]))
    print("curve -> %s" % curve_path)
    print("========================================================\n")


if __name__ == "__main__":
    main()
