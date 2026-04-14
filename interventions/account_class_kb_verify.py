"""Intervention L: account_class KB-verify gate.

Block call_discoverable_agent_tool(open_bank_account_4821) when the
agent hasn't done a KB_search mentioning the chosen account_class.
Forces a "verify via KB" step before committing to an account class.

Targets the ~16-task "account_class reasoning" failure class: the agent
has the valid set (Intervention I) but picks the wrong class because it
hasn't read the class-specific KB doc. This intervention helped task_057
pass on gpt-4.1-mini (brian, commit 7ddaa018, 11/97 tied for #1).

Author: brian
"""
from __future__ import annotations

import json
from typing import Optional

from interventions import (
    REGISTRY,
    HookContext,
    HookResult,
    Intervention,
)


def account_class_kb_verify(ctx: HookContext) -> Optional[HookResult]:
    tc = ctx.tool_call
    if tc is None:
        return None

    name = getattr(tc, "name", None)
    if name != "call_discoverable_agent_tool":
        return None

    args = getattr(tc, "arguments", None)
    if args is None:
        args = getattr(tc, "args", None)
    if not isinstance(args, dict):
        return None

    if args.get("agent_tool_name") != "open_bank_account_4821":
        return None

    inner_str = args.get("arguments", "")
    if not isinstance(inner_str, str) or not inner_str:
        return None

    try:
        inner_kwargs = json.loads(inner_str)
    except (json.JSONDecodeError, TypeError):
        return None

    acct_class = (inner_kwargs.get("account_class") or "").lower()
    if not acct_class:
        return None

    kb_queries = ctx.state.get("kb_queries", [])
    if any(acct_class in q for q in kb_queries):
        return None  # Already searched — let the call through

    chosen = inner_kwargs.get("account_class", "")
    return HookResult(
        drop=True,
        drop_note=(
            f"MANDATORY NEXT ACTION: The {chosen} call was blocked because I "
            f"haven't read the KB doc for this account class yet. I MUST now "
            f"call KB_search(query=\"{chosen} eligibility features\") to verify "
            f"this is the right class for this customer. After reading the result, "
            f"I will retry the open_bank_account_4821 call with the correct "
            f"account_class value. DO NOT stop — do the KB_search immediately."
        ),
        log={
            "reason": "blocked_account_class_not_kb_verified",
            "account_class": acct_class,
        },
    )


REGISTRY.register(
    Intervention(
        id="L",
        name="account-class-kb-verify",
        hook="gate_pre",
        target_cluster="arguments",
        author="brian",
        description=(
            "Drop call_discoverable_agent_tool(open_bank_account_4821) if "
            "the chosen account_class hasn't appeared in any prior "
            "KB_search query. Forces a verify-via-KB step, helps agent "
            "avoid picking valid-but-wrong account classes."
        ),
        status="active",
        apply=account_class_kb_verify,
    )
)
