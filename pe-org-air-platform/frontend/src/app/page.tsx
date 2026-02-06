"use client";

import { useEffect, useState } from "react";
import {
  Plus,
  Search,
  RefreshCw,
  TrendingUp,
  Building2,
  Activity,
  ArrowUpRight,
  Loader2,
  Clock,
  AlertCircle,
  Settings,
} from "lucide-react";
import Link from "next/link";

// Types based on backend models
interface Stats {
  companies: number;
  documents: number;
  signals: number;
  errors: number;
  status: string;
  last_run: string | null;
}

interface Company {
  id: string;
  name: string;
  ticker: string;
  industry_id: string;
  position_factor: number;
}

export default function Dashboard() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [backfilling, setBackfilling] = useState(false);

  const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    async function fetchData() {
      try {
        const [statsRes, companiesRes] = await Promise.all([
          fetch(`${API_BASE}/api/v1/evidence/stats`),
          fetch(`${API_BASE}/api/v1/companies/`)
        ]);

        if (statsRes.ok) setStats(await statsRes.json());
        if (companiesRes.ok) {
          const data = await companiesRes.json();
          setCompanies(data.items || []);
        }
      } catch (err) {
        console.error("Failed to fetch data:", err);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
    const interval = setInterval(fetchData, 10000); // Poll every 10s
    return () => clearInterval(interval);
  }, [API_BASE]);

  const handleBackfill = async () => {
    setBackfilling(true);
    try {
      await fetch(`${API_BASE}/api/v1/evidence/backfill`, { method: "POST" });
      // We don't wait for it to finish as it's a 202
    } catch (err) {
      console.error("Backfill failed:", err);
    } finally {
      setTimeout(() => setBackfilling(false), 2000);
    }
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Intelligence Dashboard</h2>
          <p className="text-slate-400 mt-1">Real-time AI Maturity signals and SEC evidence monitoring.</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleBackfill}
            disabled={backfilling || stats?.status === "running"}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800/50 text-white px-5 py-2.5 rounded-xl transition-all font-medium"
          >
            {stats?.status === "running" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            {stats?.status === "running" ? "Backfilling..." : "Run Global Backfill"}
          </button>
          <Link
            href="/manage"
            className="flex items-center gap-2 bg-[#18181b] border border-slate-800 hover:bg-zinc-800 text-white px-5 py-2.5 rounded-xl transition-all font-medium"
          >
            <Settings className="h-4 w-4 text-blue-400" />
            Management
          </Link>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          label="Tracked Companies"
          value={companies.length.toString()}
          icon={<Building2 className="text-blue-500" size={20} />}
          trend="+2 recent"
        />
        <StatCard
          label="Signals Collected"
          value={stats?.signals.toLocaleString() || "0"}
          icon={<TrendingUp className="text-purple-500" size={20} />}
          trend="Real-time"
        />
        <StatCard
          label="SEC Filings"
          value={stats?.documents.toString() || "0"}
          icon={<Activity className="text-green-500" size={20} />}
          trend="10-K, 10-Q detected"
        />
        <StatCard
          label="System Health"
          value={stats?.status === "running" ? "Backfilling" : "Active"}
          icon={<Clock className="text-orange-500" size={20} />}
          status={stats?.status}
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-8">
        <div className="xl:col-span-2 space-y-6">
          <div className="bg-[#0c0c0e] border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
            <div className="p-6 border-b border-slate-800 flex justify-between items-center">
              <h3 className="font-semibold text-lg flex items-center gap-2">
                <Activity size={18} className="text-blue-400" />
                Target Intelligence
              </h3>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                <input
                  type="text"
                  placeholder="Filter targets..."
                  className="bg-[#18181b] border border-slate-800 rounded-full py-2 pl-10 pr-4 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500/50 w-64"
                />
              </div>
            </div>

            <div className="divide-y divide-slate-800">
              {companies.map((company) => (
                <div key={company.id} className="p-6 flex items-center justify-between hover:bg-white/[0.02] transition-colors cursor-pointer group">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-blue-600/10 rounded-2xl flex items-center justify-center border border-blue-500/20 group-hover:border-blue-500/50 transition-all">
                      <span className="font-bold text-blue-400">{company.ticker}</span>
                    </div>
                    <div>
                      <h4 className="font-semibold text-lg">{company.name}</h4>
                      <p className="text-sm text-slate-500">ID: {company.id.substring(0, 8)}...</p>
                    </div>
                  </div>

                  <div className="flex gap-4 items-center">
                    <div className="text-right mr-4">
                      <div className="text-sm text-slate-500">Position Factor</div>
                      <div className="font-medium">{(company.position_factor * 100).toFixed(0)}%</div>
                    </div>
                    <div className="h-8 w-[1px] bg-slate-800 mr-2" />
                    <Link
                      href={`/audit/${company.id}`}
                      className="flex items-center gap-1.5 text-blue-400 hover:text-blue-300 text-sm font-medium transition-all px-3 py-1.5 rounded-lg hover:bg-blue-600/10"
                    >
                      View Audit <ArrowUpRight size={16} />
                    </Link>
                  </div>
                </div>
              ))}

              {companies.length === 0 && (
                <div className="p-12 text-center text-slate-500">
                  <AlertCircle className="mx-auto h-12 w-12 opacity-20 mb-4" />
                  <p>No companies found. Run a backfill or add targets manually.</p>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Sidebar / Activity */}
        <div className="space-y-6">
          <div className="bg-[#0c0c0e] border border-slate-800 rounded-3xl p-6 shadow-xl h-fit">
            <h3 className="font-semibold text-lg mb-6 flex items-center gap-2">
              <Activity size={18} className="text-purple-400" />
              Recent Collection
            </h3>
            <div className="space-y-6">
              <ActivityItem
                title="Job Signals Collected"
                detail="Caterpillar Inc. (CAT)"
                time="2m ago"
                type="success"
              />
              <ActivityItem
                title="8-K Filing Detected"
                detail="John Deere (DE)"
                time="15m ago"
                type="info"
              />
              <ActivityItem
                title="Patent Analysis"
                detail="UnitedHealth (UNH)"
                time="1h ago"
                type="success"
              />
              <ActivityItem
                title="Connection Error"
                detail="SEC EDGAR Timeout"
                time="2h ago"
                type="error"
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, trend, status }: { label: string; value: string; icon: React.ReactNode; trend?: string; status?: string }) {
  return (
    <div className="bg-[#0c0c0e] border border-slate-800 rounded-2xl p-6 shadow-xl relative overflow-hidden group">
      <div className="absolute top-0 right-0 p-3 opacity-20 group-hover:scale-110 transition-transform duration-300">
        {icon}
      </div>
      <p className="text-slate-400 text-sm font-medium">{label}</p>
      <div className="flex items-end gap-2 mt-2">
        <h3 className="text-3xl font-bold">{value}</h3>
      </div>
      {status === "running" ? (
        <div className="mt-3 flex items-center gap-2 text-orange-400 text-sm font-medium animate-pulse">
          <Loader2 size={12} className="animate-spin" />
          Processing Pipeline...
        </div>
      ) : trend ? (
        <p className="text-slate-500 text-xs mt-3 flex items-center gap-1">
          {trend}
        </p>
      ) : null}
    </div>
  );
}

function ActivityItem({ title, detail, time, type }: { title: string; detail: string; time: string; type: 'success' | 'error' | 'info' }) {
  const colors = {
    success: 'bg-green-500',
    error: 'bg-red-500',
    info: 'bg-blue-500'
  };

  return (
    <div className="flex gap-4">
      <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${colors[type]}`} />
      <div className="flex-1 border-b border-slate-800/50 pb-4">
        <div className="flex justify-between items-start">
          <h5 className="font-medium text-sm">{title}</h5>
          <span className="text-[10px] text-slate-600 font-medium uppercase tracking-wider">{time}</span>
        </div>
        <p className="text-xs text-slate-500 mt-0.5">{detail}</p>
      </div>
    </div>
  );
}
