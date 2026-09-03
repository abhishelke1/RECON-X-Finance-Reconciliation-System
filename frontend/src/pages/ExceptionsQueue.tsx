import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { 
  AlertTriangle, CheckCircle2, XCircle, BrainCircuit, 
  HelpCircle, ShieldAlert, ArrowUpRight, Search, Filter 
} from 'lucide-react';
import api, { ExceptionItem } from '../api';

export default function ExceptionsQueue() {
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterSeverity, setFilterSeverity] = useState<string>('');
  const [investigatingId, setInvestigatingId] = useState<string | null>(null);

  useEffect(() => {
    loadExceptions();
  }, [filterStatus, filterSeverity]);

  const loadExceptions = async () => {
    setLoading(true);
    try {
      let query = '/exceptions?limit=100';
      if (filterStatus) query += `&status=${filterStatus}`;
      if (filterSeverity) query += `&severity=${filterSeverity}`;
      const res = await api.get(query);
      setExceptions(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleInvestigate = async (id: string) => {
    setInvestigatingId(id);
    try {
      const res = await api.post(`/exceptions/${id}/investigate`);
      alert(
        res.data.auto_resolved
          ? `Auto-Resolved! Action: ${res.data.policy_decision.action}`
          : `Routed to Human Review: ${res.data.policy_decision.reason}`
      );
      loadExceptions();
    } catch (e: any) {
      alert(`Investigation failed: ${e.response?.data?.detail || e.message}`);
    } finally {
      setInvestigatingId(null);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight">Exception Investigation & Review Queue</h1>
          <p className="text-sm text-slate-400 mt-1">
            Audit discrepant transaction positions, inspect AI root-cause hypotheses, and execute policy-governed dispositions.
          </p>
        </div>

        {/* Filter Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-300 rounded-lg px-3 py-2 outline-none"
          >
            <option value="">All Statuses</option>
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="auto_resolved">Auto Resolved</option>
            <option value="human_review">Human Review</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
          </select>

          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="bg-slate-800 border border-slate-700 text-xs text-slate-300 rounded-lg px-3 py-2 outline-none"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* Queue Table */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden shadow-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-semibold bg-slate-850/50">
                <th className="p-4">Severity</th>
                <th className="p-4">Type</th>
                <th className="p-4">Status</th>
                <th className="p-4">Exposure (INR)</th>
                <th className="p-4">Variance</th>
                <th className="p-4">Description</th>
                <th className="p-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {exceptions.map((exc) => (
                <tr key={exc.id} className="hover:bg-slate-850/40 transition-colors">
                  <td className="p-4">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider ${
                      exc.severity === 'critical' ? 'bg-rose-500/10 text-rose-400 border border-rose-500/20' :
                      exc.severity === 'high' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                      exc.severity === 'medium' ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20' :
                      'bg-slate-700/30 text-slate-400'
                    }`}>
                      {exc.severity}
                    </span>
                  </td>
                  <td className="p-4 font-semibold text-white">{exc.exception_type}</td>
                  <td className="p-4">
                    <span className={`px-2 py-0.5 rounded text-[11px] font-medium capitalize ${
                      exc.status === 'auto_resolved' ? 'bg-emerald-500/10 text-emerald-400' :
                      exc.status === 'approved' ? 'bg-indigo-500/10 text-indigo-400' :
                      exc.status === 'human_review' ? 'bg-amber-500/10 text-amber-400' : 'bg-slate-800 text-slate-400'
                    }`}>
                      {exc.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="p-4 font-mono font-medium text-white">₹{exc.amount_involved?.toFixed(2) || '0.00'}</td>
                  <td className="p-4 font-mono">
                    <span className={exc.variance && Math.abs(exc.variance) > 0.05 ? 'text-amber-400 font-bold' : 'text-slate-400'}>
                      ₹{exc.variance?.toFixed(2) || '0.00'}
                    </span>
                  </td>
                  <td className="p-4 text-slate-400 max-w-xs truncate" title={exc.description}>{exc.description}</td>
                  <td className="p-4 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <button
                        onClick={() => handleInvestigate(exc.id)}
                        disabled={investigatingId === exc.id || exc.status === 'auto_resolved'}
                        className="px-2.5 py-1.5 rounded text-xs bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 border border-indigo-500/30 font-medium transition-colors"
                      >
                        <BrainCircuit className="w-3.5 h-3.5 inline mr-1" />
                        {investigatingId === exc.id ? 'Investigating...' : 'AI Investigate'}
                      </button>
                      <Link
                        to={`/exceptions/${exc.id}`}
                        className="px-2.5 py-1.5 rounded text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium transition-colors"
                      >
                        Dossier
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
              {exceptions.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-500">
                    No exceptions found matching current filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
