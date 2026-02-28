# Mock data – Open Opt

Mock data is seeded by `scripts/seed_mock_data.py` and covers permutations for Banking, Investing, Family, and Research subagents (see plan §4.6).

**Password for all mock users:** `mock123`

**Email pattern:** `mock_{household_slug}_{member_index}@example.com`  
Example: `mock_smith_family_0@example.com` = first member (Parent 1) of Mock Smith Family.

---

## Logins by household

| Household | Members | Email (index = role order) | Role | Scenario |
|-----------|---------|----------------------------|------|----------|
| **Mock Smith Family** | 4 | `mock_smith_family_0@example.com` … `mock_smith_family_3@example.com` | Parent 1, Parent 2, Child 1, Child 2 | Full picture: all account types, multi-bank, RESP family plan, mixed ownership |
| **Mock Lee Family** | 3 | `mock_lee_family_0@example.com` … `mock_lee_family_2@example.com` | Parent, Child 1, Child 2 | Education focus, 1 parent, RESP-heavy, CLB-eligible |
| **Mock Chen Family** | 2 | `mock_chen_family_0@example.com`, `mock_chen_family_1@example.com` | Parent 1, Parent 2 | Retirement / high earner, maxed TFSA/RRSP, FHSA, first-home goal |
| **Mock Brown Family** | 4 | `mock_brown_family_0@example.com` … `mock_brown_family_3@example.com` | Parent 1, Parent 2, Child 1, Child 2 | Sparse: only chequing + savings, no registered accounts |
| **Mock Patel Family** | 4 | `mock_patel_family_0@example.com` … `mock_patel_family_3@example.com` | Parent 1, Parent 2, Child 1, Child 2 | Varied ages: child near 17, CESG maxed vs room, multi-bank RESPs |
| **Mock Wilson Family** | 2 | `mock_wilson_family_0@example.com`, `mock_wilson_family_1@example.com` | Parent 1, Parent 2 | Tax loss harvesting: non_registered, affiliated persons |
| **Mock Kim Family** | 2 | `mock_kim_family_0@example.com`, `mock_kim_family_1@example.com` | Parent, Child | Single parent + one child, education + emergency goals |
| **Mock Taylor Family** | 3 | `mock_taylor_family_0@example.com` … `mock_taylor_family_2@example.com` | Parent 1, Parent 2, Child | Zero/low balances, idle cash, move-to-Wealthsimple |
| **Mock Martinez Family** | 4 | `mock_martinez_family_0@example.com` … `mock_martinez_family_3@example.com` | Parent 1, Parent 2, Child 1, Child 2 | All four goal types, accounts at all six institutions |
| **Mock Singh Family** | 2 | `mock_singh_family_0@example.com`, `mock_singh_family_1@example.com` | Parent 1, Parent 2 | High earner, unused RRSP room (edge) |

---

## Permutation coverage

| Subagent | Dimension | Covered in households |
|----------|-----------|------------------------|
| **Banking** | Account mix | A (all types), B–J (varied); joint vs individual via `owner_member_index` |
| | Balances | Zero (H), low (B,H), medium/high (A,C,E,I), maxed (C) |
| | Multi-bank | A,C,E,I (RBC, TD, BMO, CIBC, Scotiabank, Wealthsimple) |
| **Investing** | Contribution room | 0% (D,H), partial (A,B,E), 100% (C); non_registered (F) |
| | Tax loss harvesting | F (non_registered, affiliated persons) |
| **Family** | Composition | 2+2 (A,D,E,I), 1+2 (B), 2+0 (C,F,J), 2+1 (H), 1+1 (G) |
| | Goals | Emergency only (H), education only (B,G), retirement (C,J), all four (I), empty (D) |
| | RESP | Family plan (A), single (B,G), CESG maxed vs room (E) |
| **Research** | Canadian rules | TFSA/RRSP/FHSA limits, RESP CESG, first-time buyer (C), superficial loss (F) |
| | Edge cases | Sparse/no registered (D), high earner unused RRSP (J), single parent (G) |

---

## Account ownership

- **`owner_member_index`** in fixtures: `0` = first member (Parent 1), `1` = second, etc.; `None` = joint/household account.
- Each family member can log in with their own email and see the same household; the accounts table shows one column per user, with balances in the owner’s column or “Household” for joint accounts.

---

## Transactions and pay patterns (SQLite)

All mock data lives in **SQLite** (`app.db`). Transactions are stored in the `transactions` table with:

- **amount_cents** (positive = income, negative = expense)
- **date**, **description**
- **pattern**: `recurring` or `one_off`
- **category**: `salary`, `rent`, `utilities`, `groceries`, `transfer`, `subscription`, `shopping`, `dining`, `other`

**Pay-pattern APIs** (auth required):

- `GET /api/accounts/{account_id}/transaction_patterns?days_back=90` — by account: recurring vs one-off, by category, monthly income/expense.
- `GET /api/households/{household_id}/transaction_patterns?days_back=90` — same across all household accounts.

Banking subagent and seed both read/write transactions from SQLite.

## Run seed

From repo root:

```bash
uv run python scripts/seed_mock_data.py
```

Options:

- **Default:** static fixtures + programmatic generated households (for-loop over settings).
- `--fixtures-only`: only static fixture households.
- `--generated-only`: only generated households (12 by default).
- `--print-logins`: list all mock emails (no DB write).

Idempotent: re-running clears existing mock households and users, then re-seeds.
