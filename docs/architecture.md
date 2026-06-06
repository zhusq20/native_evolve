# native_evolve — method architecture

One self-evolving loop per task. Each task is first **served** (inference / test, reads no gold),
then **learned from** (self-evolution / train, uses gold-grounded evidence). Three persistent stores
carry knowledge across tasks, so *today's learning is tomorrow's context*. The **determinism rule**:
only the blue nodes call the LLM (`claude -p`); curation, crediting and the gate *decision* are
deterministic Python — the LLM proposes, Python disposes (anti ACE context-collapse).

## Diagram (Mermaid)

```mermaid
flowchart TB
  stream(["TASK STREAM — t1 → t2 → t3 …<br/>prequential: TEST each task, then LEARN from it"])
  stream --> retr

  subgraph SERVE["① SERVE — inference · reads NO gold"]
    direction TB
    retr["RETRIEVE — 3 tiers (ours_full)<br/>episodic exemplars + distilled bullets + gated skills<br/><b>AGENTIC-INDEX</b>: model selects [ids] from a plain-text index<br/>(native paradigm; lexical top-k still available)"]
    agent["TARGET AGENT — claude -p"]
    verify{"VERIFY — reference-free<br/>self_both: exec ⊕ self-critique<br/>clean exec is authoritative"}
    repair["REPAIR ≤N — MONOTONE<br/>replace only if it re-verifies ok"]
    ans["final answer"]
    retr -->|inject ctx| agent --> verify
    verify -->|reject| repair --> verify
    verify -->|ok| ans
  end

  score["SCORE — gold · external · gold-isolated"]
  ans --> score

  subgraph LEARN["② LEARN — self-evolution · gold-grounded EVIDENCE (train only)"]
    direction TB
    rec["record episode"]
    cred["CREDIT injected ids → helpful / harmful"]
    refl["REFLECT — claude, trace-grounded → candidate bullet"]
    cur["CURATE — dedup · merge · decay<br/>never LLM-rewrite ⇒ anti context-collapse"]
    gate{"every K — PROMOTE GATE<br/>induce skill (claude) → ROLLING A/B on held-out replay<br/>activate IFF lift ≥ margin AND broke ≤ rescued"}
    rec --> cred --> refl --> cur --> gate
  end
  score --> rec

  epi[("EPISODIC STORE<br/>raw trajectory + failure signature")]
  dist[("DISTILLED STORE<br/>bullets: content · scope · helpful/harmful · uses")]
  skl[("SKILL STORE<br/>gated · versioned · git-visible")]

  rec --> epi
  cred -. update counters .-> dist
  cur --> dist
  gate -->|accept| skl
  gate -. reject → keep as candidate .-> skl

  epi -. read .-> retr
  dist -. read .-> retr
  skl -. read .-> retr

  classDef llm fill:#dbeafe,stroke:#2563eb,color:#1e3a8a;
  classDef det fill:#dcfce7,stroke:#16a34a,color:#14532d;
  classDef store fill:#fef9c3,stroke:#ca8a04,color:#713f12;
  classDef ext fill:#e5e7eb,stroke:#374151,color:#111827;
  class agent,refl,retr,verify,gate llm;
  class cred,cur,repair det;
  class epi,dist,skl store;
  class score,ans,stream ext;
```

**Colour legend.** 🟦 involves a `claude -p` call · 🟩 pure deterministic Python ·
🟨 persistent store · ⬜ external / gold-isolated.
*Mixed nodes* `RETRIEVE` / `VERIFY` / `PROMOTE GATE` are coloured blue because they *contain* a
claude call (agentic select · self-critique · skill-induce + A/B), but their **decision logic**
(id parsing, the exec-authoritative veto, accept/reject by margin & non-dilution) is deterministic.

## Diagram (ASCII fallback)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  TASK STREAM   t1 → t2 → t3 → …      prequential: TEST each task, then LEARN     │
└───────────────────────────────────┬────────────────────────────────────────────┘
                                     │  task tᵢ
  ① S E R V E  (inference · reads NO gold)
  ┌──────────────────────────────────────────────────────────────────────────┐
  │ RETRIEVE  (3 tiers)   episodic exemplars + distilled bullets + gated skills │
  │      └─ AGENTIC-INDEX: the model selects [ids] from a plain-text index       │
  │                        (native paradigm; lexical top-k still available)      │
  └───────────────────────────────┬────────────────────────────────────────────┘
                       inject ctx  ▼
                 ┌───────────────────────────┐
                 │  TARGET AGENT  (claude)    │ ─► attempt
                 └─────────────┬──────────────┘
                               ▼
            VERIFY (reference-free: exec ⊕ self-critique, exec authoritative)
                 reject ─► REPAIR (≤N, MONOTONE: replace only if re-verifies ok) ─┐
                   │ ok                                                            │
                   ▼ ◄──────────────────────────────────────────────────────────-┘
               final answer ─►  SCORE (gold · external · isolated)
                                     │
  ② L E A R N  (self-evolution · gold-grounded EVIDENCE · train only)
                                     ▼
     record episode ───────────────────────────────────────►  ▓ EPISODIC STORE
     CREDIT injected ids  [deterministic] ─► helpful / harmful ─► (updates DISTILLED)
     REFLECT (claude, trace-grounded) ─► candidate bullet
                   │
           CURATE  [deterministic: dedup · merge · decay]
                   ▼   never LLM-rewrite ⇒ anti context-collapse
                                                            ▓ DISTILLED STORE
     every K tasks ─► PROMOTE GATE
        induce skill (claude) ─► ROLLING A/B on held-out replay
        activate IFF  lift ≥ margin  AND  broke ≤ rescued
        else keep as candidate (graceful degradation)       ▓ SKILL STORE (gated)
  ──────────────────────────────────────────────────────────────────────────────
   ▓ STORES persist across tasks ─► read back by RETRIEVE on the next task
     (the loop closes: today's learning becomes tomorrow's context)

  LLM (claude -p):   target-solve · agentic-select · self-critique · reflect · skill-induce
  Deterministic Py:  credit · curate (dedup/merge/decay) · monotone-repair · gate decision
  External/isolated: SCORE (gold) — never visible to SERVE or VERIFY
```

## How the two scientific claims sit on this picture
- **C1 (two-tier > single-tier ACE):** the **DISTILLED STORE** (retrieved, not dumped) + the gated
  **SKILL STORE** vs ACE's one monolithic playbook injected in full every turn.
- **C2 (native online ≥ external offline optimizer):** the whole ② LEARN band runs *in the agent's own
  loop*, amortized into real work — versus a separate offline trainer that freezes one global skill.

## Deployment vs. evaluation
- **Deployment** = the same loop wired into **Claude Code hooks**: `UserPromptSubmit` → RETRIEVE inject,
  `Stop` → REFLECT/CURATE/GATE (recursion-guarded). Skills live visibly in `engine/skills/`.
- **Evaluation** = `eval/prequential.py` orchestrates SERVE+LEARN over a task stream and logs
  accuracy-vs-cumulative-cost; `eval/run.py` fans methods/seeds out in parallel.
