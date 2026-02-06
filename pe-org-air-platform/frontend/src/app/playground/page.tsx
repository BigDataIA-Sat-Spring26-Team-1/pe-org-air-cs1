"use client";

import { useState } from "react";
import {
    Play,
    Database,
    Globe,
    Lock,
    Terminal,
    Code,
    Table as TableIcon,
    ChevronRight,
    Loader2,
    Trash2,
    Plus
} from "lucide-react";

interface Endpoint {
    name: string;
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
    path: string;
    description: string;
}

const ENDPOINTS: Endpoint[] = [
    { name: "List Companies", method: 'GET', path: '/api/v1/companies/', description: "Get tracked targets" },
    { name: "List Industries", method: 'GET', path: '/api/v1/industries/', description: "Get industry risk factors" },
    { name: "Get Signal Summary", method: 'GET', path: '/api/v1/signals/summary?ticker=CAT', description: "Real-time summary" },
    { name: "List SEC Docs", method: 'GET', path: '/api/v1/documents?limit=5', description: "Indexed filings" },
    { name: "Health Check", method: 'GET', path: '/health', description: "System status" }
];

export default function Playground() {
    const [selectedEndpoint, setSelectedEndpoint] = useState<Endpoint>(ENDPOINTS[0]);
    const [customPath, setCustomPath] = useState(ENDPOINTS[0].path);
    const [response, setResponse] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [viewMode, setViewMode] = useState<'json' | 'table'>('json');

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    const handleRun = async () => {
        setLoading(true);
        try {
            const res = await fetch(`${API_BASE}${customPath}`);
            const data = await res.json();
            setResponse(data);
        } catch (err) {
            setResponse({ error: "Request failed", details: err });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-8 space-y-8 max-w-6xl">
            <div>
                <h2 className="text-3xl font-bold tracking-tight">API Playground</h2>
                <p className="text-slate-400 mt-1">Directly invoke and inspect the PE OrgAIR unified API.</p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Endpoint Selector */}
                <div className="space-y-4">
                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest px-2">Common Endpoints</h3>
                    <div className="space-y-2">
                        {ENDPOINTS.map((ep) => (
                            <button
                                key={ep.name}
                                onClick={() => {
                                    setSelectedEndpoint(ep);
                                    setCustomPath(ep.path);
                                }}
                                className={`w-full text-left p-4 rounded-2xl border transition-all ${selectedEndpoint.name === ep.name
                                        ? "bg-blue-600/10 border-blue-500/30 text-blue-400"
                                        : "bg-[#0c0c0e] border-slate-800 text-slate-400 hover:border-slate-700 hover:bg-white/[0.02]"
                                    }`}
                            >
                                <div className="flex items-center justify-between mb-1">
                                    <span className={`text-[10px] font-black px-1.5 py-0.5 rounded ${ep.method === 'GET' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                                        }`}>{ep.method}</span>
                                    <ChevronRight size={14} className={selectedEndpoint.name === ep.name ? "opacity-100" : "opacity-0"} />
                                </div>
                                <div className="font-bold text-sm truncate">{ep.name}</div>
                                <div className="text-[10px] opacity-60 mt-1 truncate">{ep.path}</div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Execution Engine */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-[#0c0c0e] border border-slate-800 rounded-3xl p-6 shadow-xl space-y-6">
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-slate-400">Request Path</label>
                            <div className="flex gap-3">
                                <div className="flex-1 relative group">
                                    <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-600 font-mono text-xs">GET</div>
                                    <input
                                        type="text"
                                        value={customPath}
                                        onChange={(e) => setCustomPath(e.target.value)}
                                        className="w-full bg-[#18181b] border border-slate-800 rounded-xl py-3 pl-14 pr-4 text-sm font-mono text-blue-300 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                                    />
                                </div>
                                <button
                                    onClick={handleRun}
                                    disabled={loading}
                                    className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white px-6 py-3 rounded-xl transition-all font-bold flex items-center gap-2"
                                >
                                    {loading ? <Loader2 size={18} className="animate-spin" /> : <Play size={18} />}
                                    EXECUTE
                                </button>
                            </div>
                        </div>

                        {response && (
                            <div className="space-y-4">
                                <div className="flex justify-between items-center">
                                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                                        <Terminal size={14} /> Response Inspector
                                    </h3>
                                    <div className="flex gap-2 p-1 bg-[#18181b] rounded-lg border border-slate-800 scale-90 origin-right">
                                        <button
                                            onClick={() => setViewMode('json')}
                                            className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${viewMode === 'json' ? "bg-zinc-800 text-white" : "text-slate-500 hover:text-white"}`}
                                        >
                                            JSON
                                        </button>
                                        <button
                                            onClick={() => setViewMode('table')}
                                            className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${viewMode === 'table' ? "bg-zinc-800 text-white" : "text-slate-500 hover:text-white"}`}
                                        >
                                            TABLE
                                        </button>
                                    </div>
                                </div>

                                <div className="bg-black/40 rounded-2xl border border-slate-800 p-6 overflow-auto max-h-[500px] scrollbar-thin">
                                    {viewMode === 'json' ? (
                                        <pre className="text-xs font-mono text-blue-300 whitespace-pre">
                                            {JSON.stringify(response, null, 2)}
                                        </pre>
                                    ) : (
                                        <JsonToTable data={response} />
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}

function JsonToTable({ data }: { data: any }) {
    if (!data) return null;
    const items = Array.isArray(data) ? data : Array.isArray(data.items) ? data.items : [data];
    if (items.length === 0) return <div className="text-slate-500 text-xs text-center p-8">No tabular data available.</div>;

    const headers = Object.keys(items[0] || {}).filter(k => typeof items[0][k] !== 'object');

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-left text-[11px] border-collapse">
                <thead className="text-slate-500 uppercase font-black tracking-widest border-b border-slate-800">
                    <tr>
                        {headers.map(h => <th key={h} className="pb-3 px-2">{h}</th>)}
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                    {items.map((row: any, i: number) => (
                        <tr key={i} className="hover:bg-white/[0.02]">
                            {headers.map(h => (
                                <td key={h} className="py-3 px-2 text-slate-300 font-mono">
                                    {String(row[h])}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
