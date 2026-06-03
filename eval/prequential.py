#!/usr/bin/env python3
"""One prequential run: stream tasks, test-then-train, log per task.

Method:
  no_memory  -> target only; no injection, no learning (lower bound)
  ours_full  -> inject retrieved memory before test; reflect/curate/promote after

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
                    choices=["no_memory", "ours_full", "ace", "external_optimizer"],
                    required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--train_n", type=int, default=12,
                    help="external_optimizer: # disjoint training tasks (after the eval slice)")
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

    from evolve import retrieve, reflect, store  # noqa: E402
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

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, task in enumerate(tasks):
        q = task["question"]

        # --- inject context per method ---
        if args.method == "ours_full":
            mem_block = retrieve.context_block(q)               # two-tier: top-k retrieval
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

        # --- train step (online methods only): reflect on the outcome -> memory ---
        if args.method in ("ours_full", "ace"):
            try:
                reflect.run(summary=env.summarize(task, resp, ev),
                            promote_skills=(args.method == "ours_full"))
            except Exception as exc:
                sys.stderr.write("reflect error @%d: %s\n" % (idx, exc))

        cc, ct = cum_cost()
        rows.append({
            "idx": idx, "id": task["id"], "em": ev["em"], "f1": ev["f1"],
            "sub_em": ev["sub_em"], "pred": ev["predicted_answer"][:80],
            "n_bullets": len(store.load()),
            "cum_cost_usd": round(cc, 6), "cum_output_tokens": ct,
        })
        sys.stderr.write(
            "[%s seed%d] %2d/%d em=%.0f f1=%.2f bullets=%d cum=$%.4f\n"
            % (args.method, args.seed, idx + 1, len(tasks), ev["em"], ev["f1"],
               rows[-1]["n_bullets"], cc)
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
