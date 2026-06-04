#!/usr/bin/env python3
"""One prequential run: stream tasks, test-then-train, log per task.

Methods (episodic-first memory; consolidation is non-destructive + explicitly gated):
  no_memory   -> target only; no injection, no learning (lower bound)
  episodic    -> retrieve raw past-success exemplars (episodic-only control); no consolidation
  ours_mem    -> distilled itemized memory: reflect/curate + top-k retrieval + presence/gold credit
  ours_full   -> episodic + distilled + GATED skills (induce, activate only if they beat the
                 episodic+distilled baseline on held-out tasks; source memory never drained)
  ace         -> single-tier: inject the FULL playbook every task; reflect; no promotion
  external_optimizer -> offline-train one frozen SKILL.md on a disjoint split (cost paid up front)

Isolation: each run gets its own NATIVE_EVOLVE_HOME (fresh memory store + prompts),
so learning is clean and reproducible and never touches the deployment store.

Cost (target + Reflector + promote) is captured via NATIVE_EVOLVE_LEDGER and
reported as a cumulative curve — the x-axis of the C2 figure.
"""
import argparse
import json
import os
import pathlib
import random
import shutil
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO_ROOT / "engine"   # the object under study (evolve/ prompts/ memory/ ...)


def prepare_home(home):
    home = pathlib.Path(home)
    (home / "memory" / "replay").mkdir(parents=True, exist_ok=True)
    (home / ".claude" / "skills").mkdir(parents=True, exist_ok=True)
    # prompts must live under HOME (config resolves them there)
    dst = home / "prompts"
    if not dst.exists():
        shutil.copytree(ENGINE_DIR / "prompts", dst)
    # seed the promotion-gate replay cases so the gate can actually verify in experiments
    src_replay = ENGINE_DIR / "memory" / "replay"
    if src_replay.exists():
        for case in src_replay.glob("*.json"):
            tgt = home / "memory" / "replay" / case.name
            if not tgt.exists():
                shutil.copy(str(case), str(tgt))
    (home / "memory" / "store.jsonl").touch()
    (home / "memory" / "skill_state.json").write_text("{}", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", required=True)
    ap.add_argument("--env", default="searchqa")
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--method",
                    choices=["no_memory", "episodic", "ours_mem", "ours_full",
                             "ace", "external_optimizer"],
                    required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--train_n", type=int, default=12,
                    help="external_optimizer: # disjoint training tasks (after the eval slice)")
    ap.add_argument("--induce_every", type=int, default=16,
                    help="ours_full: run gated skill consolidation every K tasks (0=off)")
    ap.add_argument("--verify_n", type=int, default=6,
                    help="ours_full: # held-out tasks for the counterfactual consolidation gate")
    ap.add_argument("--home", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # env must be set BEFORE importing evolve (config reads HOME at import)
    home = pathlib.Path(args.home).resolve()
    home.mkdir(parents=True, exist_ok=True)
    os.environ["NATIVE_EVOLVE_HOME"] = str(home)
    ledger = home / "ledger.jsonl"
    ledger.write_text("", encoding="utf-8")
    os.environ["NATIVE_EVOLVE_LEDGER"] = str(ledger)
    prepare_home(args.home)
    sys.path.insert(0, str(ENGINE_DIR))

    from evolve import retrieve, reflect, store, curate, episodic, induce, verify  # noqa: E402
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import external_opt  # noqa: E402
    import envs as envs_pkg  # noqa: E402
    from evolve import llm  # noqa: E402
    env = envs_pkg.get_env(args.env)

    all_tasks = env.load_tasks(args.tasks)
    rng = random.Random(args.seed)
    rng.shuffle(all_tasks)
    tasks = all_tasks[: args.n]                          # eval stream (same across methods)
    train_tasks = all_tasks[args.n: args.n + args.train_n]  # disjoint, for external optimizer
    vstart = args.n + args.train_n
    verify_tasks = all_tasks[vstart: vstart + args.verify_n]  # disjoint, for the consolidation gate

    # external_optimizer: pay the offline training cost up front, then freeze one skill.
    frozen_skill = ""
    if args.method == "external_optimizer":
        sys.stderr.write("[external_optimizer seed%d] offline training on %d tasks...\n"
                         % (args.seed, len(train_tasks)))
        frozen_skill = external_opt.train_external(train_tasks, env)

    def cum_cost():
        c = t = 0.0
        for line in ledger.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            c += rec.get("cost_usd", 0.0)
            t += rec.get("output_tokens", 0)
        return c, t

    def base_block(t):
        """Episodic + distilled injection — the episodic-first baseline the gate must beat."""
        epi = episodic.exemplar_block(t["question"])
        dis, _ = retrieve.select_and_block(t["question"])
        return "\n\n".join(x for x in (epi, dis) if x)

    def consolidate(idx):
        """Non-destructive, GATED consolidation: induce skills from memory, activate them ONLY
        if they lift held-out accuracy over the episodic+distilled baseline; else keep them as
        candidates so ours_full degrades gracefully to episodic+distilled (never below)."""
        cands = induce.induce(focus_failures=True)
        if not cands:
            return
        skill_block = "## Candidate skills (apply if relevant):\n\n" + "\n\n".join(c["md"] for c in cands)
        bp, fp, vn = verify.lift_over_base(skill_block, base_block, verify_tasks, env)
        activate = vn > 0 and fp > bp
        for c in cands:
            induce.write_skill(c, status=("active" if activate else "candidate"))
        sys.stderr.write("[consolidate @%d] gate: base %d -> +skills %d (of %d) => %s\n"
                         % (idx, bp, fp, vn,
                            ("ACTIVATE %d skills" % len(cands)) if activate else "REJECT (degrade)"))

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, task in enumerate(tasks):
        q = task["question"]

        # --- inject context per method ---
        injected_ids = []
        if args.method == "episodic":
            mem_block = episodic.exemplar_block(q)              # raw past-success exemplars (episodic-only)
        elif args.method == "ours_mem":
            mem_block, injected_ids = retrieve.select_and_block(q)  # distilled top-k memory only
        elif args.method == "ours_full":
            epi = episodic.exemplar_block(q)                    # episodic exemplars
            dis, injected_ids = retrieve.select_and_block(q)    # distilled top-k memory
            skl = retrieve.skills_block(q)                      # gated, verified skills (often none)
            mem_block = "\n\n".join(x for x in (epi, dis, skl) if x)
        elif args.method == "ace":
            mem_block = retrieve.full_playbook_block()          # single-tier: full playbook
        elif args.method == "external_optimizer":
            mem_block = ("## Skill (offline-optimized, frozen)\n" + frozen_skill) if frozen_skill else ""
        else:
            mem_block = ""                                      # no_memory

        try:
            resp = llm.call_claude(env.build_prompt(task, mem_block), allowed_tools="Read")
        except Exception as exc:
            resp = ""
            sys.stderr.write("target error @%d: %s\n" % (idx, exc))

        ev = env.score(task, resp)

        # --- record the RAW EPISODE (episodic-first methods): first-class, append-only ---
        if args.method in ("episodic", "ours_full"):
            try:
                episodic.record(task["id"], q, resp, ev["em"] == 1.0)
            except Exception as exc:
                sys.stderr.write("episode record error @%d: %s\n" % (idx, exc))

        # --- credit distilled bullets that were injected (deterministic presence/gold) ---
        if args.method in ("ours_mem", "ours_full") and injected_ids:
            try:
                curate.credit(injected_ids, ev["em"] == 1.0)
            except Exception as exc:
                sys.stderr.write("credit error @%d: %s\n" % (idx, exc))

        # --- reflect -> distilled memory (methods that maintain a distilled store) ---
        # promote_skills=False: consolidation is now the NON-DESTRUCTIVE, GATED induce step
        # (consolidate()), never the old per-bullet promote that drained the memory tier.
        if args.method in ("ours_mem", "ours_full", "ace"):
            try:
                reflect.run(summary=env.summarize(task, resp, ev), promote_skills=False)
            except Exception as exc:
                sys.stderr.write("reflect error @%d: %s\n" % (idx, exc))

        # --- gated consolidation (ours_full): induce skills, activate only if they beat the
        #     episodic+distilled baseline on held-out tasks; else degrade gracefully ---
        if args.method == "ours_full" and args.induce_every > 0 and (idx + 1) % args.induce_every == 0:
            try:
                consolidate(idx)
            except Exception as exc:
                sys.stderr.write("consolidate error @%d: %s\n" % (idx, exc))

        cc, ct = cum_cost()
        bullets = store.load()
        skill_state = store.load_skill_state()
        n_active_skills = sum(1 for v in skill_state.values() if v.get("status") == "active")
        n_episodes = len(episodic.load()) if args.method in ("episodic", "ours_full") else 0
        rows.append({
            "idx": idx, "id": task["id"], "em": ev["em"], "f1": ev["f1"],
            "sub_em": ev["sub_em"], "pred": ev["predicted_answer"][:80],
            "n_bullets": len(bullets), "n_episodes": n_episodes,
            "max_uses": max((b.get("uses", 0) for b in bullets), default=0),
            "max_helpful": max((b.get("helpful", 0) for b in bullets), default=0),
            "n_active_skills": n_active_skills,
            "cum_cost_usd": round(cc, 6), "cum_output_tokens": ct,
        })
        sys.stderr.write(
            "[%s seed%d] %2d/%d em=%.0f f1=%.2f bul=%d ep=%d uses<=%d skills=%d cum=$%.4f\n"
            % (args.method, args.seed, idx + 1, len(tasks), ev["em"], ev["f1"],
               rows[-1]["n_bullets"], n_episodes, rows[-1]["max_uses"],
               rows[-1]["n_active_skills"], cc)
        )

    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    em = sum(r["em"] for r in rows) / max(1, len(rows))
    f1 = sum(r["f1"] for r in rows) / max(1, len(rows))
    sys.stderr.write("DONE %s seed%d: EM=%.3f F1=%.3f cum=$%.4f -> %s\n"
                     % (args.method, args.seed, em, f1, rows[-1]["cum_cost_usd"] if rows else 0, out))


if __name__ == "__main__":
    main()
