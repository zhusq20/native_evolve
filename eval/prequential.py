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
import tempfile

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


def monotone_repair(resp, verify, repair_call, repair_turns, make_hint):
    """Verify-gated, MONOTONE repair loop. Returns (result, sigs, trace, ncalls).

    THE INVARIANT (why a noisy verify can never drop us BELOW the single-shot baseline): the returned
    `result` is the single-shot `resp` UNLESS some repair attempt VERIFY-PASSES. A repair is adopted
    ONLY when re-verification says ok; a repair that still fails verify is NEVER returned (we keep the
    baseline and, at most, iterate from the failing candidate for extra context). This closes two bugs in
    the old loop: (1) it blindly replaced `resp` with the repair without checking it improved anything, so
    an over-firing signal that rejected a CORRECT first attempt would swap in a worse one and score it —
    dropping BELOW baseline; (2) with repair_turns=1 the final repair was scored without ever being
    verified. `verify(r)->verdict|None`; `repair_call(verdict, hint)->str` (may raise); `make_hint(sig)
    ->str`. The result is what the caller should SCORE and record (consistent with the trace)."""
    result = resp
    sigs, trace, ncalls = [], [], 0
    if repair_turns <= 0:
        return result, sigs, trace, ncalls
    cur, vr = resp, verify(resp)
    for _ in range(repair_turns):
        if not vr or vr.get("ok"):                   # current attempt verifies (or is unverifiable)
            break
        sig = vr.get("signature", "")
        try:
            cand = repair_call(vr, make_hint(sig))
        except Exception as exc:                     # noqa: BLE001
            sys.stderr.write("repair call error: %s\n" % exc)
            break
        cand_vr = verify(cand)
        ncalls += 1
        sigs.append(sig)
        trace.append({"signature": sig, "feedback": vr.get("feedback", ""),
                      "before": cur, "after": cand})
        if cand_vr is not None and cand_vr.get("ok"):
            result = cand                            # repair RESOLVED the issue -> adopt it & stop
            break
        if cand_vr is None:
            break                                    # can't evaluate the repair -> keep baseline
        cur, vr = cand, cand_vr                      # still failing -> keep baseline, iterate from cand
    return result, sigs, trace, ncalls


# ---- correctness SIGNAL: reference-free (deploy-available) vs the GOLD oracle ----
# The self-evolving system's own credit / reflect / gate must run on a signal a REAL deployment has.
# self_verify (execution / in-prompt constraints / self-critique) is that signal — it reads NO gold.
# env.score (gold EM) is the OUTSIDE measurement (the eval overlay) and an opt-in oracle CEILING. These
# helpers are module-level + pure so the routing is unit-testable (see eval/test_signal_routing.py).
# Field context (papers/): every offline optimizer gates on GOLD; "reference-free self-eval driving
# ONLINE deploy evolution" is the gap this makes measurable. See memory/native-design-law.md.

def reffree_verdict(self_verify_fn, task, resp, env):
    """Reference-free verdict {ok, signature, feedback}, or None when nothing was checkable."""
    try:
        return self_verify_fn(task, resp, env)
    except Exception:
        return None


def reffree_ok(self_verify_fn, task, resp, env):
    """Reference-free correctness bool, or None when the signal is UNAVAILABLE (caller degrades)."""
    vr = reffree_verdict(self_verify_fn, task, resp, env)
    return None if vr is None else bool(vr.get("ok"))


def make_judge(signal, env, self_verify_fn):
    """Build the gate's judge(task, resp) -> bool. signal='oracle' -> GOLD (env.score em == 1.0; the
    measurement ceiling, NOT deploy-available). signal='reffree' -> reference-free self_verify ok
    (deploy-available, no gold); an UNAVAILABLE verdict counts as NOT-ok, so the rolling gate's
    margin/non-dilution guard cannot activate a skill on a missing/noisy signal (precision law)."""
    if signal == "oracle":
        return lambda task, resp: env.score(task, resp).get("em") == 1.0
    return lambda task, resp: bool(reffree_ok(self_verify_fn, task, resp, env))


def reffree_evidence_dict(task, resp, ev, vr):
    """Deploy-faithful reflection evidence: built from the REFERENCE-FREE verdict `vr` + the repair
    trace, NEVER from gold (no reference answer, no gold value-diff / N3 — its honest cost). Pure ->
    testable; render with envs.render_evidence (it skips the gold/diagnosis fields this omits)."""
    ok = None if vr is None else bool(vr.get("ok"))
    if ok is True:
        outcome = ("self-check PASSED (no reference-free violation detected; the answer may still be "
                   "wrong in ways no gold-free check can see)")
    elif ok is False:
        outcome = "self-check FAILED: " + ((vr or {}).get("feedback", "") or "")
    else:
        outcome = "no reference-free check was available for this attempt"
    d = {"outcome": outcome,
         "task": (task.get("prompt") or task.get("question") or "")[:1500],
         "predicted": ((ev or {}).get("predicted_answer") or resp or "")[:1500]}
    trace = ev.get("_repair_trace") if isinstance(ev, dict) else None
    if trace:
        d["repair"] = ("This task needed %d self-repair round(s) before the final answer. Record a "
                       "transferable heuristic to AVOID this failure mode up front:\n" % len(trace)
                       + "\n".join("round %d: attempt failed [%s] — %s"
                                   % (i, s.get("signature", ""), (s.get("feedback", "") or "")[:300])
                                   for i, s in enumerate(trace, 1)))
    return d


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
    ap.add_argument("--gate_min_n", type=int, default=18,
                    help="rolling consolidation gate: min CUMULATIVE A/B val tasks (across "
                         "checkpoints) before a skill set may activate (power floor).")
    ap.add_argument("--gate_margin", type=int, default=2,
                    help="rolling gate: required cumulative (with-skill minus base) passes; combined "
                         "with a non-dilution guard (broke <= rescued) to kill false-positives.")
    ap.add_argument("--gate_audit", action="store_true",
                    help="precision-law-FOR-GATING audit: at the consolidation gate, solve the val A/B "
                         "ONCE and score it with BOTH the oracle (gold) AND the reffree (self_verify) "
                         "judge on the IDENTICAL answers, logging both decisions to home/gate_audit.json "
                         "(clean shared-acquisition isolation of the gate signal). The LIVE decision "
                         "still follows --gate_signal. No-op when no candidate is induced.")
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
    ap.add_argument("--batch_size", type=int, default=1,
                    help="BOUNDED-STALENESS parallel prequential: solve B tasks concurrently against "
                         "one committed memory snapshot, then learn before the next batch. Speedup ~B; "
                         "memory staleness <= B tasks (vs whole-stream under full serving). 1 = strict "
                         "sequential (max memory fidelity). Applies to learning methods only.")
    ap.add_argument("--repair_turns", type=int, default=0,
                    help="max CONDITIONAL repair rounds per task (0=single-shot). A round fires "
                         "only when env.verify (REFERENCE-FREE, reads no gold) rejects the attempt, "
                         "so it is valid even at frozen-test time and free when the first attempt "
                         "verifies. Each round is one extra claude call, billed to the ledger. "
                         "REPAIR IS A SEPARATE, LABELED LEVER (design (a)): default 0 keeps it OFF, "
                         "and MEMORY claims are always read off this repair=0 column. To study repair, "
                         "report the memory x repair 2x2 (this flag x methods) explicitly — never fold "
                         "repair into a 'memory helps' number.")
    ap.add_argument("--repair_methods", default="ours",
                    help="when --repair_turns>0, which methods get the repair lever: 'ours' "
                         "(episodic/ours_mem/ours_full = the repair-ON cell), 'all' (every arm — for "
                         "the clean memory x repair 2x2), or a comma list ('no_memory' = the "
                         "apparatus-only ablation arm). Repair is a labeled lever, NOT part of memory.")
    ap.add_argument("--verify_mode", choices=["oracle", "self", "self_exec", "self_both"], default="self_both",
                    help="signal that drives the repair loop. self_both (DEFAULT, deployment-realistic): "
                         "run BOTH dataset-agnostic channels — EXECUTION + LLM semantic self-critique — "
                         "together; on a code task a clean execution stays AUTHORITATIVE so critique is "
                         "ADVISORY (enriches the failure feedback, never flips ok->fail), so it can't drag "
                         "below baseline. self: route to ONE channel by code-block (exec for code, else "
                         "critique). self_exec: dataset-agnostic, EXECUTION ONLY (no critique). oracle: "
                         "per-env verify() (dataset-AWARE ceiling/back-compat; pass explicitly for the oracle map).")
    ap.add_argument("--gate_signal", choices=["reffree", "oracle"], default="oracle",
                    help="correctness signal the skill-promotion GATE's held-out A/B decides on. oracle "
                         "(DEFAULT, back-compat): GOLD env.score — the measurement ceiling, NOT available "
                         "in a real deployment. reffree (deploy-faithful): the reference-free self_verify "
                         "the system would actually have at deploy (reads NO gold). Run both to measure the "
                         "gap = precision-law-for-gating. See memory/native-design-law.md.")
    ap.add_argument("--credit_signal", choices=["reffree", "oracle"], default="oracle",
                    help="correctness signal for episodic-success + distilled-bullet CREDIT. oracle "
                         "(DEFAULT): GOLD em. reffree: self_verify ok (deploy-available, no gold; costs "
                         "+1 verify call per learned task on non-code tasks).")
    ap.add_argument("--reflect_signal", choices=["reffree", "oracle"], default="oracle",
                    help="evidence the Reflector sees. oracle (DEFAULT): GOLD-grounded collect_evidence "
                         "(incl. the N3 semantic value-diff). reffree: reference-free evidence (self_verify "
                         "verdict + repair trace, NO gold) — deploy-faithful; loses N3 (its honest cost).")
    ap.add_argument("--agentic", action="store_true",
                    help="agentic solve: the target runs MULTI-TURN with Read/Write/Bash/Skill in a "
                         "per-task gold-isolated sandbox (writes, RUNS, and repairs its own code) "
                         "instead of single-shot text. The harness repair loop is bypassed (the agent "
                         "self-repairs) for clean attribution. Env must implement agentic_attempt (SB does).")
    ap.add_argument("--agentic_max_turns", type=int, default=20,
                    help="agentic: hard cap on agent turns per task (claude --max-turns; overflow exits).")
    ap.add_argument("--native_skills", default="",
                    help="comma list of skill names from engine/skills/ to install as DISCOVERABLE "
                         "skills in every agent sandbox (e.g. self-verify-and-repair). The "
                         "hand-authored procedural-skill arm / oracle ceiling; '' = bare-agentic ablation.")
    ap.add_argument("--retrieval", choices=["lexical", "agentic"], default="agentic",
                    help="how distilled memory is RETRIEVED for ours_mem/ours_full. agentic (DEFAULT, "
                         "native Claude Code paradigm): present a plain-text INDEX of memory one-liners "
                         "and let the MODEL select the relevant [id]s (one extra claude call/task, billed "
                         "to the ledger). lexical: deterministic bag-of-words top-k overlap score (the "
                         "pre-2026-06-06 behavior; pass explicitly to reproduce the old runs).")
    ap.add_argument("--memory_mode", choices=["inject", "native"], default="native",
                    help="HOW memory + skills reach the solving agent. native (DEFAULT, deploy-faithful): "
                         "every distilled bullet, episode, and promoted skill is written as a DISCOVERABLE "
                         "Claude Code skill (.claude/skills) and the agent NATIVELY selects/invokes what it "
                         "needs (a few-turn Skill-enabled solve); credit goes to what it ACTUALLY invoked. "
                         "inject: the pre-2026-06-08 behavior — the harness force-injects a top-k memory/skill "
                         "TEXT block into a single-shot prompt (pass explicitly to reproduce old runs; "
                         "--retrieval then applies). ace/external still inject their playbook/frozen-skill text.")
    ap.add_argument("--skill_turns", type=int, default=4,
                    help="native: claude --max-turns for the Skill-enabled solve (enough to invoke a skill "
                         "then answer). Small (default 4) -> ~1.5-3x single-shot cost, NOT the heavyweight agentic loop.")
    ap.add_argument("--skill_tools", default="Skill,Read",
                    help="native: allowed tools for the solve (claude --allowedTools). Default 'Skill,Read'. "
                         "For code envs that self-test (e.g. ARC running its solve() on the shown demos) use "
                         "'Skill,Read,Write,Edit,Bash'. Applied to ALL arms, so it doesn't confound the comparison.")
    ap.add_argument("--permission_mode", default="bypassPermissions",
                    help="native/agentic: claude --permission-mode. Default 'bypassPermissions' (headless "
                         "needs it so Skill/Bash/Write run without a prompt). Use 'acceptEdits'/'default' "
                         "only if you want interactive-style gating (will stall headless tool use).")
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

    from evolve import retrieve, reflect, store, curate, episodic, induce, verify, materialize  # noqa: E402
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import external_opt  # noqa: E402
    import envs as envs_pkg  # noqa: E402
    import self_verify as self_verify_mod  # noqa: E402
    from evolve import llm  # noqa: E402
    env = envs_pkg.get_env(args.env)

    # NATIVE skills (role A as a discoverable skill): resolve the hand-authored SKILL.md text from the
    # SOURCE engine/skills/ (NOT the per-run home, which starts empty) and pass to env.agentic_attempt.
    def _load_native_skills(names):
        out = []
        for nm in [x.strip() for x in (names or "").split(",") if x.strip()]:
            p = ENGINE_DIR / "skills" / nm / "SKILL.md"
            if p.exists():
                out.append((nm, p.read_text(encoding="utf-8")))
            else:
                sys.stderr.write("native skill not found: %s\n" % p)
        return out
    NATIVE_SKILLS = _load_native_skills(args.native_skills)
    if args.agentic:
        sys.stderr.write("[%s seed%d] AGENTIC mode: max_turns=%d native_skills=%s\n"
                         % (args.method, args.seed, args.agentic_max_turns,
                            [n for n, _ in NATIVE_SKILLS] or "(none)"))

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
    # (The actual training runs AFTER solve() is defined — below — so its rollouts go through the SAME
    # solve path the frozen skill is deployed under: no train/inference mismatch. See note near `out=`.)
    frozen_skill = ""

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

    def retrieve_distilled(q):
        """Distilled-memory retrieval, selectable via --retrieval. agentic = native paradigm
        (model selects from the index); lexical = bag-of-words top-k. Returns (block, ids).
        Used by BOTH inject() and the gate's base_block so the gate A/B compares like with like."""
        if args.retrieval == "agentic":
            return retrieve.select_and_block_agentic(q)
        return retrieve.select_and_block(q)

    def base_block(t):
        """Episodic + distilled injection — the episodic-first baseline the gate must beat."""
        epi = episodic.exemplar_block(t["question"])
        dis, _ = retrieve_distilled(t["question"])
        return "\n\n".join(x for x in (epi, dis) if x)

    def consolidate_native(idx, cands):
        """NATIVE gate: judge a candidate by PRESENCE in the discoverable catalog, not by injected
        text. base arm = native_solve with the current catalog (episodic+distilled+active skills);
        full arm = same catalog + the candidate skills as discoverable. The agent decides whether to
        invoke the candidate — so the gate also tests 'is the candidate's description good enough to be
        picked', exactly as deployment would. Reuses gate_tally / signal_agreement / rolling_decision
        (identical accept rule + rolling state as the text-injection gate)."""
        cand_pairs = [(c["name"], c["md"]) for c in cands]
        audit = getattr(args, "gate_audit", False)
        if audit:
            judges = {"oracle": make_judge("oracle", env, self_verify_mod.self_verify),
                      "reffree": make_judge("reffree", env, self_verify_mod.self_verify)}
        else:
            judges = {"live": make_judge(args.gate_signal, env, self_verify_mod.self_verify)}

        def _pair(t):
            # solve base & full ONCE each, score with every judge on the IDENTICAL answers
            rb = native_solve(t, "", extra_skills=None, want_cost=True)[0]
            rf = native_solve(t, "", extra_skills=cand_pairs, want_cost=True)[0]
            row = {}
            for nm, j in judges.items():
                try: row[nm + "_base"] = int(bool(j(t, rb)))
                except Exception: row[nm + "_base"] = 0
                try: row[nm + "_full"] = int(bool(j(t, rf)))
                except Exception: row[nm + "_full"] = 0
            return row
        rows = llm.pmap(_pair, verify_tasks, args.deploy_workers)

        if audit:
            t_or = verify.gate_tally(rows, "oracle", min_n=args.gate_min_n, margin=args.gate_margin)
            t_rf = verify.gate_tally(rows, "reffree", min_n=args.gate_min_n, margin=args.gate_margin)
            sig = verify.signal_agreement(rows, "oracle", "reffree")
            agree = (t_or["activate"] == t_rf["activate"])
            audit_obj = {"idx": idx, "candidates": [c["name"] for c in cands], "mode": "native",
                         "oracle": t_or, "reffree": t_rf, "agree": agree,
                         "signal_agreement": sig, "live_signal": args.gate_signal}
            try:
                (home / "memory" / "gate_audit.json").write_text(json.dumps(audit_obj, indent=2),
                                                                 encoding="utf-8")
            except Exception as exc:
                sys.stderr.write("gate_audit write error: %s\n" % exc)
            activate = (t_rf if args.gate_signal == "reffree" else t_or)["activate"]
            for c in cands:
                induce.write_skill(c, status=("active" if activate else "candidate"))
            sys.stderr.write(
                "[gate_audit native @%d] %d cand(s) | ORACLE rescued=%d broke=%d act=%s | "
                "REFFREE rescued=%d broke=%d act=%s | AGREE=%s | base_fail_agree=%.2f (gold_fail=%d) | live=%s\n"
                % (idx, len(cands), t_or["rescued"], t_or["broke"], t_or["activate"],
                   t_rf["rescued"], t_rf["broke"], t_rf["activate"], agree,
                   sig["base_fail_agree"], sig["n_base_fail"], args.gate_signal))
            return

        prod_rows = [{"base_em": r["live_base"], "full_em": r["live_full"]} for r in rows]
        bp, fp, vn, activate, info = verify.rolling_decision(
            prod_rows, str(home / "memory" / "gate_window.json"),
            min_n=args.gate_min_n, margin=args.gate_margin)
        for c in cands:
            induce.write_skill(c, status=("active" if activate else "candidate"))
        sys.stderr.write("[consolidate native @%d] rolling gate (%s): cum base %d -> +skills %d (n=%d, "
                         "rescued=%d broke=%d sat=%s) => %s\n"
                         % (idx, args.gate_signal, bp, fp, vn, info["rescued"], info["broke"],
                            info["decision"]["saturated"],
                            ("ACTIVATE %d skills" % len(cands)) if activate
                            else "REJECT/candidate (degrade)"))

    def consolidate(idx):
        """Non-destructive, GATED consolidation: induce skills from memory, activate them ONLY
        if they lift held-out accuracy over the episodic+distilled baseline; else keep them as
        candidates so ours_full degrades gracefully to episodic+distilled (never below)."""
        cands = induce.induce(focus_failures=True)
        if not cands:
            return
        if args.memory_mode == "native":
            return consolidate_native(idx, cands)
        # NO train/inference MISMATCH (skill presentation): show CANDIDATE skills to the gate EXACTLY
        # as inference shows ACTIVE skills — same render_skills_block (top-k by relevance, compacted,
        # same header), appended AFTER the episodic+distilled base (skill LAST), per inject() order.
        cand_skills = [{"name": c["name"], "md": c["md"], "value": 0} for c in cands]
        skill_block_fn = lambda t: retrieve.render_skills_block(cand_skills, t["question"], k=3)
        # NO train/inference MISMATCH (solve path): judge the A/B via the harness's REAL serve path
        # (single-shot + repair, or agentic) so a skill is rated on the answer it will ACTUALLY face
        # at inference, not a bare single-shot. (For repair_turns=0 this is identical cost to before.)
        gate_solve = lambda task, mem: solve(task, mem, want_cost=True)[0]
        # GATE SIGNAL (A1): reffree = deploy-faithful self_verify A/B (no gold); oracle = GOLD env.score.
        if getattr(args, "gate_audit", False):
            # PRECISION-LAW-FOR-GATING audit: solve the val A/B ONCE, score with BOTH judges on the
            # IDENTICAL answers (clean isolation of the gate SIGNAL — re-solving per judge would
            # re-introduce claude noise). The live decision follows --gate_signal, derived from the
            # SAME rows (no double-solve).
            judges = {"oracle": make_judge("oracle", env, self_verify_mod.self_verify),
                      "reffree": make_judge("reffree", env, self_verify_mod.self_verify)}
            rows = verify.paired_ab_multi(skill_block_fn, base_block, verify_tasks, env, judges,
                                          workers=args.deploy_workers, solve_fn=gate_solve)
            t_or = verify.gate_tally(rows, "oracle", min_n=args.gate_min_n, margin=args.gate_margin)
            t_rf = verify.gate_tally(rows, "reffree", min_n=args.gate_min_n, margin=args.gate_margin)
            sig = verify.signal_agreement(rows, "oracle", "reffree")
            agree = (t_or["activate"] == t_rf["activate"])
            audit = {"idx": idx, "candidates": [c["name"] for c in cands],
                     "oracle": t_or, "reffree": t_rf, "agree": agree,
                     "signal_agreement": sig, "live_signal": args.gate_signal}
            try:
                (home / "memory" / "gate_audit.json").write_text(json.dumps(audit, indent=2),
                                                                 encoding="utf-8")
            except Exception as exc:
                sys.stderr.write("gate_audit write error: %s\n" % exc)
            activate = (t_rf if args.gate_signal == "reffree" else t_or)["activate"]
            for c in cands:
                induce.write_skill(c, status=("active" if activate else "candidate"))
            sys.stderr.write(
                "[gate_audit @%d] %d cand(s) | ORACLE rescued=%d broke=%d (full-base=%d) act=%s | "
                "REFFREE rescued=%d broke=%d (full-base=%d) act=%s | AGREE=%s | "
                "signal base_agree=%.2f base_fail_agree=%.2f (gold_fail=%d) | live=%s\n"
                % (idx, len(cands),
                   t_or["rescued"], t_or["broke"], t_or["full_pass"] - t_or["base_pass"], t_or["activate"],
                   t_rf["rescued"], t_rf["broke"], t_rf["full_pass"] - t_rf["base_pass"], t_rf["activate"],
                   agree, sig["base_agree"], sig["base_fail_agree"], sig["n_base_fail"], args.gate_signal))
            return
        gate_judge = make_judge(args.gate_signal, env, self_verify_mod.self_verify)
        bp, fp, vn, activate, info = verify.rolling_gate(
            skill_block_fn, base_block, verify_tasks, env,
            state_path=str(home / "memory" / "gate_window.json"),
            workers=args.deploy_workers, min_n=args.gate_min_n, margin=args.gate_margin,
            judge=gate_judge, solve_fn=gate_solve)
        for c in cands:
            induce.write_skill(c, status=("active" if activate else "candidate"))
        sys.stderr.write("[consolidate @%d] rolling gate (%s): cum base %d -> +skills %d (n=%d, "
                         "rescued=%d broke=%d sat=%s) => %s\n"
                         % (idx, args.gate_signal, bp, fp, vn, info["rescued"], info["broke"],
                            info["decision"]["saturated"],
                            ("ACTIVATE %d skills" % len(cands)) if activate
                            else "REJECT/candidate (degrade)"))

    LEARN_METHODS = ("episodic", "ours_mem", "ours_full", "ace")
    OURS_METHODS = ("episodic", "ours_mem", "ours_full")

    def _repair_budget():
        """How many repair rounds THIS method gets. Repair is a SEPARATE, LABELED lever (design (a)):
        the DEPLOY-FAITHFUL headline keeps it OFF (repair_turns=0; native self-correction is measured
        via --agentic, where monotone_repair is bypassed). When ON, the 'ours' family is the repair-ON
        cell (the inference-time self-correction that also produces the error->fix traces the method
        learns from); baselines stay single-shot. --repair_methods overrides the set ('all' for the
        clean memory x repair 2x2, 'no_memory' for the apparatus-only ablation arm). MEMORY claims are
        always reported at repair=0 — never read a 'memory helps' delta off a repair-on run."""
        if args.repair_turns <= 0:
            return 0
        sel = (args.repair_methods or "ours").strip().lower()
        if sel == "all":
            allowed = set(("no_memory",) + LEARN_METHODS + ("external_optimizer",))
        elif sel == "ours":
            allowed = set(OURS_METHODS)
        else:
            allowed = set(s.strip() for s in sel.split(",") if s.strip())
        return args.repair_turns if args.method in allowed else 0

    REPAIR_TURNS = _repair_budget()

    def _repair_suffix(vr, hint):
        s = ("\n\n## Your previous attempt FAILED an automatic check\n"
             + (vr.get("feedback") or "(no detail)") +
             "\n\nFix exactly that problem and return ONLY the corrected final output in the "
             "required format. Do not repeat the mistake above.")
        if hint:
            s += "\n\n## A fix that worked on a past similar failure (adapt, don't copy)\n" + hint
        return s

    def _do_verify(task, resp):
        """Route the repair-loop check: oracle (per-env, dataset-aware), self (dataset-agnostic:
        execution + LLM critique), or self_exec (dataset-agnostic, execution channel only)."""
        if args.verify_mode == "self":
            return self_verify_mod.self_verify(task, resp, env)
        if args.verify_mode == "self_exec":
            return self_verify_mod.self_verify(task, resp, env, use_critique=False)
        if args.verify_mode == "self_both":   # force exec+critique together (critique stays advisory
            return self_verify_mod.self_verify(task, resp, env, use_critique=True)  # on a clean run)
        return envs_pkg.run_verify(env, task, resp)

    def _native_catalog(method):
        """Which memory enters the discoverable catalog for this method (native mode). ace/external
        keep their playbook/frozen-skill TEXT in the prompt (via inject) + an EMPTY catalog, so the
        C1 contrast is clean: dump-everything-in-context (ace) vs agent-selects-from-catalog (ours)."""
        if method == "ours_full":
            return store.load(), episodic.load(), True
        if method == "ours_mem":
            return store.load(), [], False
        if method == "episodic":
            return [], episodic.load(), False
        return [], [], False     # no_memory / ace / external_optimizer

    _NATIVE_NUDGE = (
        "\n\nYou have access to project Skills capturing lessons and worked examples distilled from "
        "PAST tasks. Review the available skills and INVOKE any that are genuinely relevant before you "
        "answer; if none apply, just answer. Then give your final answer in the required format."
    )
    _POST_HOOK = ENGINE_DIR / "adapters" / "claude_code" / "hook_post_tool_use.py"

    def native_solve(task, mem_block, extra_skills=None, want_cost=False):
        """Skill-discovery-enabled solve (the deploy-faithful NATIVE path). Materializes memory + the
        promoted skills as a discoverable .claude/skills catalog in a per-task sandbox, lets the agent
        invoke what it needs over a few turns, and credits exactly what it INVOKED (read from a
        PostToolUse hook). The harness repair loop is bypassed (native self-correction), mirroring the
        --agentic branch. Returns (resp, ev, meta) with meta['invoked_ids'] = distilled-bullet ids used.
        `extra_skills` (a list of (name, md) pairs) adds CANDIDATE skills to the catalog — the gate's
        'full' arm presents candidates as discoverable, exactly as inference would present them active."""
        items, eps, inc_promoted = _native_catalog(args.method)
        sandbox = tempfile.mkdtemp(prefix="native_")
        invoked_path = os.path.join(sandbox, ".invoked")
        cost = 0.0
        try:
            known_names = materialize.setup_sandbox(
                sandbox, _POST_HOOK, invoked_path, items=items, episodes=eps,
                include_promoted=inc_promoted, extra_skills=(extra_skills or None))
            prompt = env.build_prompt(task, mem_block) + _NATIVE_NUDGE
            resp = ""
            try:
                r = llm.call_claude(
                    prompt, allowed_tools=args.skill_tools, cwd=sandbox, add_dir=sandbox,
                    setting_sources="project", permission_mode=args.permission_mode,
                    max_turns=args.skill_turns, max_retries=1, timeout=900, return_cost=True)
                resp, c = r if isinstance(r, tuple) else (r, 0.0)
                cost += c
            except Exception as exc:                       # turn-cap overflow / transient
                sys.stderr.write("native target error: %s\n" % exc)
            try:
                log = open(invoked_path, encoding="utf-8").read() if os.path.exists(invoked_path) else ""
            except Exception:
                log = ""
            invoked = materialize.match_invoked(log, known_names)
            invoked_ids = materialize.invoked_to_bullet_ids(invoked)
            try:
                ev = env.score(task, resp)
            except Exception as exc:
                sys.stderr.write("score error: %s\n" % exc)
                ev = {"em": 0.0, "f1": 0.0, "sub_em": 0.0, "predicted_answer": ""}
            if isinstance(ev, dict):
                ev["_native"] = True
                ev["_invoked"] = invoked
            return resp, ev, {"repair_calls": 0, "signatures": [], "cost": cost,
                              "trace": [], "invoked_ids": invoked_ids}
        finally:
            if os.environ.get("NATIVE_EVOLVE_KEEP_SANDBOX") != "1":
                shutil.rmtree(sandbox, ignore_errors=True)

    def _credit_ids(injected_ids, meta):
        """Bullets to credit for a learned task: what the agent INVOKED (native) or, in the legacy
        inject mode, what the harness injected. Keeps all credit call-sites mode-agnostic."""
        if args.memory_mode == "native":
            return meta.get("invoked_ids", []) if isinstance(meta, dict) else []
        return injected_ids

    def solve(task, mem_block, want_cost=False):
        """Single-shot target call + up to REPAIR_TURNS CONDITIONAL repair rounds. A round fires
        only when env.verify (REFERENCE-FREE; reads no gold) rejects the attempt, so the loop is
        valid even during the frozen TEST phase and costs nothing when the first attempt verifies.
        Returns (resp, ev, meta) with meta = {repair_calls, signatures, cost, trace}; `trace` is the
        list of error->fix pairs used by repair-grounded reflection (Phase 2)."""
        if args.memory_mode == "native":
            # Deploy-faithful: memory/skills as a discoverable catalog, agent selects natively.
            # (Mutually exclusive with --agentic's heavyweight write/run/repair sandbox.)
            return native_solve(task, mem_block, extra_skills=None, want_cost=want_cost)
        base = env.build_prompt(task, mem_block)
        cost = [0.0]

        if args.agentic and hasattr(env, "agentic_attempt"):
            # Multi-turn agentic solve: the agent writes, RUNS, and repairs its own code in a
            # gold-isolated sandbox, optionally using the native verify-repair skill. The harness
            # repair loop is BYPASSED (repair_calls=0) so the gain is attributable to the agent +
            # skill, not to monotone_repair. score()/the gate stay external + gold-isolated.
            resp, c = env.agentic_attempt(task, mem_block, NATIVE_SKILLS,
                                          args.agentic_max_turns, llm.call_claude, want_cost=True)
            cost[0] += c
            try:
                ev = env.score(task, resp)
            except Exception as exc:
                sys.stderr.write("score error: %s\n" % exc)
                ev = {"em": 0.0, "f1": 0.0, "sub_em": 0.0, "predicted_answer": ""}
            if isinstance(ev, dict):
                ev["_agentic"] = True
            return resp, ev, {"repair_calls": 0, "signatures": [], "cost": cost[0], "trace": []}

        def _call(prompt):
            if want_cost:
                r, c = llm.call_claude(prompt, allowed_tools="Read", return_cost=True)
                cost[0] += c
                return r
            return llm.call_claude(prompt, allowed_tools="Read")

        try:
            resp = _call(base)
        except Exception as exc:
            resp = ""
            sys.stderr.write("target error: %s\n" % exc)

        def _verify(r):
            try:
                return _do_verify(task, r)
            except Exception:
                return None

        def _make_hint(sig):
            hint_fn = getattr(episodic, "repair_hint", None)         # Phase 2 fills this in
            if hint_fn and args.method in ("episodic", "ours_full"):
                try:
                    return hint_fn(task.get("question", ""), sig)
                except Exception:
                    return ""
            return ""

        # MONOTONE repair: only a VERIFY-PASSING repair replaces the single-shot attempt, so a noisy /
        # over-firing verify (e.g. critique nitpicking correct code) can never score BELOW baseline.
        result, sigs, trace, ncalls = monotone_repair(
            resp, _verify, lambda vr, hint: _call(base + _repair_suffix(vr, hint)),
            REPAIR_TURNS, _make_hint)
        try:
            ev = env.score(task, result)
        except Exception as exc:
            sys.stderr.write("score error: %s\n" % exc)
            ev = {"em": 0.0, "f1": 0.0, "sub_em": 0.0, "predicted_answer": ""}
        if isinstance(ev, dict) and trace:               # let reflection see the error->fix path
            ev["_repair_trace"] = trace                  # (rendered into evidence via collect_evidence)
            ev["_repair_signatures"] = sigs              # failure modes overcome (-> episodic signature)
        return result, ev, {"repair_calls": ncalls, "signatures": sigs,
                            "cost": cost[0], "trace": trace}

    def inject(task):
        """Build the injected memory/skill block for the current method (read-only retrieval)."""
        q = task["question"]
        injected_ids = []
        if args.memory_mode == "native":
            # ours_*/episodic memory becomes the discoverable CATALOG (built in native_solve), not
            # in-prompt text -> no injected_ids (credit = what the agent invokes). ace/external still
            # put their playbook/frozen-skill text in the prompt (the single-tier-dump contrast).
            if args.method == "ace":
                return retrieve.full_playbook_block(), []
            if args.method == "external_optimizer":
                return (("## Skill (offline-optimized, frozen)\n" + frozen_skill) if frozen_skill else ""), []
            return "", []
        if args.method == "episodic":
            mem = episodic.exemplar_block(q)                    # raw past-success exemplars (episodic-only)
        elif args.method == "ours_mem":
            mem, injected_ids = retrieve_distilled(q)           # distilled memory (lexical|agentic)
        elif args.method == "ours_full":
            epi = episodic.exemplar_block(q)                    # episodic exemplars
            dis, injected_ids = retrieve_distilled(q)           # distilled memory (lexical|agentic)
            skl = retrieve.skills_block(q)                      # gated, verified skills (often none)
            mem = "\n\n".join(x for x in (epi, dis, skl) if x)
        elif args.method == "ace":
            mem = retrieve.full_playbook_block()                # single-tier: full playbook
        elif args.method == "external_optimizer":
            mem = ("## Skill (offline-optimized, frozen)\n" + frozen_skill) if frozen_skill else ""
        else:
            mem = ""                                            # no_memory
        return mem, injected_ids

    def _learn_signals(task, resp, ev):
        """(success_bool, reflect_evidence_str) for a learned task under --credit_signal/--reflect_signal.
        reffree = deploy-available self_verify (NO gold; the system's own signal); oracle = GOLD
        (env.score em / gold-grounded collect_evidence, incl. N3). The reference-free verdict is computed
        AT MOST ONCE and reused for both the success flag (episode + credit, A2) and the reflection
        evidence (A3). `success` is the credit signal; on a rare UNAVAILABLE reffree verdict it falls
        back to gold so the episode still records a label."""
        vr = None
        if args.credit_signal == "reffree" or args.reflect_signal == "reffree":
            vr = reffree_verdict(self_verify_mod.self_verify, task, resp, env)
        if args.credit_signal == "oracle" or vr is None:
            succ = (ev.get("em") == 1.0)
        else:
            succ = bool(vr.get("ok"))
        if args.reflect_signal == "oracle":
            evi = envs_pkg.render_evidence(envs_pkg.collect_evidence(env, task, resp, ev))
        else:
            evi = envs_pkg.render_evidence(reffree_evidence_dict(task, resp, ev, vr))
        return succ, evi

    def process(task, idx, learn, phase):
        """One task: inject -> target call -> score. If learn, update memory (record/credit/reflect).
        Deployment (learn=False) is pure inference on a FROZEN store: the held-out test phase."""
        q = task["question"]
        mem_block, injected_ids = inject(task)
        resp, ev, meta = solve(task, mem_block)

        if learn:
            # ONE reference-free verdict per learned task (deploy-available), reused for episode-success,
            # credit (A2), and reflection evidence (A3). Computed only when a reffree signal is selected.
            succ, evi = _learn_signals(task, resp, ev)
            # record the RAW EPISODE (episodic-first methods): first-class, append-only
            if args.method in ("episodic", "ours_full"):
                try:
                    episodic.record(task["id"], q, resp, succ,
                                    signature=(ev.get("_repair_signatures") or [""])[-1])
                except Exception as exc:
                    sys.stderr.write("episode record error @%d: %s\n" % (idx, exc))
            # credit distilled bullets (deterministic; A2 signal = --credit_signal). native: what the
            # agent INVOKED (meta.invoked_ids); inject: what was force-injected (injected_ids).
            if args.method in ("ours_mem", "ours_full"):
                cids = _credit_ids(injected_ids, meta)
                if cids:
                    try:
                        curate.credit(cids, succ)
                    except Exception as exc:
                        sys.stderr.write("credit error @%d: %s\n" % (idx, exc))
            # reflect -> distilled memory (promote_skills=False: consolidation is the gated induce step)
            if args.method in ("ours_mem", "ours_full", "ace"):
                try:
                    reflect.run(summary=evi, promote_skills=False)
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
            "n_active_skills": n_active_skills, "repair_calls": meta["repair_calls"],
            "cum_cost_usd": round(cc, 6), "cum_output_tokens": ct,
        }
        sys.stderr.write(
            "[%s seed%d %s] %2d em=%.0f f1=%.2f bul=%d ep=%d uses<=%d skills=%d rep=%d cum=$%.4f\n"
            % (args.method, args.seed, phase, idx + 1, ev["em"], ev["f1"],
               row["n_bullets"], n_episodes, row["max_uses"], n_active_skills,
               meta["repair_calls"], cc))
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
            resp, ev, meta = solve(task, mem_block, want_cost=True)   # solve handles target/score errors
            cost = meta["cost"]
            sys.stderr.write("[%s seed%d %s] %3d/%d em=%.0f f1=%.2f rep=%d $%.4f\n"
                             % (args.method, args.seed, phase, idx + 1, len(stream),
                                ev["em"], ev["f1"], meta["repair_calls"], cost))
            return {"idx": idx, "id": task["id"], "em": ev["em"], "f1": ev["f1"],
                    "sub_em": ev["sub_em"], "pred": ev["predicted_answer"][:80],
                    "repair_calls": meta["repair_calls"], "_cost": cost}

        partials = llm.pmap(one, list(enumerate(stream)), args.deploy_workers)
        out_rows, run = [], c0
        for p in sorted(partials, key=lambda r: r["idx"]):
            run += p["_cost"]
            out_rows.append({
                "idx": p["idx"], "phase": phase, "id": p["id"], "em": p["em"], "f1": p["f1"],
                "sub_em": p["sub_em"], "pred": p["pred"], "n_bullets": stat["n_bullets"],
                "n_episodes": stat["n_episodes"], "max_uses": stat["max_uses"],
                "max_helpful": stat["max_helpful"], "n_active_skills": stat["n_active_skills"],
                "repair_calls": p["repair_calls"],
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

        def learn_job(task, resp, ev, credit_ids):
            deltas = []
            # reffree verdict + reflection evidence (A2/A3) OUTSIDE the lock — the expensive parallel half
            succ, evi = _learn_signals(task, resp, ev)
            if args.method in ("ours_mem", "ours_full", "ace"):
                try:
                    deltas = reflect.reflect_deltas(evi)               # parallel (no lock)
                except Exception as exc:
                    sys.stderr.write("reflect error: %s\n" % exc)
            with store.STORE_LOCK:                                                    # serialized + atomic
                if args.method in ("episodic", "ours_full"):
                    try:
                        episodic.record(task["id"], task["question"], resp, succ,
                                        signature=(ev.get("_repair_signatures") or [""])[-1])
                    except Exception as exc:
                        sys.stderr.write("episode record error: %s\n" % exc)
                if deltas:
                    try:
                        curate.merge(deltas)
                    except Exception as exc:
                        sys.stderr.write("curate error: %s\n" % exc)
                if args.method in ("ours_mem", "ours_full") and credit_ids:
                    try:
                        curate.credit(credit_ids, succ)
                    except Exception as exc:
                        sys.stderr.write("credit error: %s\n" % exc)

        def serve_one(pair):
            idx, task = pair
            mem_at_serve = len(store.load())                 # snapshot: memory visible when served
            mem_block, injected_ids = inject(task)           # live retrieval (eventually-consistent)
            resp, ev, meta = solve(task, mem_block, want_cost=True)   # repair loop + robust errors
            cost = meta["cost"]
            credit_ids = _credit_ids(injected_ids, meta)             # native: invoked; inject: injected
            learn_futs.append(learn_ex.submit(learn_job, task, resp, ev, credit_ids))  # async learn
            sys.stderr.write("[%s seed%d %s/serve] %3d/%d em=%.0f mem@serve=%d rep=%d $%.4f\n"
                             % (args.method, args.seed, phase, idx + 1, len(stream),
                                ev["em"], mem_at_serve, meta["repair_calls"], cost))
            return {"idx": idx, "id": task["id"], "em": ev["em"], "f1": ev["f1"],
                    "sub_em": ev["sub_em"], "pred": ev["predicted_answer"][:80],
                    "mem_at_serve": mem_at_serve, "repair_calls": meta["repair_calls"], "_cost": cost}

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
                "repair_calls": p["repair_calls"],
                "cum_cost_usd": round(run, 6), "cum_output_tokens": 0,
            })
        sys.stderr.write("[%s seed%d] SERVING acquire done: %d served, final store=%d bullets, "
                         "%d episodes (learning drained)\n"
                         % (args.method, args.seed, len(rows), len(store.load()),
                            len(episodic.load()) if args.method in ("episodic", "ours_full") else 0))
        return rows

    def batched_learn(stream, phase, B):
        """BOUNDED-STALENESS parallel prequential — the speed<->memory-fidelity tradeoff knob.

        Process the stream in chunks of B. All B tasks in a chunk are SOLVED CONCURRENTLY against the
        SAME committed memory snapshot (no writes happen during a chunk's solve phase), THEN learned
        from (record/credit/reflect — writes serialized) BEFORE the next chunk. So memory staleness is
        BOUNDED BY B (a task sees every lesson from tasks > B positions back), unlike full serving where
        a task may see an almost-empty store. B=1 reduces to strict-sequential prequential (max memory
        fidelity); B=N is full parallel (max speed, no online memory). The knob preserves the
        harness-observable memory while making inference B-way parallel. Consolidation fires at the chunk
        boundary that crosses each induce_every multiple. Per-row stats are read AFTER that task's learn
        (as in process()), so the curve is directly comparable to the sequential one."""
        items = list(enumerate(stream))
        workers = max(1, min(B, 16))
        rows, run = [], cum_cost()[0]
        next_induce = args.induce_every if args.induce_every > 0 else 0

        def _solve_only(pair):                                 # read-only on the store (no writes)
            idx, task = pair
            mem_at = len(store.load())
            mem_block, injected_ids = inject(task)
            resp, ev, meta = solve(task, mem_block, want_cost=True)
            succ, evi = _learn_signals(task, resp, ev)         # reffree verdict computed in PARALLEL
            return {"idx": idx, "task": task, "resp": resp, "ev": ev, "meta": meta,
                    "ids": injected_ids, "mem_at": mem_at, "succ": succ, "evi": evi}

        for c0 in range(0, len(items), B):
            chunk = items[c0:c0 + B]
            solved = llm.pmap(_solve_only, chunk, workers)      # PARALLEL solve, shared snapshot
            for s in sorted(solved, key=lambda r: r["idx"]):    # LEARN in idx order (writes serialized)
                task, resp, ev, meta, injected_ids = s["task"], s["resp"], s["ev"], s["meta"], s["ids"]
                succ, evi = s["succ"], s["evi"]                  # signals computed in the parallel phase
                if args.method in ("episodic", "ours_full"):
                    try:
                        episodic.record(task["id"], task["question"], resp, succ,
                                        signature=(ev.get("_repair_signatures") or [""])[-1])
                    except Exception as exc:
                        sys.stderr.write("episode record error @%d: %s\n" % (s["idx"], exc))
                if args.method in ("ours_mem", "ours_full"):
                    credit_ids = _credit_ids(injected_ids, meta)
                    if credit_ids:
                        try:
                            curate.credit(credit_ids, succ)
                        except Exception as exc:
                            sys.stderr.write("credit error @%d: %s\n" % (s["idx"], exc))
                if args.method in ("ours_mem", "ours_full", "ace"):
                    try:
                        reflect.run(summary=evi, promote_skills=False)
                    except Exception as exc:
                        sys.stderr.write("reflect error @%d: %s\n" % (s["idx"], exc))
                run += meta["cost"]
                bullets, skill_state = store.load(), store.load_skill_state()
                rows.append({
                    "idx": s["idx"], "phase": phase, "id": task["id"], "em": ev["em"], "f1": ev["f1"],
                    "sub_em": ev["sub_em"], "pred": ev["predicted_answer"][:80], "n_bullets": len(bullets),
                    "n_episodes": len(episodic.load()) if args.method in ("episodic", "ours_full") else 0,
                    "max_uses": max((b.get("uses", 0) for b in bullets), default=0),
                    "max_helpful": max((b.get("helpful", 0) for b in bullets), default=0),
                    "n_active_skills": sum(1 for v in skill_state.values() if v.get("status") == "active"),
                    "repair_calls": meta["repair_calls"], "cum_cost_usd": round(run, 6),
                    "cum_output_tokens": 0,
                })
            last = chunk[-1][0] + 1
            sys.stderr.write("[%s seed%d %s/B=%d] %d/%d done (mem snapshot=%d bullets)\n"
                             % (args.method, args.seed, phase, B, last, len(items),
                                solved[0]["mem_at"] if solved else 0))
            if args.method == "ours_full" and next_induce and last >= next_induce:
                try:
                    consolidate(chunk[-1][0])
                except Exception as exc:
                    sys.stderr.write("consolidate error @%d: %s\n" % (chunk[-1][0], exc))
                while next_induce and next_induce <= last:
                    next_induce += args.induce_every
        return rows

    def learn_stream(stream, phase):
        """Route a learning phase: bounded-staleness micro-batch (--batch_size>1), else serving
        (concurrent serve + async learn), else strict-sequential prequential (or parallel for
        no-writes methods)."""
        if args.batch_size > 1 and args.method in LEARN_METHODS:
            return batched_learn(stream, phase, args.batch_size)
        if args.acquire_mode == "serving" and args.method in LEARN_METHODS and args.deploy_workers > 1:
            return serve_and_learn(stream, phase)
        return run_phase(stream, learn=True, phase=phase)

    # external_optimizer offline training (deferred to here so its rollouts use the SAME solve() the
    # frozen skill is deployed under — single-shot OR repair/agentic — removing the train/inference
    # mismatch and matching SkillOpt's own (multi-turn) training harness). Cost is paid up front onto
    # the ledger before the eval loop, so the acc-vs-cumulative-cost (C2) curve counts it honestly.
    if args.method == "external_optimizer":
        sys.stderr.write("[external_optimizer seed%d] offline training on %d tasks (via solve())...\n"
                         % (args.seed, len(train_tasks)))
        frozen_skill = external_opt.train_external(
            train_tasks, env, workers=args.deploy_workers,
            solve_fn=lambda task, mem: solve(task, mem, want_cost=True)[0])

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if args.protocol == "frozen":
        # ACQUIRE on train (only methods that learn online — external paid its cost up front in
        # train_external; no_memory has nothing) -> final consolidation -> FREEZE -> DEPLOY on test.
        acq_rows = []
        if args.method in LEARN_METHODS:
            acq_rows = learn_stream(train_tasks, "acquire")
            if args.method == "ours_full" and args.induce_every > 0:
                try:
                    consolidate(len(train_tasks) - 1)   # capture late-acquired memory before freezing
                except Exception as exc:
                    sys.stderr.write("final consolidate error: %s\n" % exc)
            # NOTE: --induce_every 0 is the true SKILL-OFF arm — NO skill induction at all (neither the
            # during-acquire consolidate at line ~876 nor this final one) -> ours_full degrades to
            # episodic+distilled memory, isolating the skill tier's marginal value for the C1 boundary.
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
