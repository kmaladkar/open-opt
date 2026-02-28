"""
Recommendation Visualization agent (parent of recommendation flow).
Invokes GenAI for recommendation content, produces narrative and chart specs (Wealthsimple-style).
Main agent delegates here for all recommendation intents; do not call GenAI recommendation directly from main agent.
"""

from sqlalchemy.orm import Session

from app.agents.subagents import (
    get_household_accounts,
    get_balances,
    get_contribution_room,
    get_family_members,
    get_goals,
    get_resp_eligibility,
)
from app.data.wealthsimple_products import get_savings_rate_comparison
from app.data.canadian_rules import (
    tfsa_annual_limit,
    FHSA_ANNUAL_LIMIT,
    RESP_CESG_BASIC_RATE,
    cesg_additional_rate,
)
from app.data.rate_assumptions import (
    CURRENT_SAVINGS_RATE_ANNUAL_PCT,
    OPTIMIZED_SAVINGS_RATE_ANNUAL_PCT,
    INVESTMENT_GROWTH_ANNUAL_PCT,
    PROJECTION_YEARS,
)
from app.core.config import settings
from app.data.recommendation_prompts import AUTO_RECOMMENDATION_TOPICS, AUTO_LIST_INSTRUCTION


def _gather_context(db: Session, household_id: int) -> dict:
    """Gather household, accounts, goals, and rules for the recommendation prompt."""
    accounts = get_household_accounts(db, household_id)
    balances = get_balances(db, household_id)
    room = get_contribution_room(db, household_id)
    members = get_family_members(db, household_id)
    goals = get_goals(db, household_id)
    resp = get_resp_eligibility(db, household_id)
    ws = get_savings_rate_comparison()
    return {
        "accounts": accounts,
        "balances": balances,
        "contribution_room": room,
        "members": members,
        "goals": goals,
        "resp_eligibility": resp,
        "wealthsimple_rates": ws,
    }


def _format_context_for_llm(context: dict) -> str:
    """Format context as readable bullets so the LLM can reference actual numbers and names."""
    lines = []
    accs = context.get("accounts", [])
    balances = context.get("balances", [])
    if accs or balances:
        by_acc = {b.get("account_id") or b.get("id"): b for b in balances} if balances else {}
        for a in (accs or []):
            aid = a.get("id") or a.get("account_id")
            bal = by_acc.get(aid, a)
            cents = bal.get("balance_cents", a.get("balance_cents", 0))
            name = (a.get("name") or bal.get("account_name") or "Account")[:40]
            inst = (a.get("institution_id") or bal.get("institution_id") or "—")[:20]
            acct_type = (a.get("account_type") or bal.get("account_type") or "—")
            lines.append(f"  • {name} ({acct_type}) @ {inst}: ${cents / 100:,.2f}")
        if not lines and balances:
            for b in balances[:15]:
                name = (b.get("account_name") or "Account")[:40]
                cents = b.get("balance_cents", 0)
                lines.append(f"  • {name}: ${cents / 100:,.2f}")
        lines.append("")
    goals_list = context.get("goals", [])
    if goals_list:
        lines.append("Goals:")
        for g in goals_list[:10]:
            name = g.get("name", "Goal")
            target = g.get("target_amount_cents", 0) / 100
            lines.append(f"  • {name}: ${target:,.0f} target")
        lines.append("")
    room = context.get("contribution_room", {})
    if room:
        lines.append("Contribution room (use these numbers in your answer):")
        tfsa = room.get("tfsa") or {}
        rrsp = room.get("rrsp") or {}
        fhsa = room.get("fhsa") or {}
        if isinstance(tfsa, dict):
            lim = tfsa.get("annual_limit_cents", 0) or 0
            bal = tfsa.get("current_balance_cents", 0) or 0
            lines.append(f"  • TFSA: ${lim / 100:,.0f}/yr limit, ${bal / 100:,.0f} current balance")
        if isinstance(rrsp, dict):
            r_room = rrsp.get("estimated_room_cents", 0) or 0
            r_bal = rrsp.get("current_balance_cents", 0) or 0
            lines.append(f"  • RRSP: ${r_room / 100:,.0f} estimated room, ${r_bal / 100:,.0f} current balance")
        if isinstance(fhsa, dict):
            f_room = fhsa.get("estimated_room_lifetime_cents", 0) or 0
            lines.append(f"  • FHSA: ${f_room / 100:,.0f} lifetime room remaining")
        lines.append("")
    resp = context.get("resp_eligibility", {})
    if resp:
        lines.append("RESP/CESG: " + str(resp)[:300])
        lines.append("")
    rules = context.get("canadian_rules", {})
    if rules:
        lines.append("Canadian limits (2025): TFSA $7,000/yr; RRSP max ~$32,490; FHSA $8,000/yr, $40k lifetime; RESP CESG 20% on first $2,500 ($500 max/match per child/yr).")
        lines.append("")
    ws = context.get("wealthsimple_rates", {})
    ws_pct = ws.get("wealthsimple_cash_cad_pct", 4)
    lines.append(f"Wealthsimple Cash: {ws_pct}% ongoing (compare to big-bank savings ~0.5%).")
    tx_patterns = context.get("transaction_patterns")
    if tx_patterns:
        lines.append("Transaction patterns (recent): " + str(tx_patterns)[:400])
    return "\n".join(lines).strip()


def _build_prompt(context: dict) -> str:
    """Build the GenAI prompt for narrative recommendations."""
    user_question = (context.get("question") or "").strip()
    data_block = _format_context_for_llm(context)

    prompt = """You are a Canadian financial advisor. Use the family's financial data below and Canadian rules (TFSA, RRSP, FHSA, RESP, CESG) as the plan. Your job is to recommend a clear list of strategies to make their finances better.

Instructions:
1. Start with 1–2 sentences that directly answer the user's question (if any) or summarize the household's situation.
2. Then provide a numbered list of 4–6 strategies. Each strategy must:
   - Be specific to this household (use their account names, institutions, dollar amounts, and goals).
   - Tie to Canadian rules where relevant (e.g. "Max RESP to get the 20% CESG match ($500 per child per year)", "Use TFSA room: $7,000/year limit", "FHSA if first-time buyer: $8k/yr, $40k lifetime").
   - Use current rates where helpful (e.g. moving big-bank savings to high-interest cash at ~4% vs ~0.5%).
3. For each strategy, briefly say why it matters (e.g. tax-free growth, match, or extra interest), and quantify the improvement where possible (e.g. "$X more per year" or "$Y more by year 5").
4. Use direct, conditional wording where relevant: "If you have X, do Y as the best next step."
5. Use "consider" and "suggest"; do not imply you will execute trades. Plain language; no jargon without a one-line explanation.
6. Keep the whole response under 400 words.

Household financial data (use these numbers and names):
"""
    prompt += data_block + "\n\n"
    if user_question:
        prompt += f"User question: {user_question[:400]}\n\n"
    prompt += "Reply with your specific, actionable recommendations (bullets encouraged):"
    return prompt


def _fallback_recommendation_from_context(context: dict) -> str:
    """Build a short, context-aware recommendation when LLM is unavailable."""
    parts = []
    balances = context.get("balances", []) or context.get("accounts", [])
    savings_cents = 0
    for b in balances:
        name = (b.get("account_name") or b.get("name") or "").lower()
        if "savings" in name or "chequing" in name:
            savings_cents += b.get("balance_cents", 0) or 0
    if savings_cents > 0:
        low = savings_cents / 100 * 0.005
        high = savings_cents / 100 * 0.04
        extra = high - low
        parts.append(
            f"You have ${savings_cents / 100:,.0f} in chequing/savings. "
            f"Moving it to Wealthsimple Cash (4% ongoing) could earn about ${extra:,.0f} more per year than typical big-bank rates (~0.5%)."
        )
    goals_list = context.get("goals", [])
    has_education = any("educ" in (g.get("name") or "").lower() for g in goals_list)
    if has_education or context.get("resp_eligibility"):
        parts.append(
            "Consider maxing RESP contributions to get the 20% CESG match (up to $500 per child per year on the first $2,500)."
        )
    room = context.get("contribution_room", {})
    tfsa = (room.get("tfsa") or {}).get("current_balance_cents", 0) or 0
    parts.append(
        f"TFSA: $7,000/year limit—top up for tax-free growth. RRSP for retirement; FHSA if you're a first-time home buyer ($8k/yr, $40k lifetime). "
        "Check CRA My Account for your exact room."
    )
    return " ".join(parts)


def _build_fallback_recommendations_list(context: dict) -> list[dict]:
    """
    Build 5–7 specific recommendations from context when LLM is unavailable or returns too few.
    Each item uses real account names, amounts, and goals so recommendations make sense.
    """
    recs = []
    accounts = context.get("accounts", [])
    balances = context.get("balances", [])
    goals_list = context.get("goals", [])
    room = context.get("contribution_room", {})
    resp = context.get("resp_eligibility", {})
    ws = context.get("wealthsimple_rates", {}) or {}
    ws_pct = ws.get("wealthsimple_cash_cad_pct", 4)

    # 1. Savings / idle cash: list low-rate accounts and suggest moving to higher rate
    by_id = {b.get("account_id") or b.get("id"): b for b in balances} if balances else {}
    cash_cents = 0
    cash_accounts = []
    for a in accounts:
        bal = by_id.get(a.get("id") or a.get("account_id"), a)
        cents = bal.get("balance_cents", a.get("balance_cents", 0)) or 0
        atype = (a.get("type") or bal.get("account_type") or "").lower()
        name = a.get("name") or bal.get("account_name") or "Account"
        inst = a.get("institution_id") or bal.get("institution_id") or ""
        if atype in ("chequing", "savings"):
            cash_cents += cents
            if inst and inst.upper() != "WEALTHSIMPLE":
                cash_accounts.append((name, inst, cents))
    if cash_cents > 0:
        extra = cash_cents / 100 * (ws_pct / 100 - 0.005)
        if cash_accounts:
            detail = "; ".join(f"{n} at {i} (${c/100:,.0f})" for n, i, c in cash_accounts[:3])
            recs.append({
                "title": "Earn more on idle cash",
                "response": f"You have ${cash_cents/100:,.0f} in chequing/savings ({detail}). Moving this to Wealthsimple Cash ({ws_pct}% ongoing) could earn about ${extra:,.0f} more per year than typical big-bank rates (~0.5%). Consider keeping an emergency buffer in chequing and moving the rest."
            })
        else:
            recs.append({
                "title": "Earn more on idle cash",
                "response": f"You have ${cash_cents/100:,.0f} in cash. Wealthsimple Cash offers {ws_pct}% ongoing—moving idle cash there could earn about ${extra:,.0f} more per year than ~0.5% at many big banks."
            })

    # 2. RESP / CESG (if children or education goal)
    children = (resp or {}).get("child_beneficiaries", [])
    resp_accounts = (resp or {}).get("resp_accounts", [])
    has_education_goal = any("educ" in (g.get("name") or "").lower() for g in goals_list)
    if children or has_education_goal or resp_accounts:
        num_kids = len(children) if children else 1
        recs.append({
            "title": "Maximize education savings (RESP & CESG)",
            "response": f"Consider contributing to an RESP to get the 20% CESG match—up to $500 per child per year on the first $2,500. That's free money from the government. With {num_kids} child(ren), maxing the match could mean $500–$1,000+ in grants each year. CESG is available until the year the child turns 17."
        })

    # 3. TFSA
    tfsa = (room.get("tfsa") or {}) if isinstance(room.get("tfsa"), dict) else {}
    tfsa_lim = tfsa.get("annual_limit_cents", 700000) or 700000
    tfsa_bal = tfsa.get("current_balance_cents", 0) or 0
    recs.append({
        "title": "Use your TFSA room",
        "response": f"TFSA limit is $7,000 per year (2025). Growth and withdrawals are tax-free. Your current TFSA balance is ${tfsa_bal/100:,.0f}. Unused room carries forward. Top up when you can to build tax-free savings. Check CRA My Account for your exact contribution room."
    })

    # 4. RRSP
    rrsp = (room.get("rrsp") or {}) if isinstance(room.get("rrsp"), dict) else {}
    rrsp_room = rrsp.get("estimated_room_cents", 0) or 0
    rrsp_bal = rrsp.get("current_balance_cents", 0) or 0
    has_retirement = any("retire" in (g.get("name") or "").lower() for g in goals_list)
    recs.append({
        "title": "RRSP for retirement",
        "response": f"RRSP contributions are tax-deductible and grow tax-deferred. You have an estimated ${rrsp_room/100:,.0f} in room and ${rrsp_bal/100:,.0f} current balance. Contributing before the deadline (first 60 days of next year for prior year) can lower your tax bill. Max is 18% of income, capped at $32,490 (2026)."
    })

    # 5. Emergency fund
    emergency_goals = [g for g in goals_list if "emergency" in (g.get("name") or "").lower()]
    target = emergency_goals[0].get("target_amount_cents", 0) / 100 if emergency_goals else 0
    recs.append({
        "title": "Emergency fund",
        "response": f"Keep 3–6 months of expenses in an accessible place. High-interest savings (e.g. Wealthsimple Cash at {ws_pct}%) lets you earn interest while staying liquid. If you have an emergency goal (e.g. ${target:,.0f}), consider building toward it in a separate savings account so you don't touch it for day-to-day spending."
    })

    # 6. FHSA (if first-home goal or we have room)
    fhsa = (room.get("fhsa") or {}) if isinstance(room.get("fhsa"), dict) else {}
    fhsa_room = fhsa.get("estimated_room_lifetime_cents", 0) or 0
    has_home_goal = any("home" in (g.get("name") or "").lower() for g in goals_list)
    if has_home_goal or fhsa_room > 0:
        recs.append({
            "title": "First-time home: FHSA",
            "response": "If you're a first-time buyer (no principal residence in the last 4 years), the FHSA offers $8,000/year up to $40,000 lifetime. Contributions are tax-deductible and withdrawals for a qualifying home are tax-free. Open one and contribute when you can—unused room carries forward up to $8,000."
        })

    # 7. Tax efficiency / non-registered
    non_reg = [a for a in accounts if (a.get("type") or "").lower() in ("non_registered", "non-registered")]
    if non_reg or len(recs) < 6:
        recs.append({
            "title": "Tax efficiency",
            "response": "Hold investments in this order for tax efficiency: TFSA and RRSP first (sheltered), then FHSA if buying a first home, then non-registered. In non-registered accounts, tax loss harvesting can offset capital gains—but avoid the superficial loss rule (no repurchase within 61 days). Consider talking to a tax advisor for your situation."
        })

    return recs[:7]


def _project_total_series(
    cash_dollars: float,
    invested_dollars: float,
    years: int,
    cash_rate: float,
    invested_rate: float,
    annual_invested_contribution: float = 0.0,
    annual_cash_contribution: float = 0.0,
    annual_cesg: float = 0.0,
) -> list[float]:
    """Project a simple annual total balance series for now + each year."""
    series = [round(cash_dollars + invested_dollars, 2)]
    c_cash, c_inv = cash_dollars, invested_dollars
    for _ in range(years):
        c_cash = (c_cash + annual_cash_contribution) * (1 + cash_rate)
        c_inv = (c_inv + annual_invested_contribution + annual_cesg) * (1 + invested_rate)
        series.append(round(c_cash + c_inv, 2))
    return series


def _build_strategy_assumptions_note(
    title: str,
    scenario_note: str,
    cash_rate_pct: float,
    invested_rate_pct: float,
    annual_invested_contribution: float,
    annual_cash_contribution: float,
    annual_cesg: float,
) -> str:
    """Build recommendation-specific assumptions so each chart note is unique and explicit."""
    parts = [
        f"Strategy: {title}.",
        scenario_note,
        f"Cash growth {cash_rate_pct:.2f}%; investments {invested_rate_pct:.2f}%.",
        f"Annual invested contribution ${annual_invested_contribution:,.0f}.",
        f"Annual cash contribution ${annual_cash_contribution:,.0f}.",
    ]
    if annual_cesg > 0:
        parts.append(f"Annual CESG ${annual_cesg:,.0f}.")
    return " ".join(parts)


def _build_chart_spec_for_recommendation(context: dict, recommendation: dict, index: int) -> dict | None:
    """
    Build a 5-year line chart spec for one recommendation item.
    The baseline is current path; recommendation path applies one strategy-specific improvement.
    """
    accounts = context.get("accounts", [])
    balances = context.get("balances", [])
    if not accounts and not balances:
        return None

    cash_now, invested_now = _balances_by_type(accounts, balances)
    total_now = cash_now + invested_now
    if total_now <= 0:
        return None

    title = (recommendation.get("title") or f"Recommendation {index + 1}").strip()
    body = (recommendation.get("response") or "").strip()
    text = f"{title} {body}".lower()

    r_cash_current = CURRENT_SAVINGS_RATE_ANNUAL_PCT / 100.0
    r_cash_opt = OPTIMIZED_SAVINGS_RATE_ANNUAL_PCT / 100.0
    r_inv = INVESTMENT_GROWTH_ANNUAL_PCT / 100.0
    years = PROJECTION_YEARS

    base_series = _project_total_series(
        cash_dollars=cash_now,
        invested_dollars=invested_now,
        years=years,
        cash_rate=r_cash_current,
        invested_rate=r_inv,
    )

    rec_cash_rate = r_cash_opt
    annual_invested_contribution = 0.0
    annual_cash_contribution = 0.0
    annual_cesg = 0.0
    scenario_note = "Higher-rate cash optimization on idle cash."

    if any(k in text for k in ("resp", "education", "cesg")):
        children = (context.get("resp_eligibility") or {}).get("child_beneficiaries", []) or []
        num_kids = max(1, len(children))
        annual_invested_contribution = 2500.0 * num_kids
        annual_cesg = min(500.0 * num_kids, annual_invested_contribution * RESP_CESG_BASIC_RATE)
        rec_cash_rate = r_cash_current
        scenario_note = "RESP annual contributions plus CESG grants and long-term growth."
    elif "tfsa" in text:
        tfsa = (context.get("contribution_room", {}).get("tfsa") or {}) if isinstance(context.get("contribution_room", {}).get("tfsa"), dict) else {}
        annual_invested_contribution = min(float((tfsa.get("annual_limit_cents", 700000) or 700000) / 100), float(tfsa_annual_limit(2025)))
        rec_cash_rate = r_cash_current
        scenario_note = "TFSA annual contributions invested for long-term growth."
    elif any(k in text for k in ("rrsp", "retire")):
        rrsp = (context.get("contribution_room", {}).get("rrsp") or {}) if isinstance(context.get("contribution_room", {}).get("rrsp"), dict) else {}
        room = float((rrsp.get("estimated_room_cents", 0) or 0) / 100)
        annual_invested_contribution = min(room if room > 0 else 3000.0, 6000.0)
        rec_cash_rate = r_cash_current
        scenario_note = "RRSP annual contributions invested for retirement growth."
    elif any(k in text for k in ("fhsa", "home")):
        fhsa = (context.get("contribution_room", {}).get("fhsa") or {}) if isinstance(context.get("contribution_room", {}).get("fhsa"), dict) else {}
        lifetime_room = float((fhsa.get("estimated_room_lifetime_cents", 0) or 0) / 100)
        annual_invested_contribution = min(FHSA_ANNUAL_LIMIT, lifetime_room if lifetime_room > 0 else FHSA_ANNUAL_LIMIT)
        rec_cash_rate = r_cash_current
        scenario_note = "FHSA annual contributions with long-term growth assumptions."
    elif "emergency" in text:
        rec_cash_rate = r_cash_opt
        scenario_note = "Emergency fund moved to high-interest cash while staying liquid."
    elif any(k in text for k in ("tax", "non-registered")):
        rec_cash_rate = r_cash_opt
        annual_invested_contribution = 2000.0
        scenario_note = "Tax-efficient contribution mix with higher-rate cash and invested growth."

    recommended_series = _project_total_series(
        cash_dollars=cash_now,
        invested_dollars=invested_now,
        years=years,
        cash_rate=rec_cash_rate,
        invested_rate=r_inv,
        annual_invested_contribution=annual_invested_contribution,
        annual_cash_contribution=annual_cash_contribution,
        annual_cesg=annual_cesg,
    )

    labels = ["Now"] + [f"Year {i}" for i in range(1, years + 1)]
    rates_note = _build_strategy_assumptions_note(
        title=title,
        scenario_note=scenario_note,
        cash_rate_pct=rec_cash_rate * 100,
        invested_rate_pct=r_inv * 100,
        annual_invested_contribution=annual_invested_contribution,
        annual_cash_contribution=annual_cash_contribution,
        annual_cesg=annual_cesg,
    )
    return {
        "type": "five_year_projection",
        "title": title,
        "labels": labels,
        "series_current_dollars": base_series,
        "series_recommended_dollars": recommended_series,
        "today_dollars": round(base_series[0], 2),
        "five_year_current_dollars": round(base_series[-1], 2),
        "five_year_recommended_dollars": round(recommended_series[-1], 2),
        "rates_note": rates_note,
    }


def _call_llm(prompt: str, context: dict | None = None, max_tokens: int = 700) -> str:
    """Call OpenAI for recommendation narrative. Returns context-aware fallback if no API key or on error."""
    fallback = _fallback_recommendation_from_context(context) if context else (
        "Consider RESP for the 20% CESG match, TFSA for tax-free growth ($7k/yr), RRSP for retirement, and FHSA for first-time buyers. "
        "Moving big-bank savings to Wealthsimple Cash could earn ~4% vs ~0.5%. Check CRA My Account for your exact room."
    )
    if not (getattr(settings, "openai_api_key", None) and settings.openai_api_key.strip()):
        return fallback
    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
        )
        return (r.choices[0].message.content or "").strip()
    except Exception as e:
        return f"[Recommendation engine temporarily unavailable: {e}.] " + fallback


def _balances_by_type(accounts: list, balances: list) -> tuple[float, float]:
    """
    Split household balances into cash (chequing/savings) vs invested (TFSA, RRSP, etc.).
    Returns (cash_dollars, invested_dollars).
    """
    by_id = {b.get("account_id") or b.get("id"): b for b in balances} if balances else {}
    cash_cents = 0
    invested_cents = 0
    for a in accounts:
        bal = by_id.get(a.get("id") or a.get("account_id"), a)
        cents = bal.get("balance_cents", a.get("balance_cents", 0)) or 0
        atype = (a.get("type") or bal.get("account_type") or "").lower()
        if atype in ("chequing", "savings"):
            cash_cents += cents
        else:
            invested_cents += cents
    if not accounts and balances:
        for b in balances:
            name = (b.get("account_name") or "").lower()
            cents = b.get("balance_cents", 0) or 0
            if "savings" in name or "chequing" in name:
                cash_cents += cents
            else:
                invested_cents += cents
    return cash_cents / 100.0, invested_cents / 100.0


def _build_five_year_projection(context: dict) -> dict | None:
    """
    Build a line chart spec: Now vs Year 1..5 for "Current path" (no change) and "With strategies" (optimized rates).
    Uses rate_assumptions for current savings 0.5%, optimized savings 4%, investment growth 5%.
    """
    accounts = context.get("accounts", [])
    balances = context.get("balances", [])
    if not accounts and not balances:
        return None
    cash_now, invested_now = _balances_by_type(accounts, balances)
    total_now = cash_now + invested_now
    if total_now <= 0:
        return None
    r_cash = CURRENT_SAVINGS_RATE_ANNUAL_PCT / 100.0
    r_cash_opt = OPTIMIZED_SAVINGS_RATE_ANNUAL_PCT / 100.0
    r_inv = INVESTMENT_GROWTH_ANNUAL_PCT / 100.0
    n = PROJECTION_YEARS

    # Current path: cash at 0.5%, invested at 5%; no reallocation
    series_current = [round(total_now, 2)]
    c_cash, c_inv = cash_now, invested_now
    for _ in range(n):
        c_cash = c_cash * (1 + r_cash)
        c_inv = c_inv * (1 + r_inv)
        series_current.append(round(c_cash + c_inv, 2))

    # With strategies: move cash to 4%, invested at 5%
    series_recommended = [round(total_now, 2)]
    o_cash, o_inv = cash_now, invested_now
    for _ in range(n):
        o_cash = o_cash * (1 + r_cash_opt)
        o_inv = o_inv * (1 + r_inv)
        series_recommended.append(round(o_cash + o_inv, 2))

    labels = ["Now"] + [f"Year {i}" for i in range(1, n + 1)]
    return {
        "type": "five_year_projection",
        "title": "Projected total: current path vs with strategies (5 years)",
        "labels": labels,
        "series_current_dollars": series_current,
        "series_recommended_dollars": series_recommended,
        "rates_note": f"Assumptions: cash {CURRENT_SAVINGS_RATE_ANNUAL_PCT}% (current) vs {OPTIMIZED_SAVINGS_RATE_ANNUAL_PCT}% (optimized); investments {INVESTMENT_GROWTH_ANNUAL_PCT}% growth.",
    }


def _build_chart_spec(context: dict, narrative: str) -> dict | None:
    """
    Produce chart spec: prefer 5-year line graph (now vs 5 years); else before/after bar or goal progress.
    """
    accounts = context.get("accounts", [])
    balances = context.get("balances", [])
    goals_list = context.get("goals", [])

    # Primary: 5-year projection line chart when we have balances
    if accounts or balances:
        line_spec = _build_five_year_projection(context)
        if line_spec:
            return line_spec
    if not balances and not goals_list:
        return None

    # Fallback: before/after bar (savings only)
    savings_accounts = [b for b in balances if "savings" in (b.get("account_name") or "").lower() or "chequing" in (b.get("account_name") or "").lower()]
    total_cents = sum(b.get("balance_cents", 0) for b in savings_accounts)
    if total_cents > 0:
        total_dollars = total_cents / 100
        return {
            "type": "before_after_interest",
            "title": "Potential interest: current vs high-interest cash (4%)",
            "labels": ["Current (0.5%)", "Optimized (4%)"],
            "values_cents": [int(total_dollars * 0.005 * 100), int(total_dollars * 0.04 * 100)],
            "values_dollars": [round(total_dollars * 0.005, 2), round(total_dollars * 0.04, 2)],
            "period": "1 year",
            "total_balance_cents": total_cents,
        }
    if goals_list:
        return {
            "type": "goal_progress",
            "title": "Goals",
            "goals": [
                {"name": g.get("name"), "target_amount_cents": g.get("target_amount_cents"), "target_date": g.get("target_date")}
                for g in goals_list[:5]
            ],
        }
    return None


def _build_prompt_for_list(context: dict) -> str:
    """Build prompt that asks for 5–7 recommendations in ## Title \\n Body format."""
    data_block = _format_context_for_llm(context)
    topics = "\n".join(f"  - {t}" for t in AUTO_RECOMMENDATION_TOPICS[:7])
    prompt = f"""You are a Canadian financial advisor. Use ONLY the household data below. Give exactly 5 to 7 short recommendations. Each must use their real account names, institutions, and dollar amounts—do not make up numbers.

Household data:
{data_block}

Cover these topics (one recommendation per topic; use the data above for amounts and names):
{topics}

For each recommendation: use conditional "if" phrasing when relevant, direct the user to the best next step, and show the expected improvement in numbers when possible.

{AUTO_LIST_INSTRUCTION}"""
    return prompt


def _parse_recommendations_list(text: str) -> list[dict]:
    """
    Parse LLM output into list of { "title": str, "response": str }.
    Expects blocks starting with ## Title; body is everything until the next ## or end.
    """
    import re
    out = []
    # Split by ## at start of line; first segment may be preamble (skip if no ##)
    blocks = re.split(r"\n##\s*", text, flags=re.IGNORECASE)
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        title = lines[0].strip().strip("#").strip()
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        if not title:
            continue
        out.append({"title": title, "response": body or title})
    return out


def run_recommendation_list_from_context(
    context: dict,
    include_visualization: bool = True,
    min_recommendations: int = 5,
) -> dict:
    """
    Produce 5+ recommendations (list of title + response) and one chart spec.
    Returns { "recommendations": [ { "title", "response" }, ... ], "chart_spec": dict | None }.
    """
    prompt = _build_prompt_for_list(context)
    narrative = _call_llm(prompt, context, max_tokens=1200)
    parsed = _parse_recommendations_list(narrative)
    # If parsing produced fewer than min, use rule-based fallback list (specific to household data)
    if len(parsed) < min_recommendations:
        import re
        numbered = re.split(r"\n\s*\d+[.)]\s+", narrative)
        numbered = [s.strip() for s in numbered if s.strip()][:10]
        if len(numbered) >= min_recommendations:
            parsed = [{"title": f"Recommendation {i+1}", "response": t} for i, t in enumerate(numbered)]
        else:
            parsed = _build_fallback_recommendations_list(context)
    chart_spec = _build_chart_spec(context, narrative) if include_visualization else None
    if include_visualization:
        for i, rec in enumerate(parsed):
            rec["chart_spec"] = _build_chart_spec_for_recommendation(context, rec, i)
    return {"recommendations": parsed, "chart_spec": chart_spec}


def run_recommendation_from_context(
    context: dict,
    include_visualization: bool = True,
) -> dict:
    """
    Produce recommendation narrative and chart spec from pre-gathered context.
    Used by the recommendation agent after it has run DB query tools.
    Returns { "narrative": str, "chart_spec": dict | None }.
    """
    prompt = _build_prompt(context)
    narrative = _call_llm(prompt, context)
    chart_spec = _build_chart_spec(context, narrative) if include_visualization else None
    return {"narrative": narrative, "chart_spec": chart_spec}


def run_recommendation_visualization(
    db: Session,
    household_id: int,
    include_visualization: bool = True,
) -> dict:
    """
    Main entry: gather context, call GenAI for narrative, optionally produce chart spec.
    Returns { "narrative": str, "chart_spec": dict | None }.
    """
    context = _gather_context(db, household_id)
    return run_recommendation_from_context(context, include_visualization)
