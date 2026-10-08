'use client';

import React, { useState, useEffect } from 'react';
import api from '@/lib/api';
import {
    FileText, Plus, GitCommit, Check, Loader2, Sparkles,
    Calendar, ArrowRight, BookOpen, ExternalLink, ShieldCheck
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

    const loadADRs = async () => {
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
        loadADRs();
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

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-3 bg-[var(--surface-0)]">
                <Loader2 size={24} className="animate-spin text-blue-500" />
                <p className="text-xs text-zinc-400">Loading Architecture Decision Records (docs/adr/)...</p>
            </div>
        );
    }

    return (
        <div className="flex h-full bg-[var(--surface-0)] overflow-hidden">
            {/* Sidebar list */}
            <div className="w-72 bg-[var(--surface-1)] border-r border-[var(--border-subtle)] flex flex-col shrink-0">
                <div className="p-4 border-b border-[var(--border-subtle)] flex items-center justify-between">
                    <div>
                        <h3 className="text-xs font-bold text-white flex items-center gap-1.5">
                            <BookOpen size={14} className="text-blue-400" />
                            <span>Decision Records</span>
                        </h3>
                        <p className="text-[10px] text-zinc-500 font-mono mt-0.5">docs/adr/</p>
                    </div>

                    <button
                        onClick={() => setShowDraftModal(true)}
                        className="flex items-center gap-1 px-2.5 py-1 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-[11px] font-semibold transition-all shadow-sm"
                    >
                        <Plus size={12} />
                        <span>Draft ADR</span>
                    </button>
                </div>

                <div className="flex-1 overflow-y-auto p-2 space-y-1">
                    {adrs.length === 0 ? (
                        <div className="p-6 text-center text-zinc-500 text-xs">
                            No decision records drafted yet. Click "Draft ADR" to document architectural changes.
                        </div>
                    ) : (
                        adrs.map(a => {
                            const isSelected = selectedAdr?.id === a.id;
                            return (
                                <button
                                    key={a.id}
                                    onClick={() => setSelectedAdr(a)}
                                    className={`w-full flex flex-col p-3 rounded-xl text-left transition-all ${
                                        isSelected
                                            ? 'bg-blue-600/15 border border-blue-500/30 text-white'
                                            : 'text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)] border border-transparent'
                                    }`}
                                >
                                    <div className="flex items-center justify-between w-full mb-1">
                                        <span className="text-[10px] font-mono text-zinc-500">{a.file_path.split('/').pop()}</span>
                                        {a.committed ? (
                                            <span className="text-[9px] px-1.5 py-0.2 rounded font-bold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                                Committed
                                            </span>
                                        ) : (
                                            <span className="text-[9px] px-1.5 py-0.2 rounded font-bold uppercase bg-amber-500/10 text-amber-400 border border-amber-500/20">
                                                Draft
                                            </span>
                                        )}
                                    </div>
                                    <span className="text-xs font-semibold truncate text-zinc-200">{a.title}</span>
                                </button>
                            );
                        })
                    )}
                </div>
            </div>

            {/* Detail Viewer */}
            <div className="flex-1 flex flex-col overflow-hidden bg-[var(--surface-0)]">
                {selectedAdr ? (
                    <>
                        <div className="px-6 py-4 border-b border-[var(--border-subtle)] bg-[var(--surface-1)] flex items-center justify-between shrink-0">
                            <div>
                                <div className="flex items-center gap-2">
                                    <h3 className="text-sm font-bold text-white">{selectedAdr.title}</h3>
                                    <span className="text-[10px] font-mono text-zinc-500">{selectedAdr.file_path}</span>
                                </div>
                                <div className="flex items-center gap-3 text-[11px] text-zinc-400 mt-0.5">
                                    <span>Status: <strong className="text-emerald-400 capitalize">{selectedAdr.status}</strong></span>
                                    <span>•</span>
                                    <span>Format: MADR 3.0</span>
                                </div>
                            </div>

                            <button
                                onClick={() => handleCommit(selectedAdr)}
                                disabled={committing || selectedAdr.committed}
                                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all shadow-sm ${
                                    selectedAdr.committed
                                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 cursor-default'
                                        : 'bg-blue-600 hover:bg-blue-500 text-white shadow-blue-600/20'
                                }`}
                            >
                                {committing ? <Loader2 size={13} className="animate-spin" /> : selectedAdr.committed ? <Check size={13} /> : <GitCommit size={13} />}
                                <span>{selectedAdr.committed ? 'Committed to Git' : 'Commit to docs/adr/'}</span>
                            </button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-8 max-w-4xl font-mono text-xs text-zinc-200 leading-relaxed whitespace-pre-wrap">
                            {selectedAdr.content}
                        </div>
                    </>
                ) : (
                    <div className="flex-1 flex items-center justify-center text-center p-8 text-zinc-500 text-xs">
                        Select an ADR from the left panel to review its contents.
                    </div>
                )}
            </div>

            {/* Draft ADR Modal */}
            {showDraftModal && (
                <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                    <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl w-full max-w-md p-6 space-y-4 shadow-2xl">
                        <div>
                            <h3 className="text-sm font-bold text-white">Draft Architectural Decision Record</h3>
                            <p className="text-xs text-zinc-400 mt-1">
                                Auto-compares your current specification with the previous snapshot to record the rationale for changes.
                            </p>
                        </div>

                        <div>
                            <label className="text-xs font-semibold text-zinc-300 mb-1 block">Decision Title (Optional):</label>
                            <input
                                value={customTitle}
                                onChange={e => setCustomTitle(e.target.value)}
                                placeholder="e.g., Introduce Multi-Tenant Stripe Billing"
                                className="w-full bg-[var(--surface-0)] border border-[var(--border-subtle)] rounded-xl p-2.5 text-xs text-white outline-none"
                            />
                        </div>

                        <div className="flex items-center justify-end gap-2 pt-2">
                            <button
                                onClick={() => setShowDraftModal(false)}
                                className="px-3 py-1.5 text-xs text-zinc-400 hover:text-zinc-200"
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
