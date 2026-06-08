# Minimal plumbing for the isolated, grounded verifier — scope

Scopes the code to make the `self-verify-and-repair` SKILL's **isolated subagent verifier** real. Companion
to `docs/related_work_no_gold.md` (why) and `memory/verifier-isolation-subagent.md` (the decision). Plain
language; terms in `docs/glossary.md`.

## The key realization (why this is small)
The "spawn an isolated verifier subagent" idea is **most of the way built already**:
- **`engine/evolve/llm.py:call_claude` IS an isolated subagent spawner.** Every call is a fresh `claude -p`
  process that already (a) sets `NATIVE_EVOLVE_REFLECTING=1` so the Stop-hook reflector no-ops (no recursion),
  (b) uses `--setting-sources user` so project hooks don't load, (c) auto-appends cost to the ledger
  (`_log_ledger`). A fresh process = a physically clean context = **real isolation**. We do NOT need a Task
  tool.
- **`eval/self_verify.py:self_verify(task, resp, env)` is isolated BY CONSTRUCTION.** Its signature receives
  only the task + the produced answer + the env — never the agent's chain-of-thought, memory bullets, or
  skill text. So the payload contract ("verifier sees only task+artifact") is *structurally guaranteed* for
  the harness signal, not something we must police.
- **The verdict is already wired.** `prequential.reffree_verdict / reffree_ok / make_judge /
  reffree_evidence_dict` all consume `self_verify`'s `{ok, signature, feedback}` to drive credit / gate /
  reflect / repair under `--*_signal reffree`. Upgrading `self_verify` in place = verdict capture for free.

So what's actually MISSING vs the design is only:
1. **Grounding** — `self_verify`'s non-code channel is *pure text self-critique* (`allowed_tools="Read"`): it
   forms an opinion by re-reading, it does NOT *verify by running*. That's the weak (type-2) channel. The
   upgrade: let that verifier RUN (Bash + the artifact in a sandbox) and AUTHOR its own checks.
2. **The agentic in-turn version** — when the agent solves multi-turn (`agentic_attempt`), its OWN
   self-checks happen inside its own (polluted) context. There a subagent gives the agent an *unbiased* check
   during solving. Only `spreadsheetbench` has `agentic_attempt` today.

## Staging

### Stage 1 — the grounded isolated verifier primitive (MINIMAL; zero claude spend to land + test)
Upgrade `self_verify`'s non-code channel from "opinion" to "ran a check," keeping isolation (already
structural) and adding grounding + author-own-check. **Flag-gated, default OFF → every existing run
reproduces byte-for-byte.**

**Change set:**
- `eval/self_verify.py`:
  - New `_grounded_verify(task, attempt, env, call_claude, sandbox=None)`: writes the artifact into a temp
    sandbox, calls `call_claude(_GROUNDED_PROMPT, allowed_tools="Read,Write,Bash", add_dir=sandbox,
    cwd=sandbox, permission_mode="bypassPermissions", max_turns=K, setting_sources="user")`, parses
    `{ok, violations}` via `llm.extract_json`, returns the standard `{ok, signature, feedback}`.
  - `_GROUNDED_PROMPT`: hands the verifier ONLY {task text, artifact}; instructs it to (1) restate the
    checkable requirements from the task alone, (2) **verify by RUNNING** (write+run assertions / run the
    code / check constraints programmatically), (3) return `{"ok":bool,"violations":[...]}`. (Mirror the
    SKILL's payload contract + "honest limit" for pure-knowledge.)
  - `self_verify(...)` gains `ground=None` (default reads `NATIVE_EVOLVE_VERIFY_GROUNDED`, default off). When
    on, the non-code critique branch routes to `_grounded_verify`; when off, the current text-critique path
    is unchanged. Execution-authoritative rule preserved (a clean run stays the verdict).
- `eval/test_isolated_verify.py` (NEW, zero spend — fakes for `call_claude` + `env.try_run`):
  - `payload_isolation`: build the verifier for a task; assert the prompt passed to the fake `call_claude`
    contains the task + artifact and does NOT contain planted reasoning/memory/skill sentinels. (Proves the
    contract.)
  - `routing`: code attempt → execution channel (try_run called); non-code → critique/grounded.
  - `grounded_flag`: `ground=on` → `call_claude` invoked with `Bash` in allowed_tools + `add_dir` set;
    `ground=off` → `allowed_tools="Read"` (current behavior).
  - `verdict_shape`: ok → `{ok:True}`; violations → `{ok:False, signature, feedback}`.
  - `exec_authoritative`: clean exec + critique violations → still ok (regression guard).
  - `no_channel`: no code + critique unavailable → None.

**Cost / risk:** default-off → no behavior change, no new spend until a run opts in with the flag. When on,
each grounded verify is one extra `claude` call — **cumulative cost auto-ledgers** (call_claude logs it), so
`cum_cost()` stays authoritative. The per-task ledger ROW still undercounts the verify call (a pre-existing
gap noted in PROGRESS); threading the verify cost into `meta["cost"]` is a small optional cleanup, not
required for correctness. Recursion is already guarded (Stage 1 needs nothing new there).

### Stage 2 — the native agentic verifier the SKILL actually calls (LATER; needs a billed end-to-end test)
Make the SKILL's "spawn a verifier" instruction executable inside `agentic_attempt`, and capture the verdict
deterministically. Cleanest option (no Task tool): install a tiny **`verify` tool script** into the agent
sandbox (alongside the skills in `_install_skills`) that the agent runs via Bash; it internally calls
`call_claude` with the payload contract, prints `{ok, violations}`, and writes a `verdict.json` the harness
reads. This (a) makes the isolated verifier a deploy-available TOOL the SKILL invokes natively, (b) captures
the verdict for credit/gate/reflect (= deploy==evaluated, Phase B), (c) ledgers cost. Then extend
`agentic_attempt` beyond SB. Deferred because it changes the agentic loop and needs a billed smoke to confirm
the agent uses the tool and the verdict round-trips.

## Recommendation
Build **Stage 1 now** (zero spend, default-off, fully unit-tested) — it lands the reusable grounded-isolated
verifier and its contract test, and lets a single opt-in flag turn on grounded reffree verification for an
A/B later. Hold **Stage 2** until we want the billed agentic-native test. No defaults change; nothing bills
until explicitly flagged.
