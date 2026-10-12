'use client';

import React, { useState, useEffect, useRef } from 'react';
import {
    Database, Download, Copy, CheckCheck, ZoomIn, ZoomOut,
    RotateCcw, Code2, FileCode, Share2, Loader2, Sparkles,
    Layers, GitFork
} from 'lucide-react';
import { fetchERD } from '@/lib/api';

interface ERDData {
    mermaid: string;
    dbml: string;
    openapi: any;
    stats: {
        tables_count: number;
        relations_count: number;
        endpoints_count: number;
    };
}

export default function ERDView({
    projectId,
    onShowToast
}: {
    projectId: number;
    onShowToast: (msg: string, ok?: boolean) => void;
}) {
    const [loading, setLoading] = useState(true);
    const [erdData, setERDData] = useState<ERDData | null>(null);
    const [activeTab, setActiveTab] = useState<'visual' | 'mermaid' | 'dbml' | 'openapi'>('visual');
    const [copied, setCopied] = useState<string | null>(null);

    // Zoom & pan controls for visual ERD
    const [zoom, setZoom] = useState(1);
    const containerRef = useRef<HTMLDivElement>(null);
    const [svgContent, setSvgContent] = useState<string>('');
    const [renderError, setRenderError] = useState<string | null>(null);

    useEffect(() => {
        let mounted = true;
        const load = async () => {
            setLoading(true);
            try {
                const data = await fetchERD(projectId);
                if (mounted) {
                    setERDData(data);
                }
            } catch {
                if (mounted) onShowToast('Failed to load ERD specification', false);
            } finally {
                if (mounted) setLoading(false);
            }
        };
        if (projectId && !isNaN(projectId)) load();
        else setLoading(false);
        return () => { mounted = false; };
    }, [projectId]);

    // Render Mermaid to SVG dynamically
    useEffect(() => {
        let active = true;
        if (!erdData?.mermaid) return;

        const renderDiagram = async () => {
            try {
                setRenderError(null);
                const mermaidModule = await import('mermaid');
                const mermaid = mermaidModule.default;
                mermaid.initialize({
                    startOnLoad: false,
                    theme: 'dark',
                    themeVariables: {
                        darkMode: true,
                        primaryColor: '#3b82f6',
                        primaryTextColor: '#f8fafc',
                        primaryBorderColor: '#60a5fa',
                        lineColor: '#94a3b8',
                        secondaryColor: '#1e293b',
                        tertiaryColor: '#0f172a'
                    },
                    er: {
                        useMaxWidth: false
                    }
                });

                const id = `mermaid-erd-${Date.now()}`;
                const { svg } = await mermaid.render(id, erdData.mermaid);
                if (active) {
                    setSvgContent(svg);
                }
            } catch (err: any) {
                console.error('Mermaid render error:', err);
                if (active) {
                    setRenderError(err?.message || 'Failed to render ER diagram');
                }
            }
        };

        renderDiagram();
        return () => { active = false; };
    }, [erdData?.mermaid]);

    const handleCopy = (text: string, label: string) => {
        navigator.clipboard.writeText(text);
        setCopied(label);
        setTimeout(() => setCopied(null), 2000);
        onShowToast(`Copied ${label} to clipboard`);
    };

    const handleDownload = (content: string, filename: string, type: string) => {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        onShowToast(`Downloaded ${filename}`);
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-12 text-zinc-500">
                <Loader2 size={24} className="animate-spin mb-3 text-cyan-400" />
                <p className="text-xs font-mono">Generating auto-layout ER diagram & schema exports...</p>
            </div>
        );
    }

    if (!erdData) {
        return (
            <div className="p-12 text-center text-zinc-500 font-mono text-xs">
                No schema data available to generate ERD. Add tables in Data Models tab first.
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full overflow-hidden bg-[var(--surface-0)]">
            {/* Top Toolbar */}
            <div className="h-12 px-4 border-b border-[var(--border-subtle)] bg-[var(--surface-1)] flex items-center justify-between shrink-0">
                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                        <Database size={15} className="text-cyan-400" />
                        <span className="text-xs font-semibold text-zinc-200">Entity-Relationship Diagram</span>
                    </div>

                    {/* Stats pills */}
                    <div className="hidden sm:flex items-center gap-2 text-[10px] font-mono text-zinc-400">
                        <span className="px-2 py-0.5 rounded-full bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                            {erdData.stats.tables_count} Tables
                        </span>
                        <span className="px-2 py-0.5 rounded-full bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                            {erdData.stats.relations_count} Relations
                        </span>
                        <span className="px-2 py-0.5 rounded-full bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                            {erdData.stats.endpoints_count} Endpoints
                        </span>
                    </div>
                </div>

                {/* Tab Switcher & Export Actions */}
                <div className="flex items-center gap-2">
                    <div className="flex items-center gap-1 p-0.5 rounded-xl bg-[var(--surface-2)] border border-[var(--border-subtle)] text-xs">
                        <button
                            onClick={() => setActiveTab('visual')}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
                                activeTab === 'visual' ? 'bg-zinc-800 text-cyan-300' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            Visual
                        </button>
                        <button
                            onClick={() => setActiveTab('mermaid')}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
                                activeTab === 'mermaid' ? 'bg-zinc-800 text-zinc-200' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            Mermaid
                        </button>
                        <button
                            onClick={() => setActiveTab('dbml')}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
                                activeTab === 'dbml' ? 'bg-zinc-800 text-zinc-200' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            DBML
                        </button>
                        <button
                            onClick={() => setActiveTab('openapi')}
                            className={`px-2.5 py-1 rounded-lg font-medium transition-colors ${
                                activeTab === 'openapi' ? 'bg-zinc-800 text-zinc-200' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            OpenAPI
                        </button>
                    </div>

                    {/* Quick export buttons based on tab */}
                    {activeTab === 'visual' && (
                        <div className="flex items-center gap-1 border-l border-zinc-800 pl-2">
                            <button
                                onClick={() => setZoom(z => Math.max(0.4, z - 0.15))}
                                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)] transition-colors"
                                title="Zoom Out"
                            >
                                <ZoomOut size={13} />
                            </button>
                            <span className="text-[10px] font-mono text-zinc-400 w-10 text-center">
                                {Math.round(zoom * 100)}%
                            </span>
                            <button
                                onClick={() => setZoom(z => Math.min(2.5, z + 0.15))}
                                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)] transition-colors"
                                title="Zoom In"
                            >
                                <ZoomIn size={13} />
                            </button>
                            <button
                                onClick={() => setZoom(1)}
                                className="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)] transition-colors"
                                title="Reset Zoom"
                            >
                                <RotateCcw size={13} />
                            </button>
                        </div>
                    )}

                    {activeTab === 'mermaid' && (
                        <button
                            onClick={() => handleCopy(erdData.mermaid, 'Mermaid')}
                            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--surface-2)] hover:bg-[var(--surface-3)] text-zinc-300 text-xs border border-zinc-700 transition-colors"
                        >
                            {copied === 'Mermaid' ? <CheckCheck size={12} className="text-emerald-400" /> : <Copy size={12} />}
                            <span>Copy</span>
                        </button>
                    )}

                    {activeTab === 'dbml' && (
                        <div className="flex items-center gap-1">
                            <button
                                onClick={() => handleCopy(erdData.dbml, 'DBML')}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--surface-2)] hover:bg-[var(--surface-3)] text-zinc-300 text-xs border border-zinc-700 transition-colors"
                            >
                                {copied === 'DBML' ? <CheckCheck size={12} className="text-emerald-400" /> : <Copy size={12} />}
                                <span>Copy</span>
                            </button>
                            <button
                                onClick={() => handleDownload(erdData.dbml, 'schema.dbml', 'text/plain')}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-colors"
                            >
                                <Download size={12} />
                                <span>Export .dbml</span>
                            </button>
                        </div>
                    )}

                    {activeTab === 'openapi' && (
                        <div className="flex items-center gap-1">
                            <button
                                onClick={() => handleCopy(JSON.stringify(erdData.openapi, null, 2), 'OpenAPI')}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[var(--surface-2)] hover:bg-[var(--surface-3)] text-zinc-300 text-xs border border-zinc-700 transition-colors"
                            >
                                {copied === 'OpenAPI' ? <CheckCheck size={12} className="text-emerald-400" /> : <Copy size={12} />}
                                <span>Copy</span>
                            </button>
                            <button
                                onClick={() => handleDownload(JSON.stringify(erdData.openapi, null, 2), 'openapi.json', 'application/json')}
                                className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-medium transition-colors"
                            >
                                <Download size={12} />
                                <span>Export JSON</span>
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 overflow-auto relative">
                {activeTab === 'visual' && (
                    <div
                        ref={containerRef}
                        className="w-full h-full min-h-[500px] overflow-auto flex items-center justify-center p-8 bg-[radial-gradient(#1e293b_1px,transparent_1px)] [background-size:16px_16px]"
                    >
                        {renderError ? (
                            <div className="p-6 rounded-xl bg-red-950/20 border border-red-800/40 text-center max-w-md">
                                <p className="text-xs text-red-300 font-mono mb-2">Mermaid Render Error</p>
                                <p className="text-[11px] text-zinc-400">{renderError}</p>
                                <button
                                    onClick={() => setActiveTab('mermaid')}
                                    className="mt-3 px-3 py-1 bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 rounded-lg"
                                >
                                    Inspect Mermaid Code
                                </button>
                            </div>
                        ) : svgContent ? (
                            <div
                                style={{ transform: `scale(${zoom})`, transformOrigin: 'center center', transition: 'transform 0.15s ease-out' }}
                                dangerouslySetInnerHTML={{ __html: svgContent }}
                                className="flex items-center justify-center selection:bg-none"
                            />
                        ) : (
                            <div className="flex items-center gap-2 text-zinc-500 text-xs font-mono">
                                <Loader2 size={16} className="animate-spin text-cyan-400" />
                                <span>Rendering diagram...</span>
                            </div>
                        )}
                    </div>
                )}

                {activeTab === 'mermaid' && (
                    <div className="p-6 h-full overflow-auto">
                        <div className="p-4 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)] font-mono text-xs leading-relaxed text-zinc-200">
                            <pre className="whitespace-pre-wrap">{erdData.mermaid}</pre>
                        </div>
                    </div>
                )}

                {activeTab === 'dbml' && (
                    <div className="p-6 h-full overflow-auto">
                        <div className="p-4 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)] font-mono text-xs leading-relaxed text-blue-200">
                            <pre className="whitespace-pre-wrap">{erdData.dbml}</pre>
                        </div>
                    </div>
                )}

                {activeTab === 'openapi' && (
                    <div className="p-6 h-full overflow-auto">
                        <div className="p-4 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)] font-mono text-xs leading-relaxed text-emerald-200">
                            <pre className="whitespace-pre-wrap">{JSON.stringify(erdData.openapi, null, 2)}</pre>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
