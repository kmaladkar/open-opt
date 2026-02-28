"""
Help for the main agent (team lead).

The main agent can call these functions when it needs guidance on:
- Which subagent to invoke (routing)
- Canadian rules and limits (for recommendations and Research subagent context)
- How to synthesize subagent outputs into a final answer
- Recommendation flow (always delegate to Visualization agent, never call GenAI directly)
- When to use Test & Debug vs Test Writer vs QA subagents
"""

from typing import List, Literal

HelpTopic = Literal[
    "routing",
    "canadian_rules",
    "synthesis",
    "recommendations",
    "test_debug",
    "full",
]

TOPICS: List[str] = [
    "routing",
    "canadian_rules",
    "synthesis",
    "recommendations",
    "test_debug",
    "full",
]


def get_routing_help() -> str:
    """When to call which subagent. Use this to choose the next node or tool."""
    return """
ROUTING: Which subagent to call

- BANKING: Accounts, balances, transactions, institution (e.g. RBC, TD, Wealthsimple).
  Call when: user asks about accounts, balances, spending, idle cash, where money is held,
  or you need account/balance data for recommendations. Tools: get_household_accounts,
  get_balances, get_transactions (and open banking adapter).

- INVESTING: Products, risk, allocation, contribution room, tax loss harvesting.
  Call when: user asks about investing, portfolios, TFSA/RRSP/FHSA room, allocation,
  or tax loss harvesting in non-registered accounts. Tools: get_eligible_products,
  get_contribution_room, tax_loss_harvesting_eligibility.

- FAMILY: Household members, goals, RESPs, beneficiaries, education/retirement goals.
  Call when: user asks about family, kids’ education, RESPs, goals, or you need
  member ages/roles for CESG or goal projections. Tools: get_family_members,
  get_goals, get_resp_eligibility, compute_resp_cesg.

- RESEARCH: Canadian rules, limits, CESG/CLB, FHSA eligibility, superficial loss rules.
  Call when: you need authoritative limits (TFSA/RRSP/FHSA/RESP), CESG income brackets,
  FHSA first-time buyer rules, or tax loss harvesting / 61-day superficial loss rules.
  This subagent encapsulates compliance; use before making recommendation text.

- VISUALIZATION (recommendation flow): For any recommendation request, delegate HERE only.
  Do not call GenAI recommendation step directly. Visualization agent owns the flow:
  it calls GenAI, produces narrative, and produces chart specs/images. Route here for
  "recommendations", "best way to save", "how to invest", or when user wants charts.

- TEST & DEBUG: Writing tests or debugging code/failures.
  Call when: user or system asks to "write tests", "debug", "fix failing test", or
  "add tests for X". Tools: read/write files, run pytest, inspect stack traces, apply fixes.

- TEST WRITER: Creating and maintaining test suites.
  Call when: need to expand coverage, add regression tests, or maintain test files.
  Works with Test & Debug. Tools: list modules/routes, read source, write test files, run tests.

- QA AND VERIFICATION: Running tests, reproducing bugs, verifying fixes.
  Call when: "run tests", "verify the fix", "reproduce this bug", or validate changes.
  Tools: run test commands, compare outputs, inspect logs, confirm behavior.
"""


def get_canadian_rules_summary() -> str:
    """Short reference for Canadian limits and rules (TFSA, RRSP, FHSA, RESP, tax loss harvesting)."""
    return """
CANADIAN RULES SUMMARY (use for room, eligibility, and recommendation wording)

Contribution limits (2025/2026):
- TFSA: $7,000/year (2025–2026); cumulative room ~$109,000 (2026) for eligible since 2009.
  Contributions count for year if by Dec 31; CRA My Account has room (updated ~April following year).
- RRSP: 18% of income, max $32,490 (2026). No lifetime cap. Deadline for prior year: first 60 days of next year (e.g. Mar 2, 2026 for 2025).
- FHSA: $8,000/year, $40,000 lifetime. Unused room carry-forward max $8,000. Tax-deductible contributions.
- RESP: No fixed annual cap. CESG lifetime $7,200 per beneficiary; CLB $2,000 per child.

RESP grants:
- Basic CESG: 20% on first $2,500/year = max $500/year per beneficiary.
- Additional CESG (income-tested): On first $500 — 20% (max $100) if family income < $57,375 (2025); 10% (max $50) if $57,375–$114,750; 0% if > $114,750. For 2026 use $58,523 and $117,045.
- CLB: Up to $2,000 per child; no contribution required; CCB-eligible. Family RESP: one plan, multiple beneficiaries; CESG/earnings shareable within limits; CLB per-child, not shareable.

FHSA: Canadian resident, 18+, first-time buyer (no principal residence ownership in current or prior 4 years for you or spouse). Qualifying withdrawal tax-free for first home in Canada; must close by end of year after first qualifying withdrawal, or within 15 years, or by 71.

Tax loss harvesting (non-registered only):
- Sell at a loss to offset capital gains; losses can carry back 3 years or forward indefinitely.
- Superficial loss rule: loss disallowed if taxpayer or affiliated person acquires same/identical property within 61 days (30 before + 30 after). Affiliated persons: spouse, taxpayer’s RRSP/RRIF/TFSA, certain trusts/corporations. Denied loss added to ACB of repurchased property.
- Do not transfer losing shares into registered accounts (loss is permanently lost). Only recommend harvesting in non-registered accounts; respect 61-day window and affiliated-person rules.
"""


def get_synthesis_guidance() -> str:
    """How to combine subagent outputs into a final answer."""
    return """
SYNTHESIS: Combining subagent outputs

- Never execute banking or investment actions yourself; only recommend. Use subagent data to support narrative.
- Frame recommendations so both the user and Wealthsimple benefit where they align. When open banking shows accounts at other banks (RBC, TD, BMO, etc.), surface opportunities where moving money to Wealthsimple improves outcomes (e.g. better interest, lower fees). Example: "Your RBC savings earn 0.5%; moving that balance to Wealthsimple Cash could earn 4%—here’s how much you’d gain." Recommend Wealthsimple when it is genuinely the best option.
- Use Research/Canadian rules for limits and eligibility so wording is accurate (TFSA room, CESG, FHSA first-time buyer, tax loss harvesting only in non-registered, 61-day superficial loss).
- When comparing rates, distinguish promotional vs ongoing and cite source (e.g. "Wealthsimple Cash 4% ongoing; RBC savings 0.5%").
- For recommendation intents: do not synthesize raw GenAI output yourself. Return the response from the Visualization agent (narrative + optional chart specs/images). The Visualization agent owns recommendation content and visuals.
- Keep language educational: use "consider", "suggest", "you could"; avoid implying execution of trades or account opening in-app without proper licensing.
"""


def get_recommendation_flow_help() -> str:
    """Reminder: recommendation flow is owned by Visualization agent only."""
    return """
RECOMMENDATION FLOW (critical)

- For any recommendation request (with or without charts), the main agent delegates to the RECOMMENDATION VISUALIZATION subagent ONLY. Do not call the GenAI recommendation step directly.
- The Visualization agent is the parent of the recommendation flow. It: (1) invokes/gathers recommendation content from GenAI, (2) produces narrative recommendation output, (3) produces chart specs or images. The API returns the combined response (text + optional visuals) from the Visualization agent.
- Main Agent → Visualization agent → GenAI (recommendations) + DB. Visualization owns and wraps the recommendation step.
"""


def get_test_debug_routing_help() -> str:
    """When to route to Test & Debug vs Test Writer vs QA."""
    return """
TEST/DEBUG ROUTING

- TEST & DEBUG: User or system wants to "write tests", "debug", "fix failing test", "add tests for X".
  Writes tests (unit, integration), debugs code, inspects errors/stack traces, proposes and applies fixes. Tools: read/write files, run pytest, inspect errors.

- TEST WRITER: Focus on creating and maintaining test suites, expanding coverage, regression tests.
  Tools: list modules/routes, read source, write test files, run tests, report coverage/failures. Use in parallel or after Test & Debug when coverage or test maintenance is needed.

- QA AND VERIFICATION: "Run tests", "verify the fix", "reproduce this bug", "validate changes".
  Runs tests, reproduces bugs, verifies fixes and no regressions. Tools: run test commands, compare outputs, inspect logs, confirm behavior. Use to validate changes or triage failures.
"""


def get_help(topic: str) -> str:
    """
    Return guidance for the main agent on the given topic.
    Use this when uncertain about routing, rules, or how to synthesize.

    Supported topics: routing, canadian_rules, synthesis, recommendations, test_debug, full.
    """
    t = topic.strip().lower() if topic else "full"
    if t == "routing":
        return get_routing_help()
    if t == "canadian_rules":
        return get_canadian_rules_summary()
    if t == "synthesis":
        return get_synthesis_guidance()
    if t == "recommendations":
        return get_recommendation_flow_help()
    if t == "test_debug":
        return get_test_debug_routing_help()
    if t == "full":
        return (
            get_routing_help()
            + "\n"
            + get_recommendation_flow_help()
            + "\n"
            + get_synthesis_guidance()
            + "\n"
            + get_canadian_rules_summary()
        )
    # Unknown topic: return list of topics and full help
    return f"Unknown topic '{topic}'. Available: {', '.join(TOPICS)}.\n\n" + get_help("full")
