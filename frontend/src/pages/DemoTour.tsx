import React, { useState } from 'react';
import { 
  Play, CheckCircle2, AlertTriangle, ShieldCheck, 
  BrainCircuit, ArrowRight, Layers, FileText, Lock 
} from 'lucide-react';

interface Scenario {
  id: string;
  title: string;
  badge: string;
  badgeColor: string;
  description: string;
  gatewayAmount: string;
  ledgerAmount: string;
  variance: string;
  matchingTier: string;
  aiExplanation: string;
  policyOutcome: string;
  policyReason: string;
  actionTaken: string;
  isAutoResolved: boolean;
}

const DEMO_SCENARIOS: Scenario[] = [
  {
    id: 'A',
    title: 'Scenario A: Clean 1:1 Direct Settlement',
    badge: '1:1 Match',
    badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    description: 'UPI customer payment captured on Razorpay and reflected with identical amount in general ledger.',
    gatewayAmount: '₹2,499.00',
    ledgerAmount: '₹2,499.00',
    variance: '₹0.00',
    matchingTier: 'Level 1: Exact ID (pay_2499)',
    aiExplanation: 'Transaction references match exactly with 0 variance. No fee deductions or dispute holds present.',
    policyOutcome: 'Reconciled',
    policyReason: 'Exact match verified. No exception created.',
    actionTaken: 'SETTLED_MATCHED',
    isAutoResolved: true,
  },
  {
    id: 'B',
    title: 'Scenario B: Gateway Fee & GST Deduction',
    badge: 'Fee Tolerance',
    badgeColor: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    description: 'Credit card payment where Razorpay deducted 2% gateway MDR + 18% GST on fee before bank deposit.',
    gatewayAmount: '₹10,000.00 (Gross)',
    ledgerAmount: '₹9,764.00 (Net)',
    variance: '-₹236.00 (Fees)',
    matchingTier: 'Level 3: Attribute Net Matching (gross - fee - tax)',
    aiExplanation: 'Expected gross position ₹10,000 matches payment. Gateway MDR ₹200 + ₹36 GST accounts for the ₹236 bank deduction.',
    policyOutcome: 'Auto-Resolved',
    policyReason: 'Deduction matches exact contractual gateway fee schedule. Variance verified as approved fee expense.',
    actionTaken: 'POST_FEE_ADJUSTMENT',
    isAutoResolved: true,
  },
  {
    id: 'C',
    title: 'Scenario C: Bank Weekend Clearance Timing Delay',
    badge: 'Timing Difference',
    badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    description: 'Payment captured on Friday evening; bank settlement credit cleared on Tuesday morning (T+2 banking delay).',
    gatewayAmount: '₹5,000.00',
    ledgerAmount: '₹5,000.00',
    variance: '₹0.00',
    matchingTier: 'Level 2: Composite Key (Amount + Date Proximity + Phone)',
    aiExplanation: 'Transaction timestamps show 72h difference due to second Saturday & Sunday banking holiday. Amount matches exactly.',
    policyOutcome: 'Auto-Resolved (Safe)',
    policyReason: 'Zero monetary variance. Clearance delay adheres to standard RBI RTGS holiday calendar.',
    actionTaken: 'MARK_TIMING_RECONCILED',
    isAutoResolved: true,
  },
  {
    id: 'D',
    title: 'Scenario D: Verified Customer Refund Offset',
    badge: 'Refund Offset',
    badgeColor: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    description: 'Customer requested order return; refund was processed on gateway, netting out invoice position.',
    gatewayAmount: '₹1,250.00 (Refunded)',
    ledgerAmount: '₹0.00 (Net Ledger Credit)',
    variance: '₹0.00',
    matchingTier: 'Level 3: Attribute Matching via Refund Entity rfnd_1250',
    aiExplanation: 'Payment pay_1250 was reversed by processed refund rfnd_1250. Net accounting position is zero.',
    policyOutcome: 'Auto-Resolved (Safe)',
    policyReason: 'Refund verified against Razorpay gateway ledger. Zero net balance exposure.',
    actionTaken: 'ASSOCIATE_REFUND',
    isAutoResolved: true,
  },
  {
    id: 'E',
    title: 'Scenario E: Card Dispute / Chargeback Hold',
    badge: 'High Risk Dispute',
    badgeColor: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    description: 'Cardholder bank raised a chargeback claim for unauthorized transaction; gateway withheld payout.',
    gatewayAmount: '₹8,500.00',
    ledgerAmount: '₹0.00 (Held in Escrow)',
    variance: '-₹8,500.00',
    matchingTier: 'Level 1: Exact ID Link to Dispute disp_8500',
    aiExplanation: 'Issuer dispute opened for fraudulent card claim. Payout suspended pending representation evidence.',
    policyOutcome: 'MANDATORY HUMAN REVIEW',
    policyReason: 'Chargeback exceptions are strictly forbidden from automated resolution. Requires controller dispute defense filing.',
    actionTaken: 'ESCALATE_TO_SENIOR_CONTROLLER',
    isAutoResolved: false,
  },
  {
    id: 'F',
    title: 'Scenario F: Partial Installment Settlement',
    badge: 'Partial Settlement',
    badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    description: 'High-ticket B2B order invoiced for ₹50,000 settled in two equal milestone tranches.',
    gatewayAmount: '₹50,000.00',
    ledgerAmount: '₹25,000.00 (Tranche 1)',
    variance: '-₹25,000.00',
    matchingTier: 'Level 2: Composite Key Match on Order Receipt',
    aiExplanation: 'Ledger entry records installment payment 1 of 2. Remaining ₹25,000 uncredited.',
    policyOutcome: 'MANDATORY HUMAN REVIEW',
    policyReason: 'Large monetary variance exceeds autonomous threshold. Controller must link Tranche 2 installment.',
    actionTaken: 'ESCALATE_TO_FINANCE_ANALYST',
    isAutoResolved: false,
  },
  {
    id: 'G',
    title: 'Scenario G: Missing ERP / Ledger Journal Entry',
    badge: 'Missing Record',
    badgeColor: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    description: 'Customer payment was captured on Razorpay, but accounting ERP webhook dropped due to server timeout.',
    gatewayAmount: '₹3,200.00 (Captured)',
    ledgerAmount: 'Not Found in ERP',
    variance: '-₹3,200.00',
    matchingTier: 'Unmatched (Level 1-4 Exhausted)',
    aiExplanation: 'No corresponding ledger credit found in Tally/ERP. Webhook transmission failure suspected.',
    policyOutcome: 'MANDATORY HUMAN REVIEW',
    policyReason: 'Missing financial records cannot be synthesized by AI. Requires manual ERP journal entry posting.',
    actionTaken: 'ESCALATE_TO_FINANCE_OPERATIONS',
    isAutoResolved: false,
  },
  {
    id: 'H',
    title: 'Scenario H: High-Variance Billing Mismatch',
    badge: 'Amount Mismatch',
    badgeColor: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    description: 'Customer billed for ₹7,500 on website checkout, but invoice was booked as ₹7,000 in ERP.',
    gatewayAmount: '₹7,500.00',
    ledgerAmount: '₹7,000.00',
    variance: '₹500.00',
    matchingTier: 'Level 1: Exact Reference Match with Variance',
    aiExplanation: 'Pricing mismatch detected. Cart promo code not accounted in backend ERP ledger.',
    policyOutcome: 'MANDATORY HUMAN REVIEW',
    policyReason: 'Variance of ₹500 exceeds auto-resolution limit (₹10.00). Requires credit note or invoice revision.',
    actionTaken: 'ESCALATE_TO_SENIOR_CONTROLLER',
    isAutoResolved: false,
  },
];

export default function DemoTour() {
  const [activeScenario, setActiveScenario] = useState<Scenario>(DEMO_SCENARIOS[0]);

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-xs font-semibold text-emerald-400 uppercase tracking-widest">
          <Play className="w-3.5 h-3.5 fill-emerald-400" />
          Interactive Demo Walkthrough
        </div>
        <h1 className="text-2xl font-black text-white tracking-tight mt-1">8 Real-World Financial Reconciliations</h1>
        <p className="text-sm text-slate-400 mt-1">
          Explore how RECON-X processes clean matches, resolves safe discrepancies autonomously, and enforces strict human review on risky positions.
        </p>
      </div>

      {/* Scenario Tabs */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
        {DEMO_SCENARIOS.map((s) => (
          <button
            key={s.id}
            onClick={() => setActiveScenario(s)}
            className={`p-3 rounded-lg text-left border transition-all ${
              activeScenario.id === s.id
                ? 'bg-slate-850 border-emerald-500 shadow-md shadow-emerald-500/10'
                : 'bg-slate-900 border-slate-800 hover:border-slate-700 text-slate-400'
            }`}
          >
            <div className="text-xs font-bold text-white">Scenario {s.id}</div>
            <div className="text-[10px] text-slate-400 mt-0.5 truncate">{s.badge}</div>
          </button>
        ))}
      </div>

      {/* Active Scenario Card */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 p-6 space-y-6 shadow-xl">
        {/* Title & Badge */}
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-slate-800 pb-4">
          <div>
            <span className={`px-2.5 py-0.5 rounded text-xs font-bold border ${activeScenario.badgeColor}`}>
              {activeScenario.badge}
            </span>
            <h2 className="text-xl font-bold text-white mt-2">{activeScenario.title}</h2>
            <p className="text-xs text-slate-400 mt-1">{activeScenario.description}</p>
          </div>

          <div className="flex items-center gap-2">
            <span className={`text-xs px-3 py-1 rounded-full font-bold uppercase tracking-wider ${
              activeScenario.isAutoResolved
                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
            }`}>
              {activeScenario.isAutoResolved ? 'Safe Auto-Resolution' : 'Human Review Mandated'}
            </span>
          </div>
        </div>

        {/* Position Breakdown */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-4 bg-slate-950 rounded-lg border border-slate-800">
            <span className="text-xs text-slate-400 block font-semibold">Payment Gateway (Razorpay)</span>
            <span className="text-lg font-black text-white font-mono mt-1 block">{activeScenario.gatewayAmount}</span>
          </div>
          <div className="p-4 bg-slate-950 rounded-lg border border-slate-800">
            <span className="text-xs text-slate-400 block font-semibold">General Ledger (ERP/Bank)</span>
            <span className="text-lg font-black text-white font-mono mt-1 block">{activeScenario.ledgerAmount}</span>
          </div>
          <div className="p-4 bg-slate-950 rounded-lg border border-slate-800">
            <span className="text-xs text-slate-400 block font-semibold">Calculated Variance</span>
            <span className={`text-lg font-black font-mono mt-1 block ${
              activeScenario.variance === '₹0.00' ? 'text-emerald-400' : 'text-amber-400'
            }`}>
              {activeScenario.variance}
            </span>
          </div>
        </div>

        {/* Pipeline Details */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
          {/* Matching & AI */}
          <div className="space-y-4">
            <div className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <Layers className="w-4 h-4 text-emerald-400" />
                Deterministic Match Classification
              </div>
              <p className="text-xs text-slate-300 font-mono">{activeScenario.matchingTier}</p>
            </div>

            <div className="p-4 bg-slate-950 rounded-lg border border-slate-800 space-y-2">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <BrainCircuit className="w-4 h-4 text-indigo-400" />
                AI Root-Cause Investigation
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{activeScenario.aiExplanation}</p>
            </div>
          </div>

          {/* Policy Guardrail Evaluation */}
          <div className="p-5 bg-slate-950 rounded-lg border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <ShieldCheck className="w-4 h-4 text-amber-400" />
                Financial Guardrail Decision
              </div>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                Action: {activeScenario.actionTaken}
              </span>
            </div>

            <div className="text-xs space-y-2">
              <div>
                <span className="text-slate-400 block font-semibold">Policy Outcome:</span>
                <span className={`font-bold text-sm ${activeScenario.isAutoResolved ? 'text-emerald-400' : 'text-amber-400'}`}>
                  {activeScenario.policyOutcome}
                </span>
              </div>
              <div>
                <span className="text-slate-400 block font-semibold">Guardrail Assessment:</span>
                <p className="text-slate-300 mt-0.5 leading-relaxed">{activeScenario.policyReason}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
