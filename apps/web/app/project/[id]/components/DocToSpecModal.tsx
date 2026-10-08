'use client';

import React, { useState } from 'react';
import api from '@/lib/api';
import {
    FileText, Image as ImageIcon, Sparkles, X, Loader2,
    Check, ArrowRight, Database, Globe, LayoutPanelTop, CheckCircle2
} from 'lucide-react';

interface DocToSpecModalProps {
    projectId: number;
    isOpen: boolean;
    onClose: () => void;
    onSpecApplied: () => void;
    onShowToast: (msg: string, isSuccess?: boolean) => void;
}

export default function DocToSpecModal({
    projectId,
    isOpen,
    onClose,
    onSpecApplied,
    onShowToast
}: DocToSpecModalProps) {
    const [mode, setMode] = useState<'prd' | 'wireframe'>('prd');
    const [prdText, setPrdText] = useState('');
    const [screenName, setScreenName] = useState('Dashboard');
    const [imagePreview, setImagePreview] = useState<string | null>(null);
    const [extracted, setExtracted] = useState<any>(null);
    const [summary, setSummary] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [applying, setApplying] = useState(false);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        if (mode === 'wireframe') {
            const reader = new FileReader();
            reader.onload = () => {
                setImagePreview(reader.result as string);
            };
            reader.readAsDataURL(file);
        } else {
            const reader = new FileReader();
            reader.onload = () => {
                setPrdText(reader.result as string);
            };
            reader.readAsText(file);
        }
    };

    const handleExtract = async () => {
        setLoading(true);
        setExtracted(null);
        setSummary(null);

        try {
            if (mode === 'prd') {
                if (!prdText.trim()) return;
                const res = await api.post(`/projects/${projectId}/spec-from-doc`, {
                    content: prdText,
                    doc_type: 'prd'
                });
                setExtracted(res.data.extracted);
                setSummary(res.data.summary);
            } else {
                if (!imagePreview) return;
                const res = await api.post(`/projects/${projectId}/spec-from-wireframe`, {
                    image_base64: imagePreview,
                    screen_name: screenName
                });
                setExtracted(res.data.extracted);
                setSummary(res.data.summary);
            }
        } catch (err: any) {
            onShowToast(err.response?.data?.detail || 'Extraction failed', false);
        } finally {
            setLoading(false);
        }
    };

    const handleApply = async () => {
        if (!extracted) return;
        setApplying(true);
        try {
            const res = await api.post(`/projects/${projectId}/spec-from-doc/apply`, {
                extracted
            });
            onShowToast(`Applied to spec: ${res.data.applied.features} features, ${res.data.applied.schemas} tables, ${res.data.applied.endpoints} routes!`);
            onSpecApplied();
            onClose();
        } catch (err: any) {
            onShowToast(err.response?.data?.detail || 'Failed to apply extracted spec', false);
        } finally {
            setApplying(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl w-full max-w-4xl flex flex-col max-h-[90vh] shadow-2xl overflow-hidden">
                {/* Header */}
                <div className="px-6 py-4 border-b border-[var(--border-subtle)] flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-xl bg-purple-600/15 border border-purple-500/25 flex items-center justify-center text-purple-400">
                            <Sparkles size={16} />
                        </div>
                        <div>
                            <h3 className="text-sm font-bold text-white">PRD & Wireframe to Spec</h3>
                            <p className="text-xs text-zinc-400">Convert product requirements docs or UI screenshots into architecture entities.</p>
                        </div>
                    </div>

                    <button onClick={onClose} className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-[var(--surface-2)]">
                        <X size={16} />
                    </button>
                </div>

                {/* Mode Selector */}
                <div className="px-6 py-2.5 bg-[var(--surface-2)] border-b border-[var(--border-subtle)] flex items-center justify-between shrink-0">
                    <div className="flex items-center bg-[var(--surface-1)] p-0.5 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold">
                        <button
                            onClick={() => { setMode('prd'); setExtracted(null); }}
                            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all ${
                                mode === 'prd' ? 'bg-purple-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            <FileText size={12} />
                            <span>Product Doc (PRD)</span>
                        </button>
                        <button
                            onClick={() => { setMode('wireframe'); setExtracted(null); }}
                            className={`flex items-center gap-1.5 px-3 py-1 rounded-lg transition-all ${
                                mode === 'wireframe' ? 'bg-purple-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            <ImageIcon size={12} />
                            <span>Wireframe / Screenshot</span>
                        </button>
                    </div>

                    <input
                        type="file"
                        onChange={handleFileChange}
                        accept={mode === 'wireframe' ? 'image/*' : '.md,.txt,.json'}
                        className="text-xs text-zinc-400 file:mr-2 file:py-1 file:px-2.5 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-zinc-800 file:text-zinc-300 hover:file:bg-zinc-700"
                    />
                </div>

                {/* Main Body */}
                <div className="flex-1 overflow-y-auto p-6 space-y-5">
                    {!extracted ? (
                        <div className="space-y-4">
                            {mode === 'prd' ? (
                                <div>
                                    <label className="text-xs font-semibold text-zinc-300 mb-1.5 block">
                                        Paste PRD / Product Requirements / User Stories:
                                    </label>
                                    <textarea
                                        value={prdText}
                                        onChange={e => setPrdText(e.target.value)}
                                        placeholder={`# Product Overview\n\nWe need a customer support portal with ticket tracking, agent assignment, and SLA alerts...`}
                                        className="w-full h-72 bg-[var(--surface-0)] border border-[var(--border-subtle)] focus:border-purple-500/50 rounded-xl p-4 text-zinc-200 text-xs font-mono resize-none outline-none leading-relaxed"
                                    />
                                </div>
                            ) : (
                                <div className="space-y-4">
                                    <div>
                                        <label className="text-xs font-semibold text-zinc-300 mb-1 block">Screen / Feature Name:</label>
                                        <input
                                            value={screenName}
                                            onChange={e => setScreenName(e.target.value)}
                                            placeholder="e.g. AnalyticsDashboard"
                                            className="w-full bg-[var(--surface-0)] border border-[var(--border-subtle)] rounded-xl p-2.5 text-xs text-white outline-none"
                                        />
                                    </div>

                                    {imagePreview ? (
                                        <div className="p-4 bg-[var(--surface-0)] rounded-xl border border-[var(--border-subtle)] text-center">
                                            <img src={imagePreview} alt="Wireframe Preview" className="max-h-60 mx-auto rounded-lg object-contain shadow-lg" />
                                        </div>
                                    ) : (
                                        <div className="h-48 border-2 border-dashed border-[var(--border-subtle)] rounded-xl flex flex-col items-center justify-center text-zinc-500 text-xs gap-2">
                                            <ImageIcon size={28} />
                                            <span>Upload a wireframe image or UI screenshot above</span>
                                        </div>
                                    )}
                                </div>
                            )}

                            <button
                                onClick={handleExtract}
                                disabled={loading || (mode === 'prd' ? !prdText.trim() : !imagePreview)}
                                className="w-full py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 disabled:opacity-40 text-white text-xs font-bold transition-all shadow-lg shadow-purple-600/20 flex items-center justify-center gap-2"
                            >
                                {loading ? <Loader2 size={14} className="animate-spin" /> : <Sparkles size={14} />}
                                <span>Synthesize Canonical Architecture Spec</span>
                            </button>
                        </div>
                    ) : (
                        <div className="space-y-5 animate-in fade-in duration-200">
                            {summary && (
                                <div className="p-3.5 bg-purple-500/10 border border-purple-500/20 rounded-xl text-xs text-purple-300">
                                    {summary}
                                </div>
                            )}

                            {/* Extracted Breakdown Grid */}
                            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                                {/* Features */}
                                <div className="bg-[var(--surface-0)] p-4 rounded-xl border border-[var(--border-subtle)] space-y-2">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-amber-400">Features ({extracted.features?.length || 0})</span>
                                    <div className="space-y-1">
                                        {extracted.features?.map((f: any, i: number) => (
                                            <div key={i} className="text-xs text-zinc-300 font-medium truncate">• {f.name}</div>
                                        ))}
                                    </div>
                                </div>

                                {/* Schemas */}
                                <div className="bg-[var(--surface-0)] p-4 rounded-xl border border-[var(--border-subtle)] space-y-2">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-blue-400">Tables ({extracted.schemas?.length || 0})</span>
                                    <div className="space-y-1">
                                        {extracted.schemas?.map((s: any, i: number) => (
                                            <div key={i} className="text-xs font-mono text-zinc-300 truncate">
                                                • {s.table_name} <span className="text-zinc-500">({s.fields?.length || 0} cols)</span>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Endpoints */}
                                <div className="bg-[var(--surface-0)] p-4 rounded-xl border border-[var(--border-subtle)] space-y-2">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-purple-400">Routes ({extracted.endpoints?.length || 0})</span>
                                    <div className="space-y-1">
                                        {extracted.endpoints?.map((e: any, i: number) => (
                                            <div key={i} className="text-xs font-mono text-zinc-300 truncate">
                                                • {e.method} {e.route}
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}
                </div>

                {/* Footer Actions */}
                <div className="px-6 py-4 bg-[var(--surface-1)] border-t border-[var(--border-subtle)] flex items-center justify-between shrink-0">
                    <button onClick={onClose} className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200">
                        Cancel
                    </button>

                    {extracted && (
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setExtracted(null)}
                                className="px-3 py-1.5 rounded-xl text-xs text-zinc-400 hover:text-zinc-200"
                            >
                                Re-edit Input
                            </button>
                            <button
                                onClick={handleApply}
                                disabled={applying}
                                className="flex items-center gap-2 px-4 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-xl shadow-md shadow-purple-600/20"
                            >
                                {applying ? <Loader2 size={13} className="animate-spin" /> : <CheckCircle2 size={13} />}
                                <span>Apply to Project Spec</span>
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
