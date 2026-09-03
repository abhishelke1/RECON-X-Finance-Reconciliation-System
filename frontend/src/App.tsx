import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, Database, RefreshCw, AlertCircle, 
  ShieldCheck, BarChart3, Play, FileText, Layers, ExternalLink 
} from 'lucide-react';

import Overview from './pages/Overview';
import Ingestion from './pages/Ingestion';
import ReconciliationRuns from './pages/ReconciliationRuns';
import ExceptionsQueue from './pages/ExceptionsQueue';
import ExceptionDossier from './pages/ExceptionDossier';
import PolicyConfig from './pages/PolicyConfig';
import EvaluationBenchmarkPage from './pages/EvaluationBenchmark';
import DemoTour from './pages/DemoTour';

const App: React.FC = () => {
  const location = useLocation();

  const navItems = [
    { path: '/', label: 'Overview', icon: LayoutDashboard },
    { path: '/ingestion', label: 'Data Ingestion', icon: Database },
    { path: '/runs', label: 'Reconciliation Cycles', icon: RefreshCw },
    { path: '/exceptions', label: 'Exceptions Queue', icon: AlertCircle },
    { path: '/policy', label: 'Policy & Guardrails', icon: ShieldCheck },
    { path: '/evaluation', label: 'Evaluation Scoreboard', icon: BarChart3 },
    { path: '/demo', label: '8-Scenario Demo Tour', icon: Play, highlight: true },
  ];

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200 overflow-hidden font-sans">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col shrink-0">
        {/* Brand Header */}
        <div className="p-6 border-b border-slate-800">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-xl font-black tracking-wider text-white">RECON-X</h1>
              <p className="text-[10px] text-emerald-400 font-bold uppercase tracking-widest">Autonomous Controller</p>
            </div>
          </div>
          <div className="mt-3 px-2 py-1 rounded bg-slate-950/60 border border-slate-800 text-[10px] text-slate-400">
            Track 04: AI Finance Controller
          </div>
        </div>
        
        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1.5 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path || (item.path !== '/' && location.pathname.startsWith(item.path));
            return (
              <Link
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-sm'
                    : item.highlight
                    ? 'text-emerald-400 hover:bg-emerald-500/10'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                <Icon className={`w-4 h-4 ${isActive ? 'text-emerald-400' : 'text-slate-400'}`} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Footer Meta */}
        <div className="p-4 border-t border-slate-800 text-[11px] text-slate-500 space-y-1 bg-slate-950/40">
          <div className="flex justify-between">
            <span>Currency:</span>
            <span className="font-mono text-slate-300">INR (₹)</span>
          </div>
          <div className="flex justify-between">
            <span>Precision:</span>
            <span className="font-mono text-slate-300">Decimal (4 DP)</span>
          </div>
          <div className="flex justify-between">
            <span>Razorpay Mode:</span>
            <span className="text-emerald-400 font-medium">Interchangeable</span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto bg-slate-950">
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/ingestion" element={<Ingestion />} />
          <Route path="/runs" element={<ReconciliationRuns />} />
          <Route path="/exceptions" element={<ExceptionsQueue />} />
          <Route path="/exceptions/:id" element={<ExceptionDossier />} />
          <Route path="/policy" element={<PolicyConfig />} />
          <Route path="/evaluation" element={<EvaluationBenchmarkPage />} />
          <Route path="/demo" element={<DemoTour />} />
        </Routes>
      </main>
    </div>
  );
};

export default App;
