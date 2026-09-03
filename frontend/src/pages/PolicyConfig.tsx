import React from 'react';
import { ShieldCheck, AlertTriangle, CheckCircle2, Lock, Sliders, Database } from 'lucide-react';

export default function PolicyConfig() {
  return (
    <div className="p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight">Policy Engine & Guardrail Configuration</h1>
        <p className="text-sm text-slate-400 mt-1">
          Deterministic financial safety rules governing when RECON-X is authorized to auto-resolve discrepancies vs mandate human controller approval.
        </p>
      </div>

      {/* Safety Philosophy Banner */}
      <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-2">
        <div className="flex items-center gap-2 text-emerald-400 text-sm font-bold">
          <Lock className="w-4 h-4" />
          The Golden Rule of Autonomous Financial Control
        </div>
        <p className="text-xs text-slate-300 leading-relaxed">
          AI models provide advisory root-cause investigation and natural language audit narratives. 
          <strong> An LLM is NEVER permitted to execute debit/credit adjustments or mutate general ledger states directly. </strong>
          All state transitions are strictly governed by deterministic threshold filters, double-entry arithmetic checks, and append-only audit logs.
        </p>
      </div>

      {/* Guardrail Controls */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Threshold 1: Confidence */}
        <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-white">Confidence Gate Threshold</h3>
            <span className="text-xs px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 font-mono font-bold">85.0%</span>
          </div>
          <p className="text-xs text-slate-400">
            Minimum mathematical & evidence confidence score required for safe automated resolution. Any score below this triggers human escalation.
          </p>
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div className="bg-emerald-400 h-full w-[85%]"></div>
          </div>
        </div>

        {/* Threshold 2: Variance Limit */}
        <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-bold text-white">Max Auto-Resolve Variance</h3>
            <span className="text-xs px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 font-mono font-bold">₹10.00 (1000 paise)</span>
          </div>
          <p className="text-xs text-slate-400">
            Absolute monetary exposure limit for automated rounding corrections (limited to &le; 0.5% of total transaction value).
          </p>
          <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
            <div className="bg-emerald-400 h-full w-[10%]"></div>
          </div>
        </div>
      </div>

      {/* Guardrail Rules Table */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden shadow-xl space-y-4 p-6">
        <h3 className="text-base font-bold text-white">Deterministic Action Permission Matrix</h3>
        <table className="w-full text-left border-collapse text-xs">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400 font-semibold">
              <th className="pb-3">Exception Category</th>
              <th className="pb-3">Allowed Action</th>
              <th className="pb-3">Resolution Mode</th>
              <th className="pb-3">Mandatory Verification</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800 text-slate-300">
            <tr>
              <td className="py-3 font-semibold text-white">Timing Difference (&gt;24h)</td>
              <td className="py-3 font-mono text-emerald-400">MARK_TIMING_RECONCILED</td>
              <td className="py-3"><span className="text-emerald-400 font-bold">Autonomous Safe</span></td>
              <td className="py-3 text-slate-400">Variance = ₹0.00</td>
            </tr>
            <tr>
              <td className="py-3 font-semibold text-white">Gateway Fee Deduction</td>
              <td className="py-3 font-mono text-emerald-400">POST_FEE_ADJUSTMENT</td>
              <td className="py-3"><span className="text-emerald-400 font-bold">Autonomous Safe</span></td>
              <td className="py-3 text-slate-400">Gross - Fee - Tax = Ledger</td>
            </tr>
            <tr>
              <td className="py-3 font-semibold text-white">Verified Refund Offset</td>
              <td className="py-3 font-mono text-emerald-400">ASSOCIATE_REFUND</td>
              <td className="py-3"><span className="text-emerald-400 font-bold">Autonomous Safe</span></td>
              <td className="py-3 text-slate-400">Refund ID verified on gateway</td>
            </tr>
            <tr>
              <td className="py-3 font-semibold text-white">Card Dispute / Chargeback</td>
              <td className="py-3 font-mono text-amber-400">HOLD_FOR_HUMAN_REVIEW</td>
              <td className="py-3"><span className="text-amber-400 font-bold">FORBIDDEN AUTO-RESOLVE</span></td>
              <td className="py-3 text-slate-400">Merchant dispute defense approval</td>
            </tr>
            <tr>
              <td className="py-3 font-semibold text-white">Missing in Ledger / ERP</td>
              <td className="py-3 font-mono text-amber-400">ESCALATE_TO_FINANCE</td>
              <td className="py-3"><span className="text-amber-400 font-bold">FORBIDDEN AUTO-RESOLVE</span></td>
              <td className="py-3 text-slate-400">ERP journal posting review</td>
            </tr>
            <tr>
              <td className="py-3 font-semibold text-white">Amount Mismatch (&gt; ₹10)</td>
              <td className="py-3 font-mono text-amber-400">ESCALATE_TO_FINANCE</td>
              <td className="py-3"><span className="text-amber-400 font-bold">FORBIDDEN AUTO-RESOLVE</span></td>
              <td className="py-3 text-slate-400">Invoice discrepancy investigation</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
