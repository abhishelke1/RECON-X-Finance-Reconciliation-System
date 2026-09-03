import React, { useEffect, useState } from 'react';
import { 
  Play, RefreshCw, CheckCircle2, AlertTriangle, Layers, 
  Clock, ArrowRight, Eye, ShieldCheck, Filter 
} from 'lucide-react';
import api, { ReconciliationRun, ReconciliationMatch } from '../api';

export default function ReconciliationRuns() {
  const [runs, setRuns] = useState<ReconciliationRun[]>([]);
  const [merchants, setMerchants] = useState<any[]>([]);
  const [selectedMerchantId, setSelectedMerchantId] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [selectedRun, setSelectedRun] = useState<ReconciliationRun | null>(null);
  const [matches, setMatches] = useState<ReconciliationMatch[]>([]);
  const [matchesLoading, setMatchesLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const mRes = await api.get('/merchants');
      setMerchants(mRes.data);
      if (mRes.data.length > 0) {
        const mId = mRes.data[0].id;
        setSelectedMerchantId(mId);
        const runsRes = await api.get(`/reconciliation?merchant_id=${mId}`);
        setRuns(runsRes.data);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerRun = async () => {
    if (!selectedMerchantId) return;
    setTriggering(true);
    try {
      const res = await api.post('/reconciliation/run', {
        merchant_id: selectedMerchantId,
        parameters: { trigger: 'manual_ui_console' },
      });
      setRuns([res.data, ...runs]);
      viewRunMatches(res.data);
    } catch (e: any) {
      alert(`Reconciliation error: ${e.response?.data?.detail || e.message}`);
    } finally {
      setTriggering(false);
    }
  };

  const viewRunMatches = async (run: ReconciliationRun) => {
    setSelectedRun(run);
    setMatchesLoading(true);
    try {
      const res = await api.get(`/reconciliation/${run.id}/matches`);
      setMatches(res.data);
    } catch (e) {
      console.error(e);
    } finally {
      setMatchesLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-black text-white tracking-tight">Reconciliation Cycles</h1>
          <p className="text-sm text-slate-400 mt-1">
            Execute 4-tier deterministic matching (L1 to L4), balance variance calculation, and exception generation.
          </p>
        </div>

        <button
          onClick={handleTriggerRun}
          disabled={triggering || !selectedMerchantId}
          className="flex items-center gap-2 px-5 py-2.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-800 text-slate-950 font-bold transition-all shadow-lg shadow-emerald-500/20"
        >
          <Play className="w-4 h-4 fill-slate-950" />
          {triggering ? 'Executing Pipeline...' : 'Run Reconciliation Cycle'}
        </button>
      </div>

      {/* Runs Table */}
      <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden shadow-xl">
        <div className="p-4 border-b border-slate-800 flex justify-between items-center bg-slate-850/50">
          <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">Historical Runs</span>
          <span className="text-xs text-slate-500">{runs.length} Runs Recorded</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-semibold bg-slate-900/50">
                <th className="p-4">Run ID</th>
                <th className="p-4">Status</th>
                <th className="p-4">Total Records</th>
                <th className="p-4">Matched</th>
                <th className="p-4">Exceptions</th>
                <th className="p-4">Duration</th>
                <th className="p-4">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800 text-slate-300">
              {runs.map((run) => (
                <tr key={run.id} className="hover:bg-slate-850/50 transition-colors">
                  <td className="p-4 font-mono text-slate-400">{run.id.slice(0, 8)}...</td>
                  <td className="p-4">
                    <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 capitalize">
                      {run.status}
                    </span>
                  </td>
                  <td className="p-4 font-semibold text-white">{run.total_records}</td>
                  <td className="p-4 text-emerald-400 font-semibold">{run.matched_records}</td>
                  <td className="p-4 text-amber-400 font-semibold">{run.exceptions_found}</td>
                  <td className="p-4 text-slate-400">{run.processing_time_ms ? `${run.processing_time_ms} ms` : '-'}</td>
                  <td className="p-4">
                    <button
                      onClick={() => viewRunMatches(run)}
                      className="flex items-center gap-1 text-xs text-slate-300 hover:text-white px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      View Matches
                    </button>
                  </td>
                </tr>
              ))}
              {runs.length === 0 && (
                <tr>
                  <td colSpan={7} className="p-8 text-center text-slate-500">
                    No reconciliation runs yet. Click "Run Reconciliation Cycle" to trigger the first run.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Matches Inspection Panel */}
      {selectedRun && (
        <div className="bg-slate-900 rounded-xl border border-slate-800 p-6 space-y-4 shadow-xl">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="text-lg font-bold text-white">Matches & Reconciliation Positions for Run {selectedRun.id.slice(0, 8)}</h3>
              <p className="text-xs text-slate-400">Inspecting 4-tier match levels and classified balance states</p>
            </div>
            <button onClick={() => setSelectedRun(null)} className="text-xs text-slate-500 hover:text-white">Close</button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-semibold bg-slate-850/50">
                  <th className="p-3">Match Status</th>
                  <th className="p-3">Reconciliation Status</th>
                  <th className="p-3">Confidence</th>
                  <th className="p-3">Expected Amount</th>
                  <th className="p-3">Actual Amount</th>
                  <th className="p-3">Variance</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800 text-slate-300 font-mono">
                {matches.slice(0, 15).map((m) => (
                  <tr key={m.id} className="hover:bg-slate-850/30">
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded text-[11px] font-sans font-bold ${
                        m.match_status === 'EXACT' ? 'bg-emerald-500/10 text-emerald-400' :
                        m.match_status === 'HIGH_CONFIDENCE' ? 'bg-blue-500/10 text-blue-400' :
                        m.match_status === 'POSSIBLE' ? 'bg-amber-500/10 text-amber-400' : 'bg-rose-500/10 text-rose-400'
                      }`}>
                        {m.match_status}
                      </span>
                    </td>
                    <td className="p-3 font-sans font-medium text-slate-200">{m.recon_status}</td>
                    <td className="p-3">{(m.match_confidence * 100).toFixed(1)}%</td>
                    <td className="p-3 text-slate-300">₹{m.expected_amount?.toFixed(2) || '0.00'}</td>
                    <td className="p-3 text-slate-300">₹{m.actual_amount?.toFixed(2) || '0.00'}</td>
                    <td className="p-3">
                      <span className={m.variance && Math.abs(m.variance) > 0.05 ? 'text-amber-400 font-bold' : 'text-emerald-400'}>
                        ₹{m.variance?.toFixed(2) || '0.00'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
