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


def stratified_split(all_tasks, sizes, seed, stratify_key=""):
    """Seeded disjoint split into EXACTLY `sizes` = (n0, n1, n2) consecutive slices.

    Follows the SkillOpt manifest roles (train -> rollout evidence; val/selection -> accept/reject
    skill edits; test -> frozen held-out headline). If `stratify_key` is set and present on every
    task, strata are interleaved in proportion so any prefix — and thus every slice — preserves the
    class mix (e.g. SB instruction_type, HotpotQA type). With stratify_key="" this is a plain seeded
    shuffle, byte-identical to the previous slicing (same seed -> same permutation)."""
    import collections
    rng = random.Random(seed)
    pool = list(all_tasks)
    rng.shuffle(pool)
    if stratify_key and all(stratify_key in t for t in pool):
        groups = collections.OrderedDict()
        for t in pool:
            groups.setdefault(t.get(stratify_key), []).append(t)
        emitted = {g: 0 for g in groups}
        order, remaining = [], len(pool)
        while remaining:
            # emit next from the stratum most "behind" its proportional share
            g = min((g for g in groups if emitted[g] < len(groups[g])),
                    key=lambda g: (emitted[g] + 1) / len(groups[g]))
            order.append(groups[g][emitted[g]])
            emitted[g] += 1
            remaining -= 1
        pool = order
    a, b, c = sizes
    return pool[:a], pool[a:a + b], pool[a + b:a + b + c]


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
    ap.add_argument("--protocol", choices=["prequential", "frozen"], default="prequential",
                    help="prequential: online test-then-train on one stream (the learning curve). "
                         "frozen (SkillOpt-style): acquire on train -> gate skill edits on val -> "
                         "FREEZE -> headline on held-out test (measures REUSE, not local adaptation).")
    ap.add_argument("--train_n", type=int, default=12,
                    help="train/rollout-evidence split: # tasks the method LEARNS on. "
                         "frozen acquisition stream + external_optimizer offline-training set. "
                         "SkillOpt SB=80.")
    ap.add_argument("--verify_n", type=int, default=18,
                    help="val/selection split: # held-out tasks for the accept/reject skill-edit "
                         "gate. SkillOpt sizes ~18-40; >6 needed for power over haiku noise (SB=40).")
    ap.add_argument("--test_n", type=int, default=0,
                    help="frozen: # held-out TEST tasks for the headline (0 = all remaining after "
                         "train+val). SkillOpt SB=280.")
    ap.add_argument("--stratify_key", default="",
                    help="task field to stratify the splits on so each split keeps the family mix "
                         "(e.g. instruction_type for SB, type for HotpotQA). '' = plain shuffle.")
    ap.add_argument("--induce_every", type=int, default=16,
                    help="ours_full: run gated skill consolidation every K tasks (0=off)")
    ap.add_argument("--deploy_workers", type=int, default=1,
                    help="concurrent claude requests for NO-WRITES phases (frozen test deploy; "
                         "and no_memory/external in prequential). Up to ~64; the runner derives "
                         "this from --max_concurrency.")
    ap.add_argument("--acquire_mode", choices=["sequential", "serving"], default="sequential",
                    help="how the LEARNING phase runs. sequential: strict prequential (task i tests "
                         "with memory from 1..i-1, then trains) — clean measurement. serving: a real "
                         "deployment — serve requests CONCURRENTLY (deploy_workers) against the LIVE "
                         "store while reflection writes ASYNC in the background; drain before freeze. "
                         "Removes the last sequential bottleneck; store writes are lock+atomic safe.")
    ap.add_argument("--learn_workers", type=int, default=4,
                    help="serving mode: background reflection workers (the async learner pool). "
                         "Store writes are serialized by STORE_LOCK regardless.")
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
    # SkillOpt-style disjoint splits: train (rollout evidence the method learns on), val/selection
    # (verify_tasks: accept/reject the skill-edit gate), test (frozen held-out headline). Optionally
    # stratified so each split keeps the task-family mix.
    if args.protocol == "frozen":
        test_n = args.test_n if args.test_n > 0 else max(
            0, len(all_tasks) - args.train_n - args.verify_n)
        need = args.train_n + args.verify_n + test_n
        if len(all_tasks) < need:
            sys.stderr.write("WARN: %d tasks < train+val+test=%d; later splits truncated\n"
                             % (len(all_tasks), need))
        train_tasks, verify_tasks, tasks = stratified_split(
            all_tasks, (args.train_n, args.verify_n, test_n), args.seed, args.stratify_key)
    else:                                                # prequential: eval stream IS the learn stream
        tasks, train_tasks, verify_tasks = stratified_split(
            all_tasks, (args.n, args.train_n, args.verify_n), args.seed, args.stratify_key)

    # external_optimizer: pay the offline training cost up front, then freeze one skill.
    frozen_skill = ""
    if args.method == "external_optimizer":
        sys.stderr.write("[external_optimizer seed%d] offline training on %d tasks...\n"
                         % (args.seed, len(train_tasks)))
        frozen_skill = external_opt.train_external(train_tasks, env, workers=args.deploy_workers)

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
        bp, fp, vn = verify.lift_over_base(skill_block, base_block, verify_tasks, env,
                                           workers=args.deploy_workers)
        activate = vn > 0 and fp > bp
        for c in cands:
            induce.write_skill(c, status=("active" if activate else "candidate"))
        sys.stderr.write("[consolidate @%d] gate: base %d -> +skills %d (of %d) => %s\n"
                         % (idx, bp, fp, vn,
                            ("ACTIVATE %d skills" % len(cands)) if activate else "REJECT (degrade)"))

    LEARN_METHODS = ("episodic", "ours_mem", "ours_full", "ace")

    def inject(task):
        """Build the injected memory/skill block for the current method (read-only retrieval)."""
        q = task["question"]
        injected_ids = []
        if args.method == "episodic":
            mem = episodic.exemplar_block(q)                    # raw past-success exemplars (episodic-only)
        elif args.method == "ours_mem":
            mem, injected_ids = retrieve.select_and_block(q)    # distilled top-k memory only
        elif args.method == "ours_full":
            epi = episodic.exemplar_block(q)                    # episodic exemplars
            dis, injected_ids = retrieve.select_and_block(q)    # distilled top-k memory
            skl = retrieve.skills_block(q)                      # gated, verified skills (often none)
            mem = "\n\n".join(x for x in (epi, dis, skl) if x)
        elif args.method == "ace":
            mem = retrieve.full_playbook_block()                # single-tier: full playbook
        elif args.method == "external_optimizer":
            mem = ("## Skill (offline-optimized, frozen)\n" + frozen_skill) if frozen_skill else ""
        else:
            mem = ""                                            # no_memory
        return mem, injected_ids

    def process(task, idx, learn, phase):
        """One task: inject -> target call -> score. If learn, update memory (record/credit/reflect).
        Deployment (learn=False) is pure inference on a FROZEN store: the held-out test phase."""
        q = task["question"]
        mem_block, injected_ids = inject(task)
        try:
            resp = llm.call_claude(env.build_prompt(task, mem_block), allowed_tools="Read")
        except Exception as exc:
            resp = ""
            sys.stderr.write("target error @%d: %s\n" % (idx, exc))
        ev = env.score(task, resp)

        if learn:
            # record the RAW EPISODE (episodic-first methods): first-class, append-only
            if args.method in ("episodic", "ours_full"):
                try:
                    episodic.record(task["id"], q, resp, ev["em"] == 1.0)
                except Exception as exc:
                    sys.stderr.write("episode record error @%d: %s\n" % (idx, exc))
            # credit distilled bullets that were injected (deterministic presence/gold)
            if args.method in ("ours_mem", "ours_full") and injected_ids:
                try:
                    curate.credit(injected_ids, ev["em"] == 1.0)
                except Exception as exc:
                    sys.stderr.write("credit error @%d: %s\n" % (idx, exc))
            # reflect -> distilled memory (promote_skills=False: consolidation is the gated induce step)
            if args.method in ("ours_mem", "ours_full", "ace"):
                try:
                    reflect.run(summary=env.summarize(task, resp, ev), promote_skills=False)
                except Exception as exc:
                    sys.stderr.write("reflect error @%d: %s\n" % (idx, exc))

        cc, ct = cum_cost()
        bullets = store.load()
        skill_state = store.load_skill_state()
        n_active_skills = sum(1 for v in skill_state.values() if v.get("status") == "active")
        n_episodes = len(episodic.load()) if args.method in ("episodic", "ours_full") else 0
        row = {
            "idx": idx, "phase": phase, "id": task["id"], "em": ev["em"], "f1": ev["f1"],
            "sub_em": ev["sub_em"], "pred": ev["predicted_answer"][:80],
            "n_bullets": len(bullets), "n_episodes": n_episodes,
            "max_uses": max((b.get("uses", 0) for b in bullets), default=0),
            "max_helpful": max((b.get("helpful", 0) for b in bullets), default=0),
            "n_active_skills": n_active_skills,
            "cum_cost_usd": round(cc, 6), "cum_output_tokens": ct,
        }
        sys.stderr.write(
            "[%s seed%d %s] %2d em=%.0f f1=%.2f bul=%d ep=%d uses<=%d skills=%d cum=$%.4f\n"
            % (args.method, args.seed, phase, idx + 1, ev["em"], ev["f1"],
               row["n_bullets"], n_episodes, row["max_uses"], n_active_skills, cc))
        return row

    def deploy_parallel(stream, phase):
        """Run a NO-WRITES phase concurrently (frozen store -> thread-safe). cum_cost is read once
        up front (acquisition cost) and reconstructed deterministically from each call's own cost,
        so the per-task cumulative curve is order-stable despite out-of-order completion."""
        c0, _ = cum_cost()                               # acquisition cost already on the ledger
        bullets = store.load()
        skill_state = store.load_skill_state()
        stat = {
            "n_bullets": len(bullets),
            "n_active_skills": sum(1 for v in skill_state.values() if v.get("status") == "active"),
            "n_episodes": len(episodic.load()) if args.method in ("episodic", "ours_full") else 0,
            "max_uses": max((b.get("uses", 0) for b in bullets), default=0),
            "max_helpful": max((b.get("helpful", 0) for b in bullets), default=0),
        }

        def one(pair):
            idx, task = pair
            mem_block, _ = inject(task)
            try:
                resp, cost = llm.call_claude(env.build_prompt(task, mem_block),
                                             allowed_tools="Read", return_cost=True)
            except Exception as exc:
                resp, cost = "", 0.0
                sys.stderr.write("target error @%d: %s\n" % (idx, exc))
            try:
                ev = env.score(task, resp)
            except Exception as exc:                     # never let one task kill the fan-out
                sys.stderr.write("score error @%d: %s\n" % (idx, exc))
                ev = {"em": 0.0, "f1": 0.0, "sub_em": 0.0, "predicted_answer": ""}
            sys.stderr.write("[%s seed%d %s] %3d/%d em=%.0f f1=%.2f $%.4f\n"
                             % (args.method, args.seed, phase, idx + 1, len(stream),
                                ev["em"], ev["f1"], cost))
            return {"idx": idx, "id": task["id"], "em": ev["em"], "f1": ev["f1"],
                    "sub_em": ev["sub_em"], "pred": ev["predicted_answer"][:80], "_cost": cost}

        partials = llm.pmap(one, list(enumerate(stream)), args.deploy_workers)
        out_rows, run = [], c0
        for p in sorted(partials, key=lambda r: r["idx"]):
            run += p["_cost"]
            out_rows.append({
                "idx": p["idx"], "phase": phase, "id": p["id"], "em": p["em"], "f1": p["f1"],
                "sub_em": p["sub_em"], "pred": p["pred"], "n_bullets": stat["n_bullets"],
                "n_episodes": stat["n_episodes"], "max_uses": stat["max_uses"],
                "max_helpful": stat["max_helpful"], "n_active_skills": stat["n_active_skills"],
                "cum_cost_usd": round(run, 6), "cum_output_tokens": 0,
            })
        return out_rows

    def run_phase(stream, learn, phase):
        """Sequential when the method WRITES this phase (online learning dependency); else run
        concurrently at --deploy_workers (no-writes: frozen deploy, or no_memory/external)."""
        writes = learn and args.method in LEARN_METHODS
        if not writes and args.deploy_workers > 1:
            return deploy_parallel(stream, phase)
        out_rows = []
        for idx, task in enumerate(stream):
            out_rows.append(process(task, idx, learn=learn, phase=phase))
            if (learn and args.method == "ours_full" and args.induce_every > 0
                    and (idx + 1) % args.induce_every == 0):
                try:
                    consolidate(idx)
                except Exception as exc:
                    sys.stderr.write("consolidate error @%d: %s\n" % (idx, exc))
        return out_rows

    def serve_and_learn(stream, phase):
        """SERVING execution of a learning phase: serve requests CONCURRENTLY (deploy_workers)
        against the LIVE store while reflection writes ASYNC in a background learner pool
        (learn_workers). Mirrors a real deployment — N+1 never blocks on N's reflection. The
        expensive reflect (claude) runs in parallel; only the cheap deterministic store write is
        serialized (store.STORE_LOCK) and atomic, so concurrent serve-time reads never tear and
        learners never lose updates. All learning is DRAINED before returning (-> freeze sees the
        fully-committed store). Per-row n_bullets = memory visible AT SERVE TIME (the staleness
        signal). Total acquisition cost (serve + async reflect) lands on the ledger and is picked
        up by the deploy phase's cum_cost; per-acquire-row cost shows serve cost only."""
        import concurrent.futures
        learn_ex = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, args.learn_workers))
        learn_futs = []

        def learn_job(task, resp, ev, injected_ids):
            deltas = []
            if args.method in ("ours_mem", "ours_full", "ace"):
                try:
                    deltas = reflect.reflect_deltas(env.summarize(task, resp, ev))   # parallel (no lock)
                except Exception as exc:
                    sys.stderr.write("reflect error: %s\n" % exc)
            with store.STORE_LOCK:                                                    # serialized + atomic
                if args.method in ("episodic", "ours_full"):
                    try:
                        episodic.record(task["id"], task["question"], resp, ev["em"] == 1.0)
                    except Exception as exc:
                        sys.stderr.write("episode record error: %s\n" % exc)
                if deltas:
                    try:
                        curate.merge(deltas)
                    except Exception as exc:
                        sys.stderr.write("curate error: %s\n" % exc)
                if args.method in ("ours_mem", "ours_full") and injected_ids:
                    try:
                        curate.credit(injected_ids, ev["em"] == 1.0)
                    except Exception as exc:
                        sys.stderr.write("credit error: %s\n" % exc)

        def serve_one(pair):
            idx, task = pair
            mem_at_serve = len(store.load())                 # snapshot: memory visible when served
            mem_block, injected_ids = inject(task)           # live retrieval (eventually-consistent)
            try:
                resp, cost = llm.call_claude(env.build_prompt(task, mem_block),
                                             allowed_tools="Read", return_cost=True)
            except Exception as exc:
                resp, cost = "", 0.0
                sys.stderr.write("target error @%d: %s\n" % (idx, exc))
            try:
                ev = env.score(task, resp)
            except Exception as exc:
                sys.stderr.write("score error @%d: %s\n" % (idx, exc))
                ev = {"em": 0.0, "f1": 0.0, "sub_em": 0.0, "predicted_answer": ""}
            learn_futs.append(learn_ex.submit(learn_job, task, resp, ev, injected_ids))  # async learn
            sys.stderr.write("[%s seed%d %s/serve] %3d/%d em=%.0f mem@serve=%d $%.4f\n"
                             % (args.method, args.seed, phase, idx + 1, len(stream),
                                ev["em"], mem_at_serve, cost))
            return {"idx": idx, "id": task["id"], "em": ev["em"], "f1": ev["f1"],
                    "sub_em": ev["sub_em"], "pred": ev["predicted_answer"][:80],
                    "mem_at_serve": mem_at_serve, "_cost": cost}

        c0, _ = cum_cost()
        partials = llm.pmap(serve_one, list(enumerate(stream)), args.deploy_workers)
        concurrent.futures.wait(learn_futs)                  # DRAIN background learning before freeze
        learn_ex.shutdown(wait=True)
        rows, run = [], c0
        for p in sorted(partials, key=lambda r: r["idx"]):
            run += p["_cost"]
            rows.append({
                "idx": p["idx"], "phase": phase, "id": p["id"], "em": p["em"], "f1": p["f1"],
                "sub_em": p["sub_em"], "pred": p["pred"], "n_bullets": p["mem_at_serve"],
                "n_episodes": 0, "max_uses": 0, "max_helpful": 0, "n_active_skills": 0,
                "cum_cost_usd": round(run, 6), "cum_output_tokens": 0,
            })
        sys.stderr.write("[%s seed%d] SERVING acquire done: %d served, final store=%d bullets, "
                         "%d episodes (learning drained)\n"
                         % (args.method, args.seed, len(rows), len(store.load()),
                            len(episodic.load()) if args.method in ("episodic", "ours_full") else 0))
        return rows

    def learn_stream(stream, phase):
        """Route a learning phase: serving (concurrent serve + async learn) when requested for a
        learning method, else strict-sequential prequential (or parallel for no-writes methods)."""
        if args.acquire_mode == "serving" and args.method in LEARN_METHODS and args.deploy_workers > 1:
            return serve_and_learn(stream, phase)
        return run_phase(stream, learn=True, phase=phase)

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.protocol == "frozen":
        # ACQUIRE on train (only methods that learn online — external paid its cost up front in
        # train_external; no_memory has nothing) -> final consolidation -> FREEZE -> DEPLOY on test.
        acq_rows = []
        if args.method in LEARN_METHODS:
            acq_rows = learn_stream(train_tasks, "acquire")
            if args.method == "ours_full":
                try:
                    consolidate(len(train_tasks) - 1)   # capture late-acquired memory before freezing
                except Exception as exc:
                    sys.stderr.write("final consolidate error: %s\n" % exc)
        sys.stderr.write("[%s seed%d] FROZEN after %d acquire tasks; deploying on %d held-out test "
                         "(deploy_workers=%d)...\n"
                         % (args.method, args.seed, len(acq_rows), len(tasks), args.deploy_workers))
        rows = run_phase(tasks, learn=False, phase="test")
        if acq_rows:                                    # keep the acquisition trace for diagnostics
            acq_path = out.with_name(out.stem + "_acquire" + out.suffix)
            with acq_path.open("w", encoding="utf-8") as f:
                for r in acq_rows:
                    f.write(json.dumps(r) + "\n")
    else:
        rows = learn_stream(tasks, "eval")                  # prequential: eval stream IS the learn stream

    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    em = sum(r["em"] for r in rows) / max(1, len(rows))
    f1 = sum(r["f1"] for r in rows) / max(1, len(rows))
    sys.stderr.write("DONE %s seed%d [%s]: EM=%.3f F1=%.3f cum=$%.4f -> %s\n"
                     % (args.method, args.seed, args.protocol, em, f1,
                        rows[-1]["cum_cost_usd"] if rows else 0, out))


if __name__ == "__main__":
    main()
