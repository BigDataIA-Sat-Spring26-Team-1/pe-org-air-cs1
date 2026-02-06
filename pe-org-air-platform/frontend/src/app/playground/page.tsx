"use client";

import { useState, useEffect } from "react";
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
    Plus,
    FileJson,
    Send
} from "lucide-react";

interface Endpoint {
    name: string;
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
    path: string;
    description: string;
    body?: any;
}

const ENDPOINTS: Endpoint[] = [
    { name: "List Companies", method: 'GET', path: '/api/v1/companies/', description: "Get tracked targets" },
    {
        name: "Create Company",
        method: 'POST',
        path: '/api/v1/companies/',
        description: "Register a new target company",
        body: {
            "name": "Caterpillar Inc.",
            "ticker": "CAT",
            "industry_id": "550e8400-e29b-41d4-a716-446655440001",
            "position_factor": 0.5,
            "cik": "0000018492",
            "name_norm": "caterpillar inc"
        }
    },
    {
        name: "Collect SEC Filings",
        method: 'POST',
        path: '/api/v1/documents/collect',
        description: "Trigger SEC collection pipeline",
        body: {
            "tickers": ["CAT", "DE"],
            "company_name": "Caterpillar Inc.",
            "limit": 5
        }
    },
    {
        name: "Run Global Backfill",
        method: 'POST',
        path: '/api/v1/evidence/backfill',
        description: "Start background evidence collection"
    },
    { name: "List SEC Docs", method: 'GET', path: '/api/v1/documents?limit=5', description: "Indexed filings" },
    { name: "List Industries", method: 'GET', path: '/api/v1/industries/', description: "Get industry risk factors" },
    { name: "Health Check", method: 'GET', path: '/health', description: "System status" }
];

export default function Playground() {
    const [selectedEndpoint, setSelectedEndpoint] = useState<Endpoint>(ENDPOINTS[0]);
    const [customPath, setCustomPath] = useState(ENDPOINTS[0].path);
    const [requestBody, setRequestBody] = useState<string>(
        ENDPOINTS[0].body ? JSON.stringify(ENDPOINTS[0].body, null, 2) : ""
    );
    const [response, setResponse] = useState<any>(null);
    const [status, setStatus] = useState<number | null>(null);
    const [loading, setLoading] = useState(false);
    const [viewMode, setViewMode] = useState<'json' | 'table'>('json');

    const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

    useEffect(() => {
        setCustomPath(selectedEndpoint.path);
        setRequestBody(selectedEndpoint.body ? JSON.stringify(selectedEndpoint.body, null, 2) : "");
    }, [selectedEndpoint]);

    const handleRun = async () => {
        setLoading(true);
        setResponse(null);
        setStatus(null);
        try {
            const options: RequestInit = {
                method: selectedEndpoint.method,
                headers: {
                    "Content-Type": "application/json",
                },
            };

            if (selectedEndpoint.method !== 'GET' && requestBody) {
                try {
                    options.body = requestBody;
                } catch (e) {
                    setResponse({ error: "Invalid JSON in request body" });
                    setLoading(false);
                    return;
                }
            }

            const res = await fetch(`${API_BASE}${customPath}`, options);
            setStatus(res.status);
            const data = await res.json();
            setResponse(data);
        } catch (err) {
            setResponse({ error: "Request failed", details: String(err) });
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-8 space-y-8 max-w-6xl min-h-screen bg-[#09090b]">
            <div>
                <h2 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">
                    API Playground
                </h2>
                <p className="text-slate-400 mt-2 flex items-center gap-2">
                    <Terminal size={18} className="text-blue-500" />
                    Interactive sandbox for PE OrgAIR unified intelligence services.
                </p>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
                {/* Endpoint Selector */}
                <div className="space-y-4">
                    <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest px-2">Service Endpoints</h3>
                    <div className="space-y-2">
                        {ENDPOINTS.map((ep) => (
                            <button
                                key={ep.name}
                                onClick={() => setSelectedEndpoint(ep)}
                                className={`w-full text-left p-4 rounded-2xl border transition-all duration-300 ${selectedEndpoint.name === ep.name
                                    ? "bg-blue-600/10 border-blue-500/40 text-blue-400 shadow-[0_0_20px_rgba(59,130,246,0.1)]"
                                    : "bg-[#0c0c0e] border-slate-800 text-slate-400 hover:border-slate-700 hover:bg-white/[0.02]"
                                    }`}
                            >
                                <div className="flex items-center justify-between mb-2">
                                    <span className={`text-[10px] font-black px-2 py-0.5 rounded-md ${ep.method === 'GET' ? 'bg-green-500/20 text-green-400' :
                                            ep.method === 'POST' ? 'bg-blue-500/20 text-blue-400' :
                                                'bg-purple-500/20 text-purple-400'
                                        }`}>{ep.method}</span>
                                    <ChevronRight size={14} className={`transition-transform duration-300 ${selectedEndpoint.name === ep.name ? "translate-x-0 opacity-100" : "-translate-x-2 opacity-0"}`} />
                                </div>
                                <div className="font-bold text-sm">{ep.name}</div>
                                <div className="text-[10px] opacity-60 mt-1 truncate">{ep.path}</div>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Execution Engine */}
                <div className="lg:col-span-2 space-y-6">
                    <div className="bg-[#0c0c0e] border border-slate-800 rounded-3xl p-8 shadow-2xl relative overflow-hidden group">
                        <div className="space-y-6">
                            {/* Path Input */}
                            <div className="space-y-3">
                                <label className="text-sm font-semibold text-slate-300 flex items-center gap-2">
                                    <Globe size={14} className="text-blue-400" />
                                    Request URL
                                </label>
                                <div className="flex gap-3">
                                    <div className="flex-1 relative group">
                                        <div className={`absolute left-4 top-1/2 -translate-y-1/2 font-black text-[10px] px-1.5 py-0.5 rounded ${selectedEndpoint.method === 'GET' ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
                                            }`}>{selectedEndpoint.method}</div>
                                        <input
                                            type="text"
                                            value={customPath}
                                            onChange={(e) => setCustomPath(e.target.value)}
                                            className="w-full bg-[#18181b] border border-slate-800 rounded-xl py-3 pl-16 pr-4 text-sm font-mono text-blue-300 focus:outline-none focus:ring-2 focus:ring-blue-500/20 transition-all"
                                        />
                                    </div>
                                    <button
                                        onClick={handleRun}
                                        disabled={loading}
                                        className="bg-blue-600 hover:bg-blue-500 active:scale-95 disabled:bg-blue-800/50 text-white px-8 py-3 rounded-xl transition-all font-black flex items-center gap-2 shadow-lg shadow-blue-500/20"
                                    >
                                        {loading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                                        SEND
                                    </button>
                                </div>
                            </div>

                            {/* Body Input (for POST) */}
                            {selectedEndpoint.method !== 'GET' && (
                                <div className="space-y-3 animate-in fade-in slide-in-from-top-2 duration-300">
                                    <label className="text-sm font-semibold text-slate-300 flex items-center justify-between">
                                        <div className="flex items-center gap-2">
                                            <FileJson size={14} className="text-purple-400" />
                                            Request Body
                                        </div>
                                        <span className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">application/json</span>
                                    </label>
                                    <textarea
                                        value={requestBody}
                                        onChange={(e) => setRequestBody(e.target.value)}
                                        rows={8}
                                        className="w-full bg-[#18181b] border border-slate-800 rounded-xl p-6 text-xs font-mono text-slate-300 focus:outline-none focus:ring-2 focus:ring-purple-500/20 transition-all resize-none shadow-inner"
                                        placeholder="{ ... }"
                                    />
                                </div>
                            )}

                            {/* Response Section */}
                            {(response || loading) && (
                                <div className="space-y-4 pt-4 border-t border-slate-800 animate-in fade-in duration-500">
                                    <div className="flex justify-between items-center">
                                        <div className="flex items-center gap-4">
                                            <h3 className="text-xs font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2">
                                                <Terminal size={14} /> Response Data
                                            </h3>
                                            {status && (
                                                <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${status < 300 ? 'bg-green-500/10 text-green-400 border border-green-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
                                                    }`}>
                                                    HTTP {status}
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex gap-2 p-1 bg-[#18181b] rounded-lg border border-slate-800 scale-90 origin-right shadow-inner">
                                            <button
                                                onClick={() => setViewMode('json')}
                                                className={`px-4 py-1.5 rounded-md text-[10px] font-black tracking-widest transition-all ${viewMode === 'json' ? "bg-blue-600 text-white shadow-lg" : "text-slate-500 hover:text-white"}`}
                                            >
                                                JSON
                                            </button>
                                            <button
                                                onClick={() => setViewMode('table')}
                                                className={`px-4 py-1.5 rounded-md text-[10px] font-black tracking-widest transition-all ${viewMode === 'table' ? "bg-blue-600 text-white shadow-lg" : "text-slate-500 hover:text-white"}`}
                                            >
                                                TABLE
                                            </button>
                                        </div>
                                    </div>

                                    <div className="bg-black/60 rounded-2xl border border-slate-800 p-8 overflow-auto max-h-[600px] scrollbar-thin shadow-inner group-hover:border-slate-700 transition-colors">
                                        {loading ? (
                                            <div className="flex flex-col items-center justify-center py-20 gap-4">
                                                <Loader2 size={32} className="animate-spin text-blue-500" />
                                                <p className="text-xs text-slate-500 font-mono animate-pulse">Waiting for remote host...</p>
                                            </div>
                                        ) : viewMode === 'json' ? (
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
        </div>
    );
}

function JsonToTable({ data }: { data: any }) {
    if (!data) return null;
    const items = Array.isArray(data) ? data : Array.isArray(data.items) ? data.items : [data];
    if (items.length === 0 || typeof items[0] !== 'object') {
        return <div className="text-slate-500 text-xs text-center p-8 font-mono">No structured tabular data available.</div>;
    }

    const headers = Object.keys(items[0]).filter(k => typeof items[0][k] !== 'object' || items[0][k] === null);

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-left text-[11px] border-collapse min-w-[500px]">
                <thead className="text-slate-500 uppercase font-black tracking-widest bg-white/[0.02]">
                    <tr>
                        {headers.map(h => <th key={h} className="py-4 px-4 border-b border-slate-800">{h}</th>)}
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                    {items.map((row: any, i: number) => (
                        <tr key={i} className="hover:bg-white/[0.04] transition-colors">
                            {headers.map(h => (
                                <td key={h} className="py-4 px-4 text-slate-300 font-mono">
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
