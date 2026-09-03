import React, { useEffect, useState } from 'react';
import { 
  Database, RefreshCw, Upload, CheckCircle2, AlertCircle, 
  FileText, Server, ArrowRight, ShieldAlert 
} from 'lucide-react';
import api from '../api';

export default function Ingestion() {
  const [merchants, setMerchants] = useState<any[]>([]);
  const [selectedMerchantId, setSelectedMerchantId] = useState<string>('');
  const [syncing, setSyncing] = useState(false);
  const [syncSummary, setSyncSummary] = useState<any>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    loadMerchants();
  }, []);

  const loadMerchants = async () => {
    try {
      const res = await api.get('/merchants');
      setMerchants(res.data);
      if (res.data.length > 0) {
        setSelectedMerchantId(res.data[0].id);
      } else {
        // Create demo merchant if none exists
        const createRes = await api.post('/merchants', {
          name: 'Demo Retail Enterprise',
          razorpay_account_id: 'acc_demo_rzp_01',
          business_type: 'ecommerce',
        });
        setMerchants([createRes.data]);
        setSelectedMerchantId(createRes.data.id);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleRazorpaySync = async () => {
    if (!selectedMerchantId) return;
    setSyncing(true);
    setMessage(null);
    try {
      const res = await api.post(`/import/razorpay/sync?merchant_id=${selectedMerchantId}`);
      setSyncSummary(res.data.summary);
      setMessage('Razorpay data synchronized successfully (mock mode verified).');
    } catch (e: any) {
      setMessage(`Sync error: ${e.response?.data?.detail || e.message}`);
    } finally {
      setSyncing(false);
    }
  };

  const handleCsvUpload = async (endpoint: string, file: File) => {
    if (!selectedMerchantId) return;
    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post(`${endpoint}?merchant_id=${selectedMerchantId}`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setMessage(`Import complete: ${res.data.records_accepted} accepted, ${res.data.duplicates} duplicates, ${res.data.records_rejected} rejected.`);
    } catch (e: any) {
      setMessage(`Upload error: ${e.response?.data?.detail || e.message}`);
    }
  };

  return (
    <div className="p-8 max-w-6xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-black text-white tracking-tight">Data Ingestion & Normalization</h1>
        <p className="text-sm text-slate-400 mt-1">
          Ingest multi-source financial feeds across Razorpay API (Sandbox/Mock), bank settlements, and ERP general ledger files.
        </p>
      </div>

      {/* Merchant Selector */}
      <div className="bg-slate-900 p-5 rounded-xl border border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Database className="w-5 h-5 text-emerald-400" />
          <div>
            <div className="text-xs text-slate-400 font-semibold uppercase tracking-wider">Active Merchant Entity</div>
            <div className="text-sm font-bold text-white">
              {merchants.find(m => m.id === selectedMerchantId)?.name || 'Loading merchant...'}
            </div>
          </div>
        </div>
        <select
          value={selectedMerchantId}
          onChange={(e) => setSelectedMerchantId(e.target.value)}
          className="bg-slate-800 border border-slate-700 text-sm text-slate-200 rounded-lg px-3 py-2 outline-none focus:border-emerald-500"
        >
          {merchants.map((m) => (
            <option key={m.id} value={m.id}>{m.name} ({m.business_type})</option>
          ))}
        </select>
      </div>

      {/* Sync Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Razorpay Ingestion */}
        <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-400">
                <Server className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-white">Razorpay API Gateway</h3>
                <p className="text-xs text-slate-400">Sync payments, orders, settlements, refunds, disputes</p>
              </div>
            </div>
            <span className="text-xs px-2.5 py-1 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
              Interchangeable Mock/Live
            </span>
          </div>

          <p className="text-xs text-slate-400 leading-relaxed">
            Ingests raw gateway objects with deterministic conversion of <strong>paise amounts to INR Decimal</strong> (divide by 100).
            Preserves immutable original payloads in <code className="text-slate-300">raw_data</code> for full compliance.
          </p>

          <button
            onClick={handleRazorpaySync}
            disabled={syncing}
            className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 disabled:bg-slate-800 text-slate-950 font-bold transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? 'Synchronizing Feeds...' : 'Sync Gateway Feeds'}
          </button>

          {syncSummary && (
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800 space-y-2 text-xs">
              <div className="text-slate-300 font-semibold">Synchronization Summary:</div>
              <div className="grid grid-cols-2 gap-2 text-slate-400">
                <div>Payments Synced: <span className="text-emerald-400 font-bold">{syncSummary.payments?.synced || 0}</span></div>
                <div>Orders Synced: <span className="text-emerald-400 font-bold">{syncSummary.orders?.synced || 0}</span></div>
                <div>Settlements Synced: <span className="text-emerald-400 font-bold">{syncSummary.settlements?.synced || 0}</span></div>
                <div>Refunds Synced: <span className="text-emerald-400 font-bold">{syncSummary.refunds?.synced || 0}</span></div>
              </div>
            </div>
          )}
        </div>

        {/* CSV File Uploads */}
        <div className="bg-slate-900 p-6 rounded-xl border border-slate-800 space-y-5">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">ERP & Ledger CSV Importer</h3>
              <p className="text-xs text-slate-400">Upload merchant accounting exports (Tally, QuickBooks, SAP)</p>
            </div>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex justify-between items-center">
              <div>
                <span className="font-semibold text-white block">Upload Payments CSV</span>
                <span className="text-slate-400">Columns: source_id, amount, currency, status, timestamp</span>
              </div>
              <label className="cursor-pointer px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium">
                Choose CSV
                <input
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && handleCsvUpload('/import/payments', e.target.files[0])}
                />
              </label>
            </div>

            <div className="p-3 bg-slate-950 rounded-lg border border-slate-800 flex justify-between items-center">
              <div>
                <span className="font-semibold text-white block">Upload General Ledger CSV</span>
                <span className="text-slate-400">Columns: source_id, amount, type, reference_id, timestamp</span>
              </div>
              <label className="cursor-pointer px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 font-medium">
                Choose CSV
                <input
                  type="file"
                  accept=".csv"
                  className="hidden"
                  onChange={(e) => e.target.files?.[0] && handleCsvUpload('/import/ledger', e.target.files[0])}
                />
              </label>
            </div>
          </div>

          {message && (
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-medium">
              {message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
