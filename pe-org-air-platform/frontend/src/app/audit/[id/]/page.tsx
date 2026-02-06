"use client";

import { useEffect, useState, use } from "react";
import {
    ArrowLeft,
    TrendingUp,
    Target as TargetIcon,
    Code,
    Table as TableIcon,
    Activity,
    Cpu,
    Brain,
    Globe,
    Briefcase,
    PieChart,
    Calendar,
    ExternalLink,
    ChevronDown,
    Loader2
} from "lucide-react";
import Link from "next/link";

interface Signal {
    id: string;
    company_id: string;
    category: string;
    source: string;
    signal_date: string;
    normalized_score: number;
    confidence: number;
    raw_value: string;
    metadata: any;
}

interface Company {
    id: string;
    name: string;
    ticker: string;
}

export default function AuditPage({ params }: { params: Promise<{ id: string }> }) {
    const { id: companyId } = use(params);
    const [signals, setSignals] = useState<Signal[]>([]);
    const [company, setCompany] = useState<Company | null>(null);
    const [loading, setLoading] = useState(true);
    const [viewMode, setViewMode] = useState<'table' | 'json'>('table');

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    useEffect(() => {
        async function fetchData() {
            try {
                const [compRes, sigRes] = await Promise.all([
                    fetch(`${API_BASE}/api/v1/companies/${companyId}`),
                    fetch(`${API_BASE}/api/v1/companies/${companyId}/signals/all`) // Note: 'all' needs to be handled by backend or mapped
                ]);

                if (compRes.ok) setCompany(await compRes.json());

                // If 'all' endpoint doesn't exist, we might need to fetch multiple times or use the list endpoint with ticker
                // Let's fallback to search since we have the ticker if list is easier
                const signalsAllRes = await fetch(`${API_BASE}/api/v1/signals/?ticker=${(await compRes.clone().json()).ticker}`);
                if (signalsAllRes.ok) setSignals(await signalsAllRes.json());

            } catch (err) {
                console.error("Failed to fetch audit data:", err);
            } finally {
                setLoading(false);
            }
        }

        if (companyId) fetchData();
    }, [companyId, API_BASE]);

    if (loading) {
        return (
            <div className="flex h-screen items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            </div>
        );
    }

    return (
        <div className="p-8 space-y-8 max-w-7xl mx-auto">
            {/* Navigation */}
            <Link href="/" className="flex items-center gap-2 text-slate-400 hover:text-white transition-all text-sm group w-fit">
                <ArrowLeft size={16} className="group-hover:-translate-x-1 transition-transform" />
                Back to Dashboard
            </Link>

            <div className="flex justify-between items-end">
                <div className="flex items-center gap-6">
                    <div className="w-20 h-20 bg-blue-600/10 rounded-3xl flex items-center justify-center border border-blue-500/30">
                        <span className="text-3xl font-black text-blue-400">{company?.ticker}</span>
                    </div>
                    <div>
                        <h1 className="text-4xl font-extrabold tracking-tight">{company?.name}</h1>
                        <div className="flex gap-4 mt-2 text-slate-500 text-sm">
                            <span className="flex items-center gap-1.5"><Calendar size={14} /> Last Audit: Today</span>
                            <span className="flex items-center gap-1.5 truncate max-w-[200px]"><TargetIcon size={14} /> ID: {companyId}</span>
                        </div>
                    </div>
                </div>

                <div className="flex gap-2 p-1 bg-[#18181b] rounded-xl border border-slate-800">
                    <button
                        onClick={() => setViewMode('table')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all ${viewMode === 'table' ? 'bg-zinc-800 text-white' : 'text-slate-500'}`}
                    >
                        <TableIcon size={16} /> Analysis View
                    </button>
                    <button
                        onClick={() => setViewMode('json')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-all ${viewMode === 'json' ? 'bg-zinc-800 text-white' : 'text-slate-500'}`}
                    >
                        <Code size={16} /> raw signal data
                    </button>
                </div>
            </div>

            {viewMode === 'table' ? (
                <div className="grid grid-cols-1 gap-8">
                    {/* Summary Stats */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                        <AuditMetric
                            label="Tech Momentum"
                            value={(signals.reduce((acc, s) => acc + s.normalized_score, 0) / (signals.length || 1) * 10).toFixed(1)}
                            icon={<Cpu className="text-blue-500" />}
                            subtext="Composite score across all clusters"
                        />
                        <AuditMetric
                            label="Market Confidence"
                            value={(signals.reduce((acc, s) => acc + s.confidence, 0) / (signals.length || 1) * 100).toFixed(0) + "%"}
                            icon={<Brain className="text-purple-500" />}
                            subtext="Signal clarity and source reliability"
                        />
                        <AuditMetric
                            label="Data Points"
                            value={signals.length.toString()}
                            icon={<Activity className="text-green-500" />}
                            subtext="Unique intelligence markers indexed"
                        />
                    </div>

                    {/* Signals Analysis */}
                    <div className="bg-[#0c0c0e] border border-slate-800 rounded-3xl overflow-hidden shadow-2xl">
                        <div className="p-6 border-b border-slate-800 flex justify-between items-center bg-white/[0.01]">
                            <h3 className="font-bold flex items-center gap-2">
                                <TrendingUp size={18} className="text-blue-400" />
                                Signal Intelligence Cluster
                            </h3>
                        </div>

                        <div className="divide-y divide-slate-800">
                            {signals.map((signal) => (
                                <div key={signal.id} className="p-6 hover:bg-white/[0.01] transition-all">
                                    <div className="flex justify-between items-start mb-4">
                                        <div className="space-y-1">
                                            <div className="flex items-center gap-2 mb-1">
                                                <CategoryBadge category={signal.category} />
                                                <span className="text-xs font-mono text-slate-500">SOURCE: {signal.source}</span>
                                            </div>
                                            <h4 className="text-lg font-semibold">{signal.raw_value || "Cluster Reading Detected"}</h4>
                                            <p className="text-sm text-slate-400 max-w-2xl">{JSON.stringify(signal.metadata).substring(0, 150)}...</p>
                                        </div>
                                        <div className="text-right flex flex-col items-end gap-2">
                                            <div className="bg-[#18181b] border border-slate-800 h-10 w-24 rounded-lg flex flex-col items-center justify-center">
                                                <span className="text-xs text-slate-500 leading-none mb-1 uppercase font-bold tracking-widest text-[8px]">SCORE</span>
                                                <span className="font-mono text-blue-400 leading-none">{signal.normalized_score.toFixed(1)}</span>
                                            </div>
                                            <span className="text-[10px] text-slate-600 font-mono uppercase tracking-widest">
                                                {new Date(signal.signal_date).toLocaleDateString()}
                                            </span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                            {signals.length === 0 && (
                                <div className="p-20 text-center text-slate-500 italic">
                                    No signals indexed for this cluster. Run a collection to populate data.
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            ) : (
                <div className="bg-[#0c0c0e] border border-slate-800 rounded-3xl p-6 shadow-2xl">
                    <div className="flex justify-between items-center mb-4">
                        <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest">Raw Response Payload</h3>
                        <button className="text-xs text-blue-400 hover:text-blue-300 font-medium px-3 py-1 bg-blue-500/10 rounded-full border border-blue-500/20">Copy JSON</button>
                    </div>
                    <pre className="text-sm font-mono text-blue-300 overflow-auto max-h-[800px] p-6 bg-black/40 rounded-2xl scrollbar-thin border border-slate-800">
                        {JSON.stringify({ company, signals }, null, 2)}
                    </pre>
                </div>
            )}
        </div>
    );
}

function CategoryBadge({ category }: { category: string }) {
    const styles: any = {
        technology_hiring: "bg-blue-500/10 text-blue-400 border-blue-500/20 icon:Briefcase",
        innovation_activity: "bg-purple-500/10 text-purple-400 border-purple-500/20 icon:Cpu",
        digital_presence: "bg-green-500/10 text-green-400 border-green-500/20 icon:Globe",
        leadership_signals: "bg-orange-500/10 text-orange-400 border-orange-500/20 icon:PieChart"
    };

    const style = styles[category] || "bg-slate-500/10 text-slate-400 border-slate-500/20 icon:Activity";
    const [colorClass, iconName] = style.split(' icon:');

    return (
        <span className={`${colorClass} border px-2.5 py-1 rounded-full text-xs font-bold uppercase tracking-tight flex items-center gap-1.5`}>
            {category.replace('_', ' ')}
        </span>
    );
}

function AuditMetric({ label, value, icon, subtext }: { label: string; value: string; icon: React.ReactNode; subtext: string }) {
    return (
        <div className="bg-[#0c0c0e] border border-slate-800 rounded-3xl p-6 shadow-xl relative group">
            <div className="absolute top-4 right-4 opacity-30 group-hover:scale-125 transition-transform duration-500">{icon}</div>
            <p className="text-slate-500 text-xs font-bold uppercase tracking-widest">{label}</p>
            <h3 className="text-4xl font-black mt-2 tracking-tighter">{value}</h3>
            <p className="text-slate-600 text-[10px] mt-4 font-medium uppercase">{subtext}</p>
        </div>
    );
}
