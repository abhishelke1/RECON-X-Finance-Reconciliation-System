import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  BrainCircuit, ShieldCheck, CheckCircle2, XCircle, HelpCircle, 
  ArrowLeft, Clock, Layers, AlertTriangle, FileText, Database, ShieldAlert 
} from 'lucide-react';
import api, { ExceptionDetail, AuditLog } from '../api';

export default function ExceptionDossier() {
  const { id } = useParams<{ id: string }>();
  const [detail, setDetail] = useState<ExceptionDetail | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionNotes, setActionNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (id) loadDossier(id);
  }, [id]);

  const loadDossier = async (exceptionId: string) => {
    setLoading(true);
    try {
      const [dRes, aRes] = await Promise.all([
        api.get(`/exceptions/${exceptionId}`),
        api.get(`/audit/${exceptionId}`).catch(() => ({ data: [] })),
      ]);
      setDetail(dRes.data);
      setAuditLogs(aRes.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleAction = async (actionType: 'approve' | 'reject' | 'request-info' | 'false-positive') => {
    if (!id) return;
    setSubmitting(true);
    try {
      await api.post(`/exceptions/${id}/${actionType}`, {
        reviewer: 'finance_controller@enterprise.com',
        notes: actionNotes,
        reason: actionNotes || `Controller executed ${actionType}`,
      });
      alert(`Action ${actionType} recorded successfully.`);
      loadDossier(id);
    } catch (e: any) {
      alert(`Action failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  if (loading || !detail) {
    return <div className="p-8 text-center text-slate-400">Loading audit dossier...</div>;
  }

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {/* Back Link */}
      <Link to="/exceptions" className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-emerald-400 transition-colors">
        <ArrowLeft className="w-4 h-4" /> Back to Exception Queue
      </Link>

      {/* Exception Banner */}
      <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <span className={`px-2.5 py-0.5 rounded text-xs font-bold uppercase tracking-wider ${
              detail.severity === 'critical' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
              detail.severity === 'high' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
              'bg-blue-500/10 text-blue-400 border border-blue-500/20'
            }`}>
              {detail.severity}
            </span>
            <span className="text-xs px-2.5 py-0.5 rounded bg-slate-800 text-slate-300 font-medium">
              Type: {detail.exception_type}
            </span>
            <span className="text-xs px-2.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 font-medium capitalize">
              Status: {detail.status.replace('_', ' ')}
            </span>
          </div>
          <h1 className="text-2xl font-black text-white mt-2">Dossier: {detail.id}</h1>
          <p className="text-xs text-slate-400 mt-1">{detail.description}</p>
        </div>

        <div className="text-right">
          <div className="text-xs text-slate-400">Financial Exposure</div>
          <div className="text-2xl font-black text-white font-mono">₹{detail.amount_involved?.toFixed(2) || '0.00'}</div>
          <div className="text-xs text-amber-400 font-mono font-semibold">Variance: ₹{detail.variance?.toFixed(2) || '0.00'}</div>
        </div>
      </div>

      {/* Two Column Layout: Evidence Graph & AI/Policy */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column: Evidence Graph */}
        <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-emerald-400" />
              Evidence Causality Graph
            </h3>
            <span className="text-xs text-slate-500">{detail.evidence_graph?.nodes?.length || 0} Entities Linked</span>
          </div>

          <p className="text-xs text-slate-400">
            Automated causality graph linking payment gateway events to general ledger records.
          </p>

          <div className="space-y-3">
            {detail.evidence_graph?.nodes?.map((node, i) => (
              <div key={node.id} className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs space-y-1">
                <div className="flex justify-between items-center">
                  <span className="font-bold text-white capitalize">{node.label}</span>
                  <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 uppercase font-mono">
                    {node.entity_type}
                  </span>
                </div>
                <div className="text-slate-400 font-mono text-[11px] truncate">ID: {node.id}</div>
                {node.data && (
                  <pre className="text-[10px] text-slate-500 bg-slate-900/50 p-2 rounded overflow-x-auto">
                    {JSON.stringify(node.data, null, 2)}
                  </pre>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Right Column: AI Analysis & Guardrails */}
        <div className="space-y-6">
          {/* AI Analysis Box */}
          <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <BrainCircuit className="w-5 h-5 text-indigo-400" />
                AI Root-Cause Investigation
              </h3>
              {detail.ai_analysis && (
                <span className="text-xs px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-mono font-bold">
                  {(detail.ai_analysis.confidence * 100).toFixed(1)}% Confidence
                </span>
              )}
            </div>

            {detail.ai_analysis ? (
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-400 block font-semibold">Classification:</span>
                  <span className="text-white font-medium">{detail.ai_analysis.classification}</span>
                </div>
                <div>
                  <span className="text-slate-400 block font-semibold">Audited Root Cause:</span>
                  <p className="text-slate-300 leading-relaxed mt-0.5">{detail.ai_analysis.explanation}</p>
                </div>
                <div>
                  <span className="text-slate-400 block font-semibold">Recommended Resolution:</span>
                  <span className="text-emerald-400 font-bold font-mono">{detail.ai_analysis.recommended_action}</span>
                </div>
                {detail.ai_analysis.supporting_evidence?.length > 0 && (
                  <div>
                    <span className="text-slate-400 block font-semibold">Citations:</span>
                    <div className="flex flex-wrap gap-1.5 mt-1">
                      {detail.ai_analysis.supporting_evidence.map((ev, i) => (
                        <span key={i} className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono text-[10px]">
                          {ev}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-500">No AI investigation has been run on this exception yet.</p>
            )}
          </div>

          {/* Policy Guardrails Box */}
          <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-white flex items-center gap-2">
                <ShieldCheck className="w-5 h-5 text-amber-400" />
                Deterministic Guardrails & Policy
              </h3>
              {detail.policy_result && (
                <span className={`text-xs px-2 py-0.5 rounded font-bold ${
                  detail.policy_result.can_auto_resolve 
                    ? 'bg-emerald-500/10 text-emerald-400' 
                    : 'bg-amber-500/10 text-amber-400'
                }`}>
                  {detail.policy_result.can_auto_resolve ? 'Auto-Resolve Permitted' : 'Human Review Mandated'}
                </span>
              )}
            </div>

            {detail.policy_result ? (
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-slate-400 block font-semibold">Policy Action:</span>
                  <span className="text-white font-mono font-bold">{detail.policy_result.action}</span>
                </div>
                <div>
                  <span className="text-slate-400 block font-semibold">Guardrail Assessment:</span>
                  <p className="text-slate-300 mt-0.5">{detail.policy_result.reason}</p>
                </div>
                {detail.policy_result.reviewer_role && (
                  <div>
                    <span className="text-slate-400 block font-semibold">Required Role:</span>
                    <span className="text-amber-400 font-medium">{detail.policy_result.reviewer_role}</span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-slate-500">Policy evaluation pending.</p>
            )}
          </div>

          {/* Human Controller Actions */}
          <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4">
            <h3 className="text-base font-bold text-white">Human Controller Actions</h3>
            <textarea
              value={actionNotes}
              onChange={(e) => setActionNotes(e.target.value)}
              placeholder="Enter audit notes or disposition rationale..."
              className="w-full bg-slate-950 border border-slate-800 text-xs text-slate-200 p-3 rounded-lg outline-none focus:border-emerald-500 h-20"
            />
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button
                onClick={() => handleAction('approve')}
                disabled={submitting}
                className="px-3 py-2 rounded bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-bold"
              >
                Approve
              </button>
              <button
                onClick={() => handleAction('reject')}
                disabled={submitting}
                className="px-3 py-2 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/30 text-xs font-bold"
              >
                Reject
              </button>
              <button
                onClick={() => handleAction('request-info')}
                disabled={submitting}
                className="px-3 py-2 rounded bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 border border-blue-500/30 text-xs font-bold"
              >
                Request Info
              </button>
              <button
                onClick={() => handleAction('false-positive')}
                disabled={submitting}
                className="px-3 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 text-xs font-bold"
              >
                False Positive
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Immutable Audit Trail */}
      <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-4">
        <h3 className="text-base font-bold text-white flex items-center gap-2">
          <Clock className="w-5 h-5 text-slate-400" />
          Immutable Audit Log Trail
        </h3>
        <div className="space-y-2">
          {auditLogs.map((log) => (
            <div key={log.id} className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs flex justify-between items-center">
              <div>
                <span className="font-semibold text-emerald-400 capitalize">{log.action.replace(/_/g, ' ')}</span>
                <span className="text-slate-400 ml-2">by {log.actor}</span>
              </div>
              <span className="text-[11px] text-slate-500 font-mono">{new Date(log.timestamp).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
