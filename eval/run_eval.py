"""Run τ³-bench evaluation on banking_knowledge domain and print accuracy."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent import create_custom_agent

import random

from tau2.registry import registry
from tau2.run import run_domain, get_tasks
# τ²-bench v1.0.0: RunConfig is now a Union type; use TextRunConfig for text/half-duplex
from tau2.data_model.simulation import TextRunConfig
from tau2.metrics.agent_metrics import compute_metrics

# Register our custom agent factory (tau2 v1.0.0 factory-function API)
registry.register_agent_factory(create_custom_agent, "custom")

DOMAIN = "banking_knowledge"
SPLIT = "test"
NUM_TRIALS = 1
SAMPLE_FRAC = float(os.environ.get("SAMPLE_FRAC", "1.0"))  # e.g. 0.1 for 10%
MODEL = os.environ.get("SOLVER_MODEL", "gpt-4.1-mini")
USER_MODEL = os.environ.get("USER_MODEL", "gpt-4.1-2025-04-14")
EVAL_LITE = os.environ.get("EVAL_LITE", "0") == "1"
MAX_CONCURRENCY = int(os.environ.get("EVAL_CONCURRENCY", "12"))

LITE_TASK_CLUSTERS = {
    "canary":               ["task_001", "task_004", "task_007", "task_076"],
    "playbook_trap":        ["task_033"],
    "dispute_calculator":   ["task_017", "task_018", "task_021", "task_026", "task_040"],
    "execution_discipline": ["task_036", "task_087", "task_100"],
    "variance_band":        ["task_006", "task_016", "task_035"],
    "escalation":           ["task_005", "task_091"],
    "recently_flipped":     ["task_019", "task_024"],
}


def run_all():
    all_tasks = get_tasks(task_set_name=DOMAIN, task_split_name=SPLIT)
    if EVAL_LITE:
        lite_ids = [tid for cluster in LITE_TASK_CLUSTERS.values() for tid in cluster]
        id_to_task = {t.id: t for t in all_tasks}
        sampled = [id_to_task[tid] for tid in lite_ids if tid in id_to_task]
        task_ids = [t.id for t in sampled]
        print(f"\n=== {DOMAIN.upper()} LITE ({len(task_ids)}/{len(all_tasks)} curated tasks) ===", file=sys.stderr)
    else:
        n_sample = max(1, int(len(all_tasks) * SAMPLE_FRAC))
        random.seed(42)
        sampled = random.sample(all_tasks, n_sample)
        task_ids = [t.id for t in sampled]
        print(f"\n=== {DOMAIN.upper()} ({n_sample}/{len(all_tasks)} tasks) ===", file=sys.stderr)

    config = TextRunConfig(
        domain=DOMAIN,
        task_split_name=SPLIT,
        task_ids=task_ids,
        agent="custom",
        llm_agent=MODEL,
        llm_args_agent={"temperature": 0.0},
        user="user_simulator",
        llm_user=USER_MODEL,
        llm_args_user={"temperature": 0.0},
        num_trials=NUM_TRIALS,
        max_steps=200,
        max_errors=10,
        seed=300,
        save_to=f"eval_{DOMAIN}",
        log_level="WARNING",
        max_concurrency=MAX_CONCURRENCY,
    )
    results = run_domain(config)
    metrics = compute_metrics(results)

    n_tasks = len(results.tasks)
    pass1 = metrics.pass_hat_ks.get(1, 0.0)
    cost = metrics.avg_agent_cost * n_tasks
    correct = int(round(pass1 * n_tasks))

    print(f"  tasks: {n_tasks}, pass^1: {pass1:.4f}, cost: ${cost:.2f}", file=sys.stderr)

    if EVAL_LITE:
        sim_by_task = {}
        for sim in results.simulations:
            r = getattr(sim.reward_info, "reward", 0.0) if sim.reward_info else 0.0
            sim_by_task[sim.task_id] = r
        print("  Per-cluster breakdown:", file=sys.stderr)
        for cluster, ids in LITE_TASK_CLUSTERS.items():
            marks, passed, total = [], 0, 0
            for tid in ids:
                if tid not in sim_by_task:
                    continue
                total += 1
                ok = sim_by_task[tid] >= 1.0
                if ok:
                    passed += 1
                marks.append(f"{tid}{'✓' if ok else '✗'}")
            print(f"    {cluster:22s} {passed}/{total}  [{', '.join(marks)}]", file=sys.stderr)

    print("---")
    print(f"accuracy:         {pass1:.6f}")
    print(f"correct:          {correct}")
    print(f"total:            {n_tasks}")
    print(f"cost_usd:         {cost:.2f}")


if __name__ == "__main__":
    run_all()
