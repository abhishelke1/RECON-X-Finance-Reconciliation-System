# RECON-X System Architecture

**Track 04: AI Finance Controller — Razorpay AI Buildathon 2026**

## 1. Architectural Philosophy
RECON-X is designed as an autonomous finance controller that reconciles payment-to-ledger records, explains discrepancies, automatically resolves safe exceptions, and escalates uncertain cases to humans.

Financial integrity demands strict boundaries between probabilistic AI and deterministic accounting:
1. **Zero LLM in Matching & Calculations**: Transaction matching (L1–L4) and monetary balance arithmetic are 100% deterministic using Python `Decimal` and SQL queries.
2. **AI as Advisory Investigator**: Large Language Models (Gemini 2.5) investigate evidence causality graphs and draft root-cause hypotheses with anti-hallucination citation checks.
3. **Deterministic Financial Guardrails**: The LLM is never permitted to mutate ledger balances. Automated resolutions are gated by strict mathematical policies (e.g. max variance ₹10.00, confidence &ge; 85%, forbidden chargeback auto-resolve).
4. **Complete Audit Trail**: Every automated and human decision creates an immutable, append-only `AuditLog` and `Decision` record.

---

## 2. High-Level System Architecture

```
[ Razorpay API / Webhooks ]     [ ERP / Tally / Bank Feeds ]
           │                                 │
           ▼                                 ▼
┌─────────────────────────────────────────────────────────┐
│ 1. INGESTION & CANONICAL NORMALIZATION                   │
│ - Paise-to-INR exact Decimal math (divide by 100)        │
│ - UTC ISO 8601 timestamp standardization                │
│ - Source-system duplicate detection & idempotency       │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│ 2. 4-TIER CASCADING MATCHING ENGINE                     │
│ Level 1: Exact ID (order_source_id, payment_id, ref_id) │
│ Level 2: Composite Key (amount + date proximity + phone)│
│ Level 3: Attribute Matching (gross - fee - tax = net)   │
│ Level 4: Fuzzy Text Matching (customer name / initials) │
│ Conflict Resolver: Multi-candidate margin tie-breaking │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│ 3. FINANCIAL RECONCILIATION ENGINE                      │
│ - Gross, fee, tax, refund, dispute position calculation │
│ - 10-State Classification (Matched, Timing Diff, etc.)  │
│ - Automated Exception & Evidence Link generation        │
└──────────────┬───────────────────────────┬──────────────┘
               │ (Clean Matches)           │ (Exceptions Found)
               ▼                           ▼
      [ Settle & Mark Done ]      ┌───────────────────────────────┐
                                  │ 4. EVIDENCE GRAPH COLLECTOR   │
                                  │ Builds causality graph nodes  │
                                  └──────────────┬────────────────┘
                                                 │
                                                 ▼
                                  ┌───────────────────────────────┐
                                  │ 5. AI ROOT-CAUSE INVESTIGATOR │
                                  │ Gemini LLM + Anti-Hallucin.   │
                                  │ Ground-truth citation verify  │
                                  └──────────────┬────────────────┘
                                                 │
                                                 ▼
                                  ┌───────────────────────────────┐
                                  │ 6. DETERMINISTIC POLICY ENGINE│
                                  │ Confidence &ge; 85%?           │
                                  │ Variance &le; ₹10.00?          │
                                  │ High risk (chargeback)?       │
                                  └───────┬───────────────┬───────┘
                                          │               │
                                 (Safe)   │               │ (Risky / Uncertain)
                                          ▼               ▼
                           ┌────────────────────┐   ┌────────────────────┐
                           │ AUTO-RESOLUTION    │   │ HUMAN REVIEW QUEUE │
                           │ Mark Timing Recon  │   │ Controller Approve │
                           │ Post Fee Adjust    │   │ Reject / Req Info  │
                           │ Associate Refund   │   │ Mark False Alarm   │
                           └─────────┬──────────┘   └─────────┬──────────┘
                                     │                        │
                                     └───────────┬────────────┘
                                                 │
                                                 ▼
                                  ┌───────────────────────────────┐
                                  │ 7. IMMUTABLE AUDIT LOG TRAIL  │
                                  │ Append-only decision record   │
                                  └───────────────────────────────┘
```

---

## 3. Database Schema Overview
15 relational tables using SQLAlchemy 2.0 and exact `Numeric(20, 4)` types:
- `merchants`: Multi-tenant merchant profile.
- `payments`: Canonical payment records with fees, taxes, and raw metadata.
- `orders`: Order entity linkage.
- `settlements`: Payout and settlement batch records.
- `refunds`: Refund offset tracking.
- `chargebacks`: Card dispute claims and reasons.
- `ledger_entries`: General ledger entries (debit/credit).
- `reconciliation_runs`: Atomic reconciliation execution summary.
- `reconciliation_matches`: Individual matched transaction records.
- `exceptions`: Discrepancy records with severity and state.
- `exception_evidence`: Immutable evidence snapshots.
- `decisions`: Comprehensive decision history.
- `audit_logs`: Append-only compliance log.
- `evaluation_runs`: Empirical benchmark metrics.

---

## 4. 4-Tier Matching Engine Details
1. **Level 1 (Exact ID Linkage)**:
   - Direct match by `order_source_id`, `reference_id`, or `payment_id`.
   - Confidence: 1.0.
2. **Level 2 (Composite Key)**:
   - Matches by exact amount, timestamp proximity (&plusmn;3 days), and customer identifiers (phone number, email, or order ID in description).
   - Confidence: 0.90–0.95.
3. **Level 3 (Attribute Net Matching)**:
   - Reconciles net amounts after gateway MDR fee & tax deductions: `gross_amount - fee - tax == ledger_amount`.
   - Confidence: 0.75–0.88.
4. **Level 4 (Fuzzy Matching)**:
   - Token-level similarity on customer names, descriptions, and initials (e.g. matching "Aarav Sharma" to "A Sharma").
   - Confidence: 0.50–0.74.
5. **Conflict Resolver**:
   - Detects 1-to-N or N-to-1 collisions. Breaks ties if the top candidate exceeds the runner-up by a &ge;0.10 margin; otherwise flags `MatchStatus.CONFLICT`.

---

## 5. Deterministic Policy Guardrails
Auto-resolution is permitted **ONLY IF ALL** conditions hold:
- AI confidence &ge; 0.85.
- `requires_human_review == False`.
- Exception type is in approved safe set: `TIMING_DIFFERENCE` (with 0 variance), `REFUND_RELATED` (verified refund ID), or micro-rounding (&le; ₹10.00 and &le; 0.5%).
- **Forbidden from Auto-Resolution**:
  - `CHARGEBACK_RELATED`: Mandatory controller review.
  - `MISSING_RECORD`: Requires manual ERP journal posting.
  - `AMOUNT_MISMATCH` (&gt; ₹10.00): Requires invoice adjustment.
