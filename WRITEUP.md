# τ³-bench banking_knowledge — session findings (2026-04-11)

*Agent `brian` building on top of `hive/junjie` commit `0d3e76a`. Session ended with no validated score improvement over junjie's 7/97, but the diagnostic findings below are more valuable than the experiments themselves. Companion session to `brian2`'s earlier exploration at `/Users/brianchen/hive-brian2/tau3`.*

---

## 1. Setup

- Task: τ³-bench `banking_knowledge` domain, 97 tasks, `gpt-4.1-mini` agent / `gpt-4.1` user simulator, temperature 0.
- Leaderboard at session start: one submission — `junjie` at `0d3e76a`, 7/97 (0.0722). Ceiling for `gpt-4.1-mini` is ~15–25% per the `program.md` research analyses.
- Baseline established for this session: junjie's code produces 9/97 on one full eval (within his own reported variance band of 6, 7, 8, 8 across reruns).
- Lite eval baseline: 8/20 with this cluster split — `canary 4/4`, `playbook_trap 0/1`, `dispute_calculator 2/5`, `execution_discipline 0/3`, `variance_band 2/3`, `escalation 0/2`, `recently_flipped 0/2`.
- Budget: $20 ceiling. Used ~$3. Stopped because the marginal return on more single-run lite experiments had dropped below noise.

## 2. The P1 classifier is a phantom on junjie's branch

**What `extract_traces.py` reports:**

```
priority_1_verification_or_unlock: 70
priority_4_execution_discipline:   11
priority_2_wrong_arguments:         6
unknown:                            1
```

**What's actually actionable:**

The classifier fires `priority_1_verification_or_unlock` whenever `discoverable_tool_analysis.missing_unlocks` is non-empty — *regardless of whether any element in `missing_unlocks` matches a tool the task actually required*. On junjie's branch (compass catalog, state-aware annotator, 7 gate interventions), the LLM still searches KB aggressively and sees lots of discoverable tool names in passing; many of those mentions are incidental (variant siblings, cross-references, unrelated procedure docs). The classifier counts every one of them as a P1 failure.

Re-classifying the same 88 failures using `missing_unlocks ∩ action_details.expected_tool`:

```
true_P1_missing_unlock_for_expected_tool: 0
P4_partial_execution:                    76
P4_never_attempted_expected:             11
P2_wrong_arguments:                       1
```

**Zero** true P1 failures after junjie's gate interventions. Any swarm agent targeting P1 via the stock counter on this branch is chasing a ghost. The bottleneck is execution discipline — the agent does *most* of the expected action trace and misses *one or two specific tools* per task.

Distribution of "how many expected actions did the agent miss" across the 88 failures:

```
missed 1 of N:  7 failures
missed 2 of N: 12 failures
missed 3 of N:  6 failures
missed 4 of N:  5 failures
missed 5 of N:  6 failures
missed 6+      33 failures
```

Many tasks are one-or-two misses away from passing. That's the payoff structure that makes this space still tractable.

## 3. The dominant unmatched expected action is a discoverable *read* tool

Top 10 unmatched `expected_tool` calls across all 88 failures (count = occurrences in `action_details` where `matched=False`):

```
49  CALL:get_bank_account_transactions_9173         ← discoverable READ
45  CALL:file_credit_card_transaction_dispute_4829
36  UCALL:submit_cash_back_dispute_0589
31  CALL:get_all_user_accounts_by_user_id_3847      ← discoverable READ
27  CALL:open_bank_account_4821
23  CALL:file_debit_card_transaction_dispute_6281
22  CALL:get_debit_cards_by_account_id_7823         ← discoverable READ
21  CALL:close_debit_card_4721
18  CALL:get_pending_replacement_orders_5765        ← discoverable READ
17  CALL:get_user_dispute_history_7291              ← discoverable READ
```

**The #1 failure pattern — by a wide margin — is the agent using a BASE read tool where the golden action trace expected the DISCOVERABLE variant.**

Example: a customer reports an unexpected credit card balance. Agent verifies identity, then calls `get_credit_card_transactions_by_user(user_id=...)` (a base tool) to fetch transactions, then proceeds to whatever the dispute flow is. The API call succeeds; the agent gets usable data; the mutation flow continues. **But the golden action trace expected the discoverable variant `get_bank_account_transactions_9173` in the action sequence.** τ²-bench's action evaluator scores on exact tool names, so the read step is marked unmatched even though the information the agent needed was obtained.

Neither junjie's 7 gate interventions nor brian2's Intervention H address this. Both were designed around *mutation* tools (gate-level arg canonicalization, enum pre-validation, phase-2 guards, dispute calculator injection). No existing intervention forces the agent to prefer a discoverable read variant when one is available.

## 4. What was tried this session and the session before

### Session 1 (`brian2` — earlier today)

| Experiment | Approach | Lite | Full | Disposition |
|---|---|---|---|---|
| Phase D v2 | Dispute guard requires `user_calls ≥ candidate_count` | 7/20 (-1) | 9/97 | Reverted. Lite regression overrode the full result. |
| Intervention H | Gate-level enum pre-validation on `call_discoverable_agent_tool` using `compass.enum_constraints()` | 6/20 (-2) | not run | Kept on branch but never submitted or pushed. |

### Session 2 (`brian` — this session, building on junjie `0d3e76a`)

| Experiment | Approach | Lite | Full | Disposition |
|---|---|---|---|---|
| Baseline reproduction | Vanilla junjie `0d3e76a` | 8/20 | 9/97 | Matches brian2's and junjie's own variance bands. |
| Exp1 | Prompt-level rules for discoverable READ tool preference + first-call arg discipline | 7/20 (-1) | not run | Reverted. Directionally: +1 `playbook_trap`, +1 `execution_discipline`, **-2 `dispute_calculator`** (lost junjie's task_017 and task_018). My new prompt section competed with junjie's existing Phase D annotator framing. |

### Common pattern across both sessions

Every single-run lite experiment moved the score by 1-2 tasks in some direction. The noise floor of a single 20-task lite run is ≥1 task. Nothing moved far enough above that floor to survive as a confident improvement, and nothing was escalated to a 4-run Stage A screen (let alone the 15-run Stage B confirmation that `program.md` demands for a publishable +2-task claim on the full eval).

**Takeaway:** on top of a hardened frontier like junjie's, signal-level improvements at lite granularity are the norm. You either need (a) a change with a large expected effect (+3-4 tasks on full eval), (b) statistical rigor via multi-run Stage A/B, or (c) both. One-shot lite experiments on top of a competent baseline mostly produce false starts.

## 5. What would be worth trying next

1. **Gate intervention: block base read tools when a discoverable variant is mentioned in the active KB context.** The #1 failure mode. When a KB_search result has mentioned `get_bank_account_transactions_9173` and the agent is about to call base `get_credit_card_transactions_by_user`, rewrite to `unlock_discoverable_agent_tool(agent_tool_name="get_bank_account_transactions_9173")` followed by `call_discoverable_agent_tool(...)`. Annotator-level side-note already exists; the gate-level block is what's missing. Expected effect: potentially multi-task lift on full eval if the pattern generalizes beyond the 2 specific tools.

2. **Adopt brian2's Intervention H (gate-level enum pre-validation) and measure it honestly.** It's a well-scoped, unit-tested gate rule that addresses the "first call gets scored" issue for typed enum args. brian2 abandoned it after a noisy -2 lite reading; it deserves a Stage A screen (4 full-eval reruns each for baseline and H) to see if it actually moves anything on the full eval.

3. **Annotator "prerequisite read" surfacing.** When KB returns a procedure doc for a mutation like `file_credit_card_transaction_dispute_4829`, scan the doc for *all* tool name mentions (not just the mutation itself) and surface them as "PREREQUISITE UNLOCKS YOU MAY NEED: get_credit_card_transactions_..." before the agent makes its first tool call in the sequence.

4. **Stop using single-run lite for decision-making on this task.** Every experiment at this stage should run at least 4 lite reruns (σ ≈ 1 task → σ_Δ ≈ 0.7 with n=4) before deciding to keep or revert. Better yet: move to Stage A full-eval screens for any change that plausibly affects the full-eval failure distribution (and most changes do, because the full eval has 4.8× more tasks and 21× more mutation attempts).

## 6. What I did not do — and why

- **Did not submit a run.** My 9/97 is indistinguishable from junjie's 7/97 at the variance the task has. Submitting would pollute the leaderboard with noise.
- **Did not attempt the discoverable-read gate intervention.** I identified it as the right next experiment but the prompt-level version (exp1) already cost me a cluster regression, and the gate-level version would consume the remaining context budget without a way to validate it at the required statistical rigor inside a single session.
- **Did not cherry-pick Intervention H.** Same reason — the right way to test H is a Stage A screen, not another single-run lite.
- **Did not post brian2's Intervention H to the swarm feed.** That's an earlier private session's work; it's the operator's call whether to share it.

## 7. Appendix: useful commands for next session

```bash
# Reproduce the baseline quickly
cd ~/tau3
git checkout hive/brian/build-on-junjie    # has LITE_EVAL patched in
EVAL_LITE=1 bash eval/eval.sh               # ~2 min, ~$0.20

# Re-classify failures by real failure class (bypasses the P1 phantom)
python -c "
import json
from collections import Counter
d = json.load(open('traces/latest.json'))
real = Counter()
for t in d['failure_traces']:
    if t['passed']: continue
    ae, am = t.get('actions_expected',0), t.get('actions_matched',0)
    if am == 0 and ae > 0: real['never_attempted'] += 1
    elif am < ae:         real['partial_execution'] += 1
    else:                 real['other'] += 1
print(dict(real))
"

# Top unmatched expected tools (the real bottleneck signal)
python -c "
import json; from collections import Counter
d = json.load(open('traces/latest.json'))
c = Counter()
for t in d['failure_traces']:
    for a in t.get('action_details', []) or []:
        if isinstance(a, dict) and not a.get('matched'):
            tool = a.get('expected_tool','?')
            args = a.get('expected_args') or {}
            if tool.startswith('call_discoverable'):
                c['CALL:' + args.get('agent_tool_name','?')] += 1
            elif tool.startswith('unlock_discoverable'):
                c['UNLOCK:' + args.get('agent_tool_name','?')] += 1
            else:
                c[tool] += 1
for k,v in c.most_common(15): print(f'{v:3d}  {k}')
"

# Adopt Intervention H from brian2
cd ~/tau3
git remote add brian2 /Users/brianchen/hive-brian2/tau3 2>/dev/null
git fetch brian2 hive/brian2/enum-pre-validation
git cherry-pick 99462ad2428d38e2edaa2cf1f57c34e37e3992bd
```

## 8. Files touched this session (branch `hive/brian/build-on-junjie`)

- `eval/run_eval.py` — ported LITE_TASK_CLUSTERS, EVAL_LITE toggle, EVAL_CONCURRENCY=12, per-cluster breakdown. The matching code changes from junjie's feed posts #11 and #12 never actually landed in `0d3e76a`; they're now on this branch.
- `.agent/learnings.md` — appended the P1 classifier insight, the discoverable-read-tool distribution, and exp1's negative result.
- `.gitignore` — added `.hive/` workspace metadata.
- `WRITEUP.md` — this file.

No changes to `agent.py` or `compass.py`. Experiment 1 modified `agent.py` but was reverted before push.

## 9. Swarm feed posts

- `#15`: P1 classifier mask finding with the 0-true-P1 re-classification numbers.
- `#17`: Experiment 1 negative with directional cluster breakdown + the top-unmatched-tools distribution + pointer to the LITE_EVAL infra commit.

Both are visible to other swarm agents via `hive task context` and `hive feed view`.
