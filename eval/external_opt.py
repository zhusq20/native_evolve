"""SkillOpt/GEPA-style external optimizer baseline (C2).

Paradigm contrast vs ours: this optimizes ONE global SKILL.md OFFLINE on a
disjoint training split, then FREEZES it for evaluation (no online learning).
The training cost (rollouts + synthesis) is paid up front and — because every
call goes through evolve.llm — is captured in the same NATIVE_EVOLVE_LEDGER, so
the accuracy-vs-cumulative-cost figure counts it fairly.

Implemented on the same `claude` CLI + same target model as every other method,
so the comparison isolates the PARADIGM (offline external vs online native), not
the model or harness.
"""
import json

from evolve import config, llm


def train_external(train_tasks, env, rounds=1):
    """Run the target on train tasks, then synthesize one global SKILL.md.

    Returns the SKILL.md text (frozen skill injected at eval time).
    rounds>1 iterates: re-run with the current draft, re-synthesize (GEPA-like).
    env provides build_prompt/score (env-agnostic).
    """
    skill_md = ""
    for _ in range(max(1, rounds)):
        examples = []
        for t in train_tasks:
            block = skill_md and ("## Skill (current draft)\n" + skill_md + "\n\n")
            prompt = env.build_prompt(t, block or "")
            try:
                resp = llm.call_claude(prompt, allowed_tools="Read")
            except Exception:
                resp = ""
            ev = env.score(t, resp)
            examples.append({
                "q": t["question"][:200],
                "agent": ev.get("predicted_answer", "")[:120],
                "correct": ev["em"] == 1.0,
                "gold": ev.get("gold_answers", t.get("answers")),
            })
        tmpl = (config.PROMPTS_DIR / "external_optimizer.md").read_text(encoding="utf-8")
        batch = "\n".join(
            "Q: %s\n  agent: %s\n  correct: %s\n  gold: %s"
            % (e["q"], e["agent"], e["correct"], json.dumps(e["gold"]))
            for e in examples
        )
        skill_md = llm.call_claude(
            tmpl + "\n\n=== TRAINING EXAMPLES ===\n" + batch, allowed_tools="Read"
        )
    return skill_md
