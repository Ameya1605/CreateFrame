'use client';

import React, { useState, useEffect, useMemo } from 'react';
import api from '@/lib/api';
import {
    FileText, Plus, GitCommit, Check, Loader2, Sparkles,
    Calendar, BookOpen, ShieldCheck, Copy, CheckCheck,
    Download, Code2, LayoutDashboard, Database, Globe,
    ThumbsUp, AlertTriangle, Search, Tag, ArrowRight,
    CheckCircle2, Compass, Layers, ListFilter
} from 'lucide-react';

interface ADRItem {
    id: number;
    title: string;
    status: string;
    file_path: string;
    content: string;
    committed: boolean;
    created_at?: string;
}

interface ParsedRoute {
    method: string;
    path: string;
}

interface ParsedADR {
    adrNumber: string;
    title: string;
    date: string;
    status: string;
    contextText: string;
    addedTables: string[];
    removedTables: string[];
    addedRoutes: ParsedRoute[];
    removedRoutes: ParsedRoute[];
    decisionDrivers: string[];
    decisionSteps: string[];
    positives: string[];
    negatives: string[];
    rawFallback?: boolean;
}

const METHOD_STYLES: Record<string, { bg: string; text: string; border: string }> = {
    GET: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/25' },
    POST: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/25' },
    PUT: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/25' },
    PATCH: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/25' },
    DELETE: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/25' },
};

function parseADRContent(content: string, fallbackTitle: string, fallbackPath: string): ParsedADR {
    if (!content) {
        return {
            adrNumber: '0001',
            title: fallbackTitle,
            date: new Date().toISOString().split('T')[0],
            status: 'Accepted',
            contextText: 'No content recorded.',
            addedTables: [],
            removedTables: [],
            addedRoutes: [],
            removedRoutes: [],
            decisionDrivers: [],
            decisionSteps: [],
            positives: [],
            negatives: [],
            rawFallback: true
        };
    }

    try {
        // Extract title & number
        const titleMatch = content.match(/#\s*(\d+)\.\s*(.+)/) || content.match(/(\d+)\.\s*(.+)/);
        const adrNumber = titleMatch ? titleMatch[1].padStart(4, '0') : (fallbackPath.match(/\d+/)?.[0] || '0001');
        const title = titleMatch ? titleMatch[2].trim() : fallbackTitle;

        // Extract Date
        const dateMatch = content.match(/Date:\s*([^\n\r]+)/i);
        const date = dateMatch ? dateMatch[1].trim() : new Date().toISOString().split('T')[0];

        // Extract Status
        const statusMatch = content.match(/##\s*Status\s*[\r\n]+([^\r\n#]+)/i);
        const status = statusMatch ? statusMatch[1].trim() : 'Accepted';

        // Extract Context block
        const contextSectionMatch = content.match(/##\s*Context\s*[\r\n]+([\s\S]*?)(?=##\s*Decision Drivers|##\s*Decision|$)/i);
        const fullContext = contextSectionMatch ? contextSectionMatch[1].trim() : '';

        // Separate pure context explanation from Changes Detected
        const changesIndex = fullContext.indexOf('### Changes Detected:');
        let contextText = fullContext;
        let changesBlock = '';
        if (changesIndex !== -1) {
            contextText = fullContext.slice(0, changesIndex).trim();
            changesBlock = fullContext.slice(changesIndex);
        }

        // Parse Routes from changes
        const parseRoutesFromText = (text: string): ParsedRoute[] => {
            const routes: ParsedRoute[] = [];
            const regex = /(GET|POST|PUT|PATCH|DELETE)\s+([^\s,\n\r`)]+)/gi;
            let match;
            while ((match = regex.exec(text)) !== null) {
                routes.push({
                    method: match[1].toUpperCase(),
                    path: match[2].trim()
                });
            }
            return routes;
        };

        // Extract added and removed routes
        const addedRoutesMatch = changesBlock.match(/- \*\*Added Routes[^*]*\*\*:\s*([\s\S]*?)(?=- \*\*Removed Routes|$)/i);
        const addedRoutes = addedRoutesMatch ? parseRoutesFromText(addedRoutesMatch[1]) : [];

        const removedRoutesMatch = changesBlock.match(/- \*\*Removed Routes[^*]*\*\*:\s*([\s\S]*?)(?=##|$)/i);
        const removedRoutes = removedRoutesMatch ? parseRoutesFromText(removedRoutesMatch[1]) : [];

        // Parse Tables from changes
        const parseTablesFromText = (text: string): string[] => {
            const clean = text.replace(/None/gi, '').trim();
            if (!clean) return [];
            return clean
                .split(/[,\n]/)
                .map(t => t.replace(/[-*`]/g, '').trim())
                .filter(t => t.length > 0 && t.toLowerCase() !== 'none');
        };

        const addedTablesMatch = changesBlock.match(/- \*\*Added Tables[^*]*\*\*:\s*([^\n\r]+)/i);
        const addedTables = addedTablesMatch ? parseTablesFromText(addedTablesMatch[1]) : [];

        const removedTablesMatch = changesBlock.match(/- \*\*Removed Tables[^*]*\*\*:\s*([^\n\r]+)/i);
        const removedTables = removedTablesMatch ? parseTablesFromText(removedTablesMatch[1]) : [];

        // Extract Decision Drivers
        const driversMatch = content.match(/##\s*Decision Drivers\s*[\r\n]+([\s\S]*?)(?=##\s*Decision|$)/i);
        const decisionDrivers = driversMatch
            ? driversMatch[1]
                .split('\n')
                .map(l => l.replace(/^[-*]\s*/, '').trim())
                .filter(Boolean)
            : [];

        // Extract Decision block
        const decisionMatch = content.match(/##\s*Decision\s*[\r\n]+([\s\S]*?)(?=##\s*Consequences|$)/i);
        const decisionSteps = decisionMatch
            ? decisionMatch[1]
                .split('\n')
                .map(l => l.replace(/^\d+\.\s*/, '').replace(/^[-*]\s*/, '').trim())
                .filter(Boolean)
            : [];

        // Extract Consequences Positive & Negative
        const posMatch = content.match(/###\s*Positive\s*[\r\n]+([\s\S]*?)(?=###\s*Negative|##|$)/i);
        const positives = posMatch
            ? posMatch[1]
                .split('\n')
                .map(l => l.replace(/^[-*]\s*/, '').trim())
                .filter(Boolean)
            : [];

        const negMatch = content.match(/###\s*Negative\s*[\r\n]+([\s\S]*?)(?=##|$)/i);
        const negatives = negMatch
            ? negMatch[1]
                .split('\n')
                .map(l => l.replace(/^[-*]\s*/, '').trim())
                .filter(Boolean)
            : [];

        return {
            adrNumber,
            title,
            date,
            status,
            contextText,
            addedTables,
            removedTables,
            addedRoutes,
            removedRoutes,
            decisionDrivers,
            decisionSteps,
            positives,
            negatives
        };
    } catch {
        return {
            adrNumber: '0001',
            title: fallbackTitle,
            date: new Date().toISOString().split('T')[0],
            status: 'Accepted',
            contextText: content,
            addedTables: [],
            removedTables: [],
            addedRoutes: [],
            removedRoutes: [],
            decisionDrivers: [],
            decisionSteps: [],
            positives: [],
            negatives: [],
            rawFallback: true
        };
    }
}

export default function ADRView({
    projectId,
    onShowToast
}: {
    projectId: number;
    onShowToast: (msg: string, isSuccess?: boolean) => void;
}) {
    const [adrs, setAdrs] = useState<ADRItem[]>([]);
    const [selectedAdr, setSelectedAdr] = useState<ADRItem | null>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    const [committing, setCommitting] = useState(false);
    const [customTitle, setCustomTitle] = useState('');
    const [showDraftModal, setShowDraftModal] = useState(false);

    // View toggles
    const [viewMode, setViewMode] = useState<'visual' | 'raw'>('visual');
    const [routeFilter, setRouteFilter] = useState('');
    const [copied, setCopied] = useState(false);

    const loadADRs = async () => {
        if (!projectId || isNaN(projectId)) {
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const res = await api.get(`/projects/${projectId}/adrs`);
            setAdrs(res.data);
            if (res.data.length > 0 && !selectedAdr) {
                setSelectedAdr(res.data[0]);
            }
        } catch {
            // non-critical
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (projectId && !isNaN(projectId)) {
            loadADRs();
        }
    }, [projectId]);

    const handleGenerate = async () => {
        setGenerating(true);
        try {
            const res = await api.post(`/projects/${projectId}/adrs/generate`, {
                title: customTitle.trim() || undefined
            });
            onShowToast(`Drafted new decision record: ${res.data.title}`);
            setShowDraftModal(false);
            setCustomTitle('');
            await loadADRs();
            setSelectedAdr(res.data);
        } catch (err: any) {
            onShowToast(err.response?.data?.detail || 'Failed to generate ADR', false);
        } finally {
            setGenerating(false);
        }
    };

    const handleCommit = async (adr: ADRItem) => {
        setCommitting(true);
        try {
            await api.post(`/projects/${projectId}/adrs/commit`, {
                adr_id: adr.id
            });
            onShowToast(`Committed ${adr.file_path} to repository!`);
            await loadADRs();
            if (selectedAdr && selectedAdr.id === adr.id) {
                setSelectedAdr({ ...selectedAdr, committed: true });
            }
        } catch (err: any) {
            onShowToast(err.response?.data?.detail || 'Failed to commit ADR to GitHub', false);
        } finally {
            setCommitting(false);
        }
    };

    const parsedADR = useMemo(() => {
        if (!selectedAdr) return null;
        return parseADRContent(selectedAdr.content, selectedAdr.title, selectedAdr.file_path);
    }, [selectedAdr]);

    const handleCopyMarkdown = () => {
        if (!selectedAdr) return;
        navigator.clipboard.writeText(selectedAdr.content);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
        onShowToast('Markdown copied to clipboard!');
    };

    const handleDownload = () => {
        if (!selectedAdr) return;
        const blob = new Blob([selectedAdr.content], { type: 'text/markdown' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = selectedAdr.file_path.split('/').pop() || 'ADR.md';
        a.click();
        URL.revokeObjectURL(url);
    };

    const filteredRoutes = useMemo(() => {
        if (!parsedADR) return [];
        if (!routeFilter.trim()) return parsedADR.addedRoutes;
        const q = routeFilter.toLowerCase();
        return parsedADR.addedRoutes.filter(r =>
            r.method.toLowerCase().includes(q) || r.path.toLowerCase().includes(q)
        );
    }, [parsedADR, routeFilter]);

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-3 bg-[var(--surface-0)]">
                <Loader2 size={24} className="animate-spin text-blue-500" />
                <p className="text-xs text-zinc-400">Loading Architecture Decision Records (docs/adr/)...</p>
            </div>
        );
    }

    return (
        <div className="flex h-full bg-[var(--surface-0)] overflow-hidden antialiased">
            {/* Sidebar list */}
            <div className="w-80 bg-[var(--surface-1)] border-r border-[var(--border-subtle)] flex flex-col shrink-0">
                <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
                    <div>
                        <h3 className="text-xs font-bold text-white flex items-center gap-1.5">
                            <BookOpen size={14} className="text-blue-400" />
                            <span>Decision Records</span>
                        </h3>
                        <p className="text-[10px] text-zinc-500 font-mono mt-0.5">MADR 3.0 • docs/adr/</p>
                    </div>

                    <button
                        onClick={() => setShowDraftModal(true)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-semibold transition-all shadow-sm shadow-blue-600/20"
                    >
                        <Plus size={12} />
                        <span>Draft ADR</span>
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-2.5 space-y-1.5">
                    {adrs.length === 0 ? (
                        <div className="p-8 text-center text-zinc-500 text-xs">
                            <Compass size={24} className="text-zinc-600 mx-auto mb-2" />
                            <p className="font-medium text-zinc-400">No decision records yet</p>
                            <p className="text-[11px] text-zinc-600 mt-1">Click "Draft ADR" to generate an architectural record from your recent spec changes.</p>
                        </div>
                    ) : (
                        adrs.map(a => {
                            const isSelected = selectedAdr?.id === a.id;
                            const fileName = a.file_path.split('/').pop() || '';
                            const num = fileName.match(/^\d+/)?.[0] || 'ADR';

                            return (
                                <button
                                    key={a.id}
                                    onClick={() => setSelectedAdr(a)}
                                    className={`w-full flex flex-col p-3 rounded-xl text-left transition-all ${
                                        isSelected
                                            ? 'bg-blue-600/15 border border-blue-500/35 text-white shadow-sm'
                                            : 'text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)]/70 border border-transparent'
                                    }`}
                                >
                                    <div className="flex items-center justify-between w-full mb-1.5">
                                        <div className="flex items-center gap-1.5">
                                            <span className="text-[10px] px-1.5 py-0.5 rounded font-mono font-bold bg-zinc-800 text-zinc-300 border border-zinc-700/50">
                                                #{num}
                                            </span>
                                            <span className="text-[10px] font-mono text-zinc-500 truncate max-w-[120px]">
                                                {fileName}
                                            </span>
                                        </div>
                                        {a.committed ? (
                                            <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                                                <Check size={9} /> Committed
                                            </span>
                                        ) : (
                                            <span className="text-[9px] px-1.5 py-0.5 rounded font-bold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                                Draft
                                            </span>
                                        )}
                                    </div>
                                    <span className="text-xs font-semibold line-clamp-2 text-zinc-200 leading-snug">
                                        {a.title}
                                    </span>
                                </button>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Detail Viewer */}
            <div className="flex-1 flex flex-col overflow-hidden bg-[var(--surface-0)]">
                {selectedAdr && parsedADR ? (
                    <>
                        {/* Top Action Bar */}
                        <div className="px-6 py-3.5 border-b border-[var(--border-subtle)] bg-[var(--surface-1)] flex items-center justify-between shrink-0">
                            <div className="flex items-center gap-4">
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-mono font-bold px-2 py-0.5 rounded-lg bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                        ADR #{parsedADR.adrNumber}
                                    </span>
                                    <h3 className="text-sm font-bold text-white truncate max-w-md">
                                        {parsedADR.title}
                                    </h3>
                                </div>

                                <div className="hidden md:flex items-center gap-2 text-xs text-zinc-400">
                                    <span className="flex items-center gap-1 text-[11px] font-mono text-zinc-500 bg-[var(--surface-2)] px-2 py-0.5 rounded-md border border-[var(--border-subtle)]">
                                        {selectedAdr.file_path}
                                    </span>
                                </div>
                            </div>

                            <div className="flex items-center gap-2">
                                {/* Mode switcher */}
                                <div className="flex items-center bg-[var(--surface-2)] p-0.5 rounded-xl border border-[var(--border-subtle)]">
                                    <button
                                        onClick={() => setViewMode('visual')}
                                        className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                                            viewMode === 'visual'
                                                ? 'bg-blue-600 text-white font-semibold shadow-sm'
                                                : 'text-zinc-400 hover:text-zinc-200'
                                        }`}
                                    >
                                        <LayoutDashboard size={12} />
                                        <span>Document View</span>
                                    </button>
                                    <button
                                        onClick={() => setViewMode('raw')}
                                        className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                                            viewMode === 'raw'
                                                ? 'bg-blue-600 text-white font-semibold shadow-sm'
                                                : 'text-zinc-400 hover:text-zinc-200'
                                        }`}
                                    >
                                        <Code2 size={12} />
                                        <span>Raw Markdown</span>
                                    </button>
                                </div>

                                <button
                                    onClick={handleCopyMarkdown}
                                    className="p-1.5 rounded-xl text-zinc-400 hover:text-white hover:bg-[var(--surface-2)] transition-all border border-[var(--border-subtle)]"
                                    title="Copy Markdown"
                                >
                                    {copied ? <CheckCheck size={14} className="text-emerald-400" /> : <Copy size={14} />}
                                </button>

                                <button
                                    onClick={handleDownload}
                                    className="p-1.5 rounded-xl text-zinc-400 hover:text-white hover:bg-[var(--surface-2)] transition-all border border-[var(--border-subtle)]"
                                    title="Download .md"
                                >
                                    <Download size={14} />
                                </button>

                                <button
                                    onClick={() => handleCommit(selectedAdr)}
                                    disabled={committing || selectedAdr.committed}
                                    className={`flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-semibold transition-all shadow-sm ${
                                        selectedAdr.committed
                                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 cursor-default'
                                            : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/25'
                                    }`}
                                >
                                    {committing ? <Loader2 size={13} className="animate-spin" /> : selectedAdr.committed ? <Check size={13} /> : <GitCommit size={13} />}
                                    <span>{selectedAdr.committed ? 'Committed to Git' : 'Commit to docs/adr/'}</span>
                                </button>
                            </div>
                        </div>

                        {/* Content Area */}
                        {viewMode === 'raw' ? (
                            <div className="flex-1 overflow-y-auto p-6 font-mono text-xs text-blue-100/90 leading-relaxed bg-[var(--surface-0)] selection:bg-blue-600/30 whitespace-pre-wrap">
                                {selectedAdr.content}
                            </div>
                        ) : (
                            <div className="flex-1 overflow-y-auto p-8 space-y-6 max-w-4xl mx-auto w-full">
                                {/* Document Header Card */}
                                <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-6 shadow-sm">
                                    <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-[var(--border-subtle)]">
                                        <div className="flex items-center gap-2.5">
                                            <span className="text-xs px-2.5 py-1 rounded-full font-bold uppercase tracking-wider bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 flex items-center gap-1.5">
                                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                                {parsedADR.status}
                                            </span>
                                            <span className="text-xs text-zinc-500">•</span>
                                            <span className="text-xs text-zinc-400 flex items-center gap-1 font-mono">
                                                <Calendar size={13} className="text-zinc-500" />
                                                {parsedADR.date}
                                            </span>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            <span className="text-[11px] font-mono text-zinc-400 px-2 py-0.5 rounded-lg bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                                                MADR 3.0 Specification
                                            </span>
                                        </div>
                                    </div>

                                    <div className="pt-4">
                                        <h1 className="text-2xl font-extrabold text-white tracking-tight leading-snug">
                                            {parsedADR.adrNumber}. {parsedADR.title}
                                        </h1>
                                        <p className="text-xs text-zinc-400 mt-2 font-mono">
                                            Target artifact: <span className="text-blue-400">{selectedAdr.file_path}</span>
                                        </p>
                                    </div>
                                </div>

                                {/* Context & Background */}
                                <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-6 shadow-sm">
                                    <div className="flex items-center gap-2 mb-3">
                                        <div className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
                                            <Compass size={16} />
                                        </div>
                                        <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-300">
                                            Context & Motivation
                                        </h2>
                                    </div>
                                    <p className="text-sm text-zinc-300 leading-relaxed font-sans">
                                        {parsedADR.contextText || 'Architecture specification was updated in CreateFrame to support new functional requirements.'}
                                    </p>
                                </div>

                                {/* Changes Detected Section (Replaces ugly wall of text with structured tags) */}
                                {(parsedADR.addedRoutes.length > 0 || parsedADR.addedTables.length > 0) && (
                                    <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-6 shadow-sm space-y-5">
                                        <div className="flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <div className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400">
                                                    <Layers size={16} />
                                                </div>
                                                <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-300">
                                                    Architectural Changes Recorded
                                                </h2>
                                            </div>
                                            <span className="text-xs font-mono px-2 py-0.5 rounded-full bg-zinc-800 text-zinc-400 border border-zinc-700">
                                                {parsedADR.addedRoutes.length} route{parsedADR.addedRoutes.length !== 1 ? 's' : ''} • {parsedADR.addedTables.length} table{parsedADR.addedTables.length !== 1 ? 's' : ''}
                                            </span>
                                        </div>

                                        {/* Added Tables */}
                                        {parsedADR.addedTables.length > 0 && (
                                            <div>
                                                <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                                    <Database size={13} className="text-purple-400" />
                                                    <span>Storage Tables Added</span>
                                                </h3>
                                                <div className="flex flex-wrap gap-2">
                                                    {parsedADR.addedTables.map((t, idx) => (
                                                        <span
                                                            key={idx}
                                                            className="px-3 py-1.5 rounded-xl bg-[var(--surface-2)] border border-[var(--border-subtle)] text-xs font-mono text-purple-300 flex items-center gap-1.5 shadow-sm"
                                                        >
                                                            <Database size={12} className="text-purple-400" />
                                                            {t}
                                                        </span>
                                                    ))}
                                                </div>
                                            </div>
                                        )}

                                        {/* Added Endpoints */}
                                        {parsedADR.addedRoutes.length > 0 && (
                                            <div>
                                                <div className="flex items-center justify-between mb-3">
                                                    <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
                                                        <Globe size={13} className="text-blue-400" />
                                                        <span>API Endpoints Added ({parsedADR.addedRoutes.length})</span>
                                                    </h3>

                                                    {parsedADR.addedRoutes.length > 6 && (
                                                        <div className="flex items-center gap-1.5 bg-[var(--surface-2)] px-2.5 py-1 rounded-lg border border-[var(--border-subtle)]">
                                                            <Search size={11} className="text-zinc-500" />
                                                            <input
                                                                type="text"
                                                                value={routeFilter}
                                                                onChange={e => setRouteFilter(e.target.value)}
                                                                placeholder="Filter routes..."
                                                                className="bg-transparent text-[11px] text-zinc-200 outline-none placeholder:text-zinc-600 w-28"
                                                            />
                                                        </div>
                                                    )}
                                                </div>

                                                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-80 overflow-y-auto pr-1">
                                                    {filteredRoutes.map((r, idx) => {
                                                        const mStyle = METHOD_STYLES[r.method] || METHOD_STYLES.GET;
                                                        return (
                                                            <div
                                                                key={idx}
                                                                className="flex items-center gap-2 p-2 rounded-xl bg-[var(--surface-2)]/80 border border-[var(--border-subtle)] hover:border-blue-500/30 transition-all font-mono text-xs"
                                                            >
                                                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider ${mStyle.bg} ${mStyle.text} border ${mStyle.border}`}>
                                                                    {r.method}
                                                                </span>
                                                                <span className="text-zinc-200 truncate" title={r.path}>
                                                                    {r.path}
                                                                </span>
                                                            </div>
                                                        );
                                                    })}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                )}

                                {/* Decision Drivers */}
                                {parsedADR.decisionDrivers.length > 0 && (
                                    <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-6 shadow-sm">
                                        <div className="flex items-center gap-2 mb-3">
                                            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                                                <Compass size={16} />
                                            </div>
                                            <h2 className="text-sm font-bold uppercase tracking-wider text-zinc-300">
                                                Decision Drivers
                                            </h2>
                                        </div>

                                        <ul className="space-y-2.5">
                                            {parsedADR.decisionDrivers.map((driver, idx) => (
                                                <li key={idx} className="flex items-start gap-2.5 text-xs text-zinc-300 leading-relaxed">
                                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-1.5 shrink-0" />
                                                    <span>{driver}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                )}

                                {/* The Decision */}
                                {parsedADR.decisionSteps.length > 0 && (
                                    <div className="bg-gradient-to-br from-blue-950/25 via-[var(--surface-1)] to-[var(--surface-1)] border border-blue-500/30 rounded-2xl p-6 shadow-md relative overflow-hidden">
                                        <div className="absolute top-0 right-0 w-32 h-32 bg-blue-500/5 rounded-full blur-2xl pointer-events-none" />

                                        <div className="flex items-center gap-2 mb-4">
                                            <div className="p-1.5 rounded-lg bg-blue-500/20 text-blue-400 border border-blue-500/30">
                                                <ShieldCheck size={16} />
                                            </div>
                                            <h2 className="text-sm font-bold uppercase tracking-wider text-blue-300">
                                                The Architectural Decision
                                            </h2>
                                        </div>

                                        <div className="space-y-3">
                                            {parsedADR.decisionSteps.map((step, idx) => (
                                                <div
                                                    key={idx}
                                                    className="flex items-start gap-3 p-3.5 rounded-xl bg-blue-900/15 border border-blue-500/20 text-xs text-zinc-200 leading-relaxed font-sans"
                                                >
                                                    <span className="w-5 h-5 rounded-full bg-blue-500/20 text-blue-400 font-bold flex items-center justify-center text-[10px] shrink-0 border border-blue-500/30">
                                                        {idx + 1}
                                                    </span>
                                                    <span>{step}</span>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                )}

                                {/* Consequences & Trade-offs */}
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                    {/* Positives */}
                                    <div className="bg-[var(--surface-1)] border border-emerald-500/20 rounded-2xl p-6 shadow-sm">
                                        <div className="flex items-center gap-2 mb-4">
                                            <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-400">
                                                <ThumbsUp size={15} />
                                            </div>
                                            <h3 className="text-xs font-bold uppercase tracking-wider text-emerald-400">
                                                Positive Outcomes
                                            </h3>
                                        </div>

                                        <ul className="space-y-2.5">
                                            {parsedADR.positives.map((p, idx) => (
                                                <li key={idx} className="flex items-start gap-2.5 text-xs text-zinc-300 leading-relaxed">
                                                    <CheckCircle2 size={13} className="text-emerald-400 shrink-0 mt-0.5" />
                                                    <span>{p}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>

                                    {/* Negatives / Trade-offs */}
                                    <div className="bg-[var(--surface-1)] border border-amber-500/20 rounded-2xl p-6 shadow-sm">
                                        <div className="flex items-center gap-2 mb-4">
                                            <div className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400">
                                                <AlertTriangle size={15} />
                                            </div>
                                            <h3 className="text-xs font-bold uppercase tracking-wider text-amber-400">
                                                Trade-offs & Constraints
                                            </h3>
                                        </div>

                                        <ul className="space-y-2.5">
                                            {parsedADR.negatives.map((n, idx) => (
                                                <li key={idx} className="flex items-start gap-2.5 text-xs text-zinc-300 leading-relaxed">
                                                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                                                    <span>{n}</span>
                                                </li>
                                            ))}
                                        </ul>
                                    </div>
                                </div>
                            </div>
                        )}
                    </>
                ) : (
                    <div className="flex-1 flex flex-col items-center justify-center text-center p-8 text-zinc-500 text-xs">
                        <BookOpen size={28} className="text-zinc-600 mb-2" />
                        <p className="font-semibold text-zinc-400">No Record Selected</p>
                        <p className="text-zinc-600 mt-1">Select an ADR from the sidebar to inspect its architecture decisions.</p>
                    </div>
                )}
            </div>

            {/* Draft ADR Modal */}
            {showDraftModal && (
                <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 animate-fade">
                    <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
                        <div>
                            <h3 className="text-sm font-bold text-white flex items-center gap-2">
                                <Sparkles size={16} className="text-blue-400" />
                                <span>Draft Architectural Decision Record</span>
                            </h3>
                            <p className="text-xs text-zinc-400 mt-1.5">
                                Auto-analyzes specification diffs, routes, and schemas to generate a structured MADR 3.0 document.
                            </p>
                        </div>

                        <div>
                            <label className="text-xs font-semibold text-zinc-300 mb-1.5 block">Decision Title (Optional):</label>
                            <input
                                value={customTitle}
                                onChange={e => setCustomTitle(e.target.value)}
                                placeholder="e.g., Introduce Telemetry & Code Analysis Routes"
                                className="w-full bg-[var(--surface-0)] border border-[var(--border-subtle)] rounded-xl p-2.5 text-xs text-white outline-none focus:border-blue-500/50 transition-colors"
                            />
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-2">
                            <button
                                onClick={() => setShowDraftModal(false)}
                                className="px-3.5 py-1.5 text-xs text-zinc-400 hover:text-zinc-200"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleGenerate}
                                disabled={generating}
                                className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md shadow-blue-600/20"
                            >
                                {generating ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
                                <span>Draft Record</span>
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
