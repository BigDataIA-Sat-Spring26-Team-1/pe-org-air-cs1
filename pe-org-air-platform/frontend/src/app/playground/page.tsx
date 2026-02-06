"use client";

import React, { useState, useEffect, useMemo } from "react";
import {
    Terminal,
    ChevronRight,
    Loader2,
    FileJson,
    Send,
    Database,
    Shield,
    Activity,
    Globe,
    Search,
    Brain,
    FileText,
    Settings,
    ChevronDown,
    TestTube,
} from "lucide-react";

interface Endpoint {
    name: string;
    method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
    path: string;
    description: string;
    body?: any;
    tag: string;
}

const CATEGORIES: any[] = [
    {
        name: "Companies",
        tag: "Companies",
        icon: <Database size={16} />,
        endpoints: [
            { tag: "Companies", name: "List Companies", method: 'GET', path: '/api/v1/companies/', description: "Get tracked targets" },
            { tag: "Companies", name: "Get Company", method: 'GET', path: '/api/v1/companies/{id}', description: "Retrieve single company details" },
            { tag: "Companies", name: "Create Company", method: 'POST', path: '/api/v1/companies/', description: "Register a new target", body: { name: "Example Inc.", ticker: "EXMP", industry_id: "...", position_factor: 0.5 } },
            { tag: "Companies", name: "Delete Company", method: 'DELETE', path: '/api/v1/companies/{id}', description: "Remove from portfolio" },
        ]
    },
    {
        name: "Documents (SEC)",
        tag: "Documents",
        icon: <FileText size={16} />,
        endpoints: [
            { tag: "Documents", name: "Inspect Chunks", method: 'GET', path: '/api/v1/documents/{document_id}/chunks', description: "View semantic segments" },
            { tag: "Documents", name: "Search Documents", method: 'GET', path: '/api/v1/documents', description: "Filter filings by ticker/type" },
            { tag: "Documents", name: "Get Document", method: 'GET', path: '/api/v1/documents/{document_id}', description: "Retrieve filing metadata" },
            { tag: "Documents", name: "Collect Filings", method: 'POST', path: '/api/v1/documents/collect', description: "Trigger SEC scraper", body: { tickers: ["CAT"], limit: 2 } },
        ]
    },
    {
        name: "Signals & Evidence",
        tag: "Evidence",
        icon: <Activity size={16} />,
        endpoints: [
            { tag: "Evidence", name: "List Signals", method: 'GET', path: '/api/v1/signals/', description: "Retrieve all captured signals" },
            { tag: "Evidence", name: "Signal Stats", method: 'GET', path: '/api/v1/signals/stats', description: "Aggregated counts" },
            { tag: "Evidence", name: "List Evidence", method: 'GET', path: '/api/v1/signals/evidence', description: "Supporting links/docs" },
            { tag: "Evidence", name: "Run Backfill", method: 'POST', path: '/api/v1/evidence/backfill', description: "Force refresh evidence" },
        ]
    },
    {
        name: "Intelligence & Metrics",
        tag: "Metrics",
        icon: <Brain size={16} />,
        endpoints: [
            { tag: "Metrics", name: "Company Stats", method: 'GET', path: '/api/v1/metrics/company-stats', description: "Performance metrics" },
            { tag: "Metrics", name: "Industry Distribution", method: 'GET', path: '/api/v1/metrics/industry-distribution', description: "Portfolio concentration" },
            { tag: "Metrics", name: "List Assessments", method: 'GET', path: '/api/v1/assessments', description: "Maturity evaluations" },
        ]
    },
    {
        name: "Testing",
        tag: "Testing",
        icon: <TestTube size={16} />,
        endpoints: [
            { tag: "Testing", name: "Run System Tests", method: 'POST', path: '/api/v1/system/run-tests', description: "Trigger full pytest infrastructure audit" },
        ]
    },
    {
        name: "System",
        tag: "Health",
        icon: <Settings size={16} />,
        endpoints: [
            { tag: "Health", name: "Health Check", method: 'GET', path: '/health', description: "Service status monitoring" },
            { tag: "Configuration", name: "Get Config", method: 'GET', path: '/api/v1/config/vars', description: "Active environment vars" },
        ]
    }
];

const ALL_ENDPOINTS: any[] = CATEGORIES.flatMap(c => c.endpoints);

export default function Playground() {
    const [selectedEndpoint, setSelectedEndpoint] = useState<Endpoint>(ALL_ENDPOINTS[0]);
    const [customPath, setCustomPath] = useState(ALL_ENDPOINTS[0].path);
    const [requestBody, setRequestBody] = useState<string>("");
    const [response, setResponse] = useState<any>(null);
    const [status, setStatus] = useState<number | null>(null);
    const [loading, setLoading] = useState(false);
    const [viewMode, setViewMode] = useState<'json' | 'table'>('json');
    const [expandedTags, setExpandedTags] = useState<string[]>(["Companies", "Documents"]);

    const API_BASE = (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_URL) || "http://localhost:8000";

    const toggleTag = (tag: string) => {
        setExpandedTags(prev => prev.includes(tag) ? prev.filter((t: string) => t !== tag) : [...prev, tag]);
    };

    const handleRun = async (overridePath?: string, overrideMethod?: string, overrideBody?: string) => {
        setLoading(true);
        setResponse(null);
        setStatus(null);

        const path = overridePath || customPath;
        const method = overrideMethod || selectedEndpoint.method;
        const body = overrideBody || requestBody;

        try {
            const options: RequestInit = {
                method: method,
                headers: { "Content-Type": "application/json" },
            };

            if (method !== 'GET' && body) {
                try {
                    options.body = body;
                } catch (e) {
                    setResponse({ error: "Invalid JSON in request body" });
                    setLoading(false);
                    return;
                }
            }

            const res = await fetch(`${API_BASE}${path}`, options);
            setStatus(res.status);
            const data = await res.json();
            setResponse(data);
        } catch (err) {
            setResponse({ error: "Request failed", details: String(err) });
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const pathParam = params.get('path');
        const methodParam = params.get('method') as 'GET' | 'POST' | null;
        const autoRun = params.get('run');

        if (pathParam) {
            // Find best matching endpoint pattern
            const foundEndpoint = ALL_ENDPOINTS.find(ep => {
                const epBase = ep.path.split('{')[0];
                return pathParam.startsWith(epBase);
            });

            const targetEndpoint: Endpoint = foundEndpoint ? {
                ...foundEndpoint,
                method: methodParam || foundEndpoint.method,
                path: pathParam
            } : {
                tag: "Custom",
                name: "Direct Request",
                method: methodParam || 'GET',
                path: pathParam,
                description: "Deep-linked from application"
            };

            setSelectedEndpoint(targetEndpoint);
            setCustomPath(pathParam);

            // Expand the relevant tag
            if (foundEndpoint && !expandedTags.includes(foundEndpoint.tag)) {
                setExpandedTags((prev: string[]) => [...prev, foundEndpoint.tag]);
            }

            if (autoRun === 'true') {
                handleRun(pathParam, targetEndpoint.method);
            }
        }
    }, []);

    const onSelectEndpoint = (ep: Endpoint) => {
        setSelectedEndpoint(ep);
        setCustomPath(ep.path);
        setRequestBody(ep.body ? JSON.stringify(ep.body, null, 2) : "");
        setResponse(null);
        setStatus(null);
    };

    return (
        <div className="flex flex-col lg:flex-row min-h-screen bg-[#09090b] text-slate-300">
            {/* Sidebar */}
            <div className="w-full lg:w-80 border-r border-slate-800 flex flex-col h-screen overflow-hidden">
                <div className="p-6 border-b border-slate-800 shrink-0">
                    <div className="flex items-center gap-2 mb-1">
                        <div className="w-6 h-6 bg-blue-600 rounded-lg flex items-center justify-center">
                            <Terminal size={14} className="text-white" />
                        </div>
                        <h1 className="font-black text-white tracking-tighter">ORG-AI-R API</h1>
                    </div>
                    <p className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">Unified Intelligence Sandbox</p>
                </div>

                <div className="flex-1 overflow-y-auto p-4 space-y-2 scrollbar-hide">
                    {CATEGORIES.map(cat => (
                        <div key={cat.tag} className="space-y-1">
                            <button
                                onClick={() => toggleTag(cat.tag)}
                                className="w-full flex items-center justify-between p-2 hover:bg-white/[0.02] rounded-lg transition-all group"
                            >
                                <div className="flex items-center gap-3">
                                    <span className="text-slate-500 group-hover:text-blue-400 transition-colors">{cat.icon}</span>
                                    <span className="text-xs font-bold text-slate-400 group-hover:text-slate-200 uppercase tracking-wider">{cat.name}</span>
                                </div>
                                <ChevronDown size={14} className={`text-slate-600 transition-transform ${expandedTags.includes(cat.tag) ? "" : "-rotate-90"}`} />
                            </button>

                            {expandedTags.includes(cat.tag) && (
                                <div className="space-y-1 pl-4 animate-in slide-in-from-top-1 duration-200">
                                    {cat.endpoints.map((ep: Endpoint) => (
                                        <button
                                            key={ep.name}
                                            onClick={() => onSelectEndpoint(ep)}
                                            className={`w-full text-left p-2.5 rounded-xl transition-all group relative ${selectedEndpoint.path === ep.path && selectedEndpoint.name === ep.name
                                                ? "bg-blue-600/10 text-blue-400"
                                                : "hover:bg-white/[0.01] text-slate-500 hover:text-slate-300"
                                                }`}
                                        >
                                            <div className="flex items-center gap-3">
                                                <span className={`text-[8px] font-black w-7 text-center ${ep.method === 'GET' ? 'text-green-500' : 'text-blue-500'
                                                    }`}>{ep.method}</span>
                                                <span className="text-[11px] font-medium truncate">{ep.name}</span>
                                            </div>
                                            {selectedEndpoint.path === ep.path && selectedEndpoint.name === ep.name && (
                                                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-4 bg-blue-500 rounded-full" />
                                            )}
                                        </button>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            </div>

            {/* Main Content */}
            <div className="flex-1 h-screen overflow-y-auto p-8 lg:p-12 space-y-8">
                <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
                    <div>
                        <div className="flex items-center gap-3 text-blue-400 mb-2">
                            <div className="h-0.5 w-8 bg-blue-500/30 rounded-full" />
                            <span className="text-xs font-black uppercase tracking-widest">{selectedEndpoint.tag}</span>
                        </div>
                        <h2 className="text-3xl font-black text-white tracking-tight">{selectedEndpoint.name}</h2>
                        <p className="text-slate-500 text-sm mt-1">{selectedEndpoint.description}</p>
                    </div>
                </div>

                <div className="flex flex-col gap-8">
                    {/* Input Panel */}
                    <div className="space-y-6">
                        <div className="bg-[#0c0c0e]/50 border border-slate-800 rounded-3xl p-8 backdrop-blur-xl shadow-2xl relative overflow-hidden group">
                            <div className="absolute top-0 right-0 w-64 h-64 bg-blue-600/5 blur-[100px] -mr-32 -mt-32 rounded-full" />

                            <div className="space-y-6 relative z-10">
                                <div className="space-y-3">
                                    <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center gap-2">
                                        <Globe size={12} className="text-blue-500" /> Endpoint Path
                                    </label>
                                    <div className="flex flex-col md:flex-row gap-3">
                                        <div className="flex-1 relative">
                                            <input
                                                type="text"
                                                value={customPath}
                                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setCustomPath(e.target.value)}
                                                className="w-full bg-black/40 border border-slate-800 rounded-2xl py-4 px-6 text-sm font-mono text-blue-400 focus:outline-none focus:border-blue-500/50 transition-all shadow-inner"
                                            />
                                        </div>
                                        <button
                                            onClick={() => handleRun()}
                                            disabled={loading}
                                            className="bg-blue-600 hover:bg-blue-500 active:scale-95 disabled:bg-blue-900/50 disabled:text-slate-500 text-white px-8 py-4 rounded-2xl font-black text-xs tracking-widest flex items-center justify-center gap-2 transition-all shadow-[0_0_30px_rgba(37,99,235,0.2)]"
                                        >
                                            {loading ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                                            RUN
                                        </button>
                                    </div>
                                </div>

                                {selectedEndpoint.method !== 'GET' && (
                                    <div className="space-y-3 animate-in fade-in duration-500">
                                        <label className="text-[10px] font-black text-slate-500 uppercase tracking-widest flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <FileJson size={12} className="text-purple-500" /> Request Payload
                                            </div>
                                            <span className="text-[9px] text-slate-700">application/json</span>
                                        </label>
                                        <div className="bg-black/40 rounded-2xl border border-slate-800 p-1">
                                            <textarea
                                                value={requestBody}
                                                onChange={(e: React.ChangeEvent<HTMLTextAreaElement>) => setRequestBody(e.target.value)}
                                                rows={10}
                                                className="w-full bg-transparent p-6 text-xs font-mono text-slate-400 focus:outline-none resize-none scrollbar-hide"
                                                placeholder="{ ... }"
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Output Panel */}
                    <div className="w-full">
                        <div className="bg-[#0c0c0e]/50 border border-slate-800 rounded-3xl min-h-[500px] flex flex-col overflow-hidden shadow-2xl relative">
                            <div className="absolute top-0 right-0 w-96 h-96 bg-green-500/5 blur-[120px] -mr-48 -mt-48 rounded-full" />

                            <div className="p-8 border-b border-slate-800 flex items-center justify-between shrink-0 relative z-10">
                                <div className="flex items-center gap-4">
                                    <div className="flex items-center gap-2">
                                        <Activity size={14} className="text-slate-500" />
                                        <h3 className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Execution Result</h3>
                                    </div>
                                    {status && (
                                        <span className={`text-[9px] font-bold px-2.5 py-1 rounded-md border ${status < 300
                                            ? 'bg-green-500/10 border-green-500/20 text-green-400'
                                            : 'bg-red-500/10 border-red-500/20 text-red-400'
                                            }`}>
                                            HTTP {status}
                                        </span>
                                    )}
                                </div>
                                <div className="flex gap-1 p-1 bg-black/40 rounded-xl border border-slate-800">
                                    <button onClick={() => setViewMode('json')} className={`px-5 py-2 rounded-lg text-[9px] font-black tracking-widest transition-all ${viewMode === 'json' ? "bg-blue-600 text-white shadow-lg" : "text-slate-500 hover:text-slate-300"}`}>JSON</button>
                                    <button onClick={() => setViewMode('table')} className={`px-5 py-2 rounded-lg text-[9px] font-black tracking-widest transition-all ${viewMode === 'table' ? "bg-blue-600 text-white shadow-lg" : "text-slate-500 hover:text-slate-300"}`}>TABLE</button>
                                </div>
                            </div>

                            <div className="flex-1 overflow-auto p-8 relative z-10">
                                {loading ? (
                                    <div className="h-full flex flex-col items-center justify-center gap-4 py-32">
                                        <Loader2 size={32} className="animate-spin text-blue-500/50" />
                                        <span className="text-[10px] font-bold text-slate-600 uppercase tracking-[0.2em] animate-pulse">Execution in progress...</span>
                                    </div>
                                ) : response ? (
                                    viewMode === 'json' ? (
                                        <pre className="text-xs font-mono text-blue-400/90 whitespace-pre-wrap break-words leading-relaxed p-6 bg-black/20 rounded-2xl border border-slate-800/50">
                                            {JSON.stringify(response, null, 2)}
                                        </pre>
                                    ) : (
                                        <JsonToTable data={response} />
                                    )
                                ) : (
                                    <div className="h-full flex flex-col items-center justify-center text-slate-700 opacity-50 py-32">
                                        <Search size={48} strokeWidth={1} className="mb-6 opacity-20" />
                                        <p className="text-[11px] font-black uppercase tracking-[0.3em] text-center leading-relaxed">No execution data<br /><span className="text-[9px] font-medium opacity-50 tracking-normal">Send request to trigger pipeline</span></p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

function JsonToTable({ data }: { data: any }) {
    if (!data) return null;
    const items = Array.isArray(data) ? data : (data && typeof data === 'object' && Array.isArray(data.items)) ? data.items : [data];
    if (items.length === 0 || typeof items[0] !== 'object' || items[0] === null) {
        return <div className="text-slate-600 text-[10px] font-mono p-4">No tabular representation available.</div>;
    }

    const headers = Object.keys(items[0]).filter(k => typeof items[0][k] !== 'object' || items[0][k] === null);

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-left text-[10px] border-collapse">
                <thead className="text-slate-600 uppercase font-black tracking-widest bg-white/[0.01]">
                    <tr>
                        {headers.map(h => <th key={h} className="py-3 px-4 border-b border-slate-800">{h}</th>)}
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                    {items.slice(0, 100).map((row: any, i: number) => (
                        <tr key={i} className="hover:bg-white/[0.02] transition-colors">
                            {headers.map(h => (
                                <td key={h} className="py-3 px-4 text-slate-400 font-mono whitespace-nowrap">
                                    {row[h] === null ? <span className="text-slate-700 italic">null</span> : String(row[h])}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
