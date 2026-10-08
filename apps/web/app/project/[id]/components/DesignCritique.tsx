'use client';

import React, { useState, useEffect } from 'react';
import api from '@/lib/api';
import {
    ShieldCheck, AlertTriangle, CheckCircle, RefreshCw, Loader2,
    Lock, Zap, LayoutGrid, Award, ArrowUpRight, Flame
} from 'lucide-react';

interface CritiqueItem {
    id: string;
    category: 'scalability' | 'security' | 'completeness' | 'maintainability';
    severity: 'critical' | 'warning' | 'suggestion';
    title: string;
    description: string;
    remediation: string;
    affected_items?: string[];
}

interface CritiqueResponse {
    overall_score: number;
    scalability_score: number;
    security_score: number;
    completeness_score: number;
    maintainability_score: number;
    executive_summary: string;
    critiques: CritiqueItem[];
}

export default function DesignCritique({ projectId }: { projectId: number }) {
    const [data, setData] = useState<CritiqueResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [refreshing, setRefreshing] = useState(false);

    const fetchCritique = async (isRefresh = false) => {
        if (!projectId || isNaN(projectId)) {
            setLoading(false);
            return;
        }
        if (isRefresh) setRefreshing(true);
        else setLoading(true);

        try {
            const res = await api.get(`/projects/${projectId}/critique`);
            setData(res.data);
        } catch {
            // fallback
        } finally {
            setLoading(false);
            setRefreshing(false);
        }
    };

    useEffect(() => {
        if (projectId && !isNaN(projectId)) {
            fetchCritique();
        }
    }, [projectId]);

    if (loading) {
        return (
            <div className="h-full flex flex-col items-center justify-center gap-3 bg-[var(--surface-0)]">
                <Loader2 size={24} className="animate-spin text-blue-500" />
                <p className="text-xs text-zinc-400">Auditing architecture scalability and security posture...</p>
            </div>
        );
    }

    if (!data) return null;

    const getScoreBadgeColor = (score: number) => {
        if (score >= 80) return 'text-emerald-400 border-emerald-500/25 bg-emerald-500/10';
        if (score >= 60) return 'text-amber-400 border-amber-500/25 bg-amber-500/10';
        return 'text-red-400 border-red-500/25 bg-red-500/10';
    };

    const getSeverityBadge = (sev: string) => {
        switch (sev) {
            case 'critical':
                return <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-red-500/15 text-red-400 border border-red-500/25">Critical</span>;
            case 'warning':
                return <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-amber-500/15 text-amber-400 border border-amber-500/25">Warning</span>;
            default:
                return <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-blue-500/15 text-blue-400 border border-blue-500/25">Suggestion</span>;
        }
    };

    return (
        <div className="flex flex-col h-full bg-[var(--surface-0)] overflow-y-auto p-8 max-w-5xl mx-auto w-full space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h2 className="text-xl font-bold text-white flex items-center gap-2.5">
                        <Award size={22} className="text-amber-400" />
                        <span>Design Critique & Posture Review</span>
                    </h2>
                    <p className="text-xs text-zinc-400 mt-1">
                        Automated structural grading across scalability, security, completeness, and maintainability.
                    </p>
                </div>

                <button
                    onClick={() => fetchCritique(true)}
                    disabled={refreshing}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-zinc-300 hover:text-white bg-[var(--surface-1)] border border-[var(--border-subtle)] hover:border-zinc-700 transition-all disabled:opacity-50"
                >
                    <RefreshCw size={12} className={refreshing ? 'animate-spin text-blue-400' : 'text-zinc-400'} />
                    <span>{refreshing ? 'Re-evaluating...' : 'Refresh Critique'}</span>
                </button>
            </div>

            {/* Scorecard Hero */}
            <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-6 grid grid-cols-1 md:grid-cols-5 gap-6 items-center">
                <div className="md:col-span-2 flex flex-col items-center justify-center text-center p-4 bg-[var(--surface-2)]/60 rounded-xl border border-[var(--border-subtle)]">
                    <span className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 mb-1">Architecture Score</span>
                    <div className="text-5xl font-black tracking-tight text-white my-1 flex items-baseline gap-1">
                        <span>{data.overall_score}</span>
                        <span className="text-lg text-zinc-500 font-normal">/100</span>
                    </div>
                    <span className={`px-2.5 py-0.5 rounded-full text-[11px] font-bold border mt-2 ${getScoreBadgeColor(data.overall_score)}`}>
                        {data.overall_score >= 80 ? 'Production Ready' : data.overall_score >= 60 ? 'Needs Hardening' : 'Critical Action Needed'}
                    </span>
                </div>

                <div className="md:col-span-3 grid grid-cols-2 gap-3">
                    <div className="p-3.5 bg-[var(--surface-2)] rounded-xl border border-[var(--border-subtle)] space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                            <span className="text-zinc-400 flex items-center gap-1.5"><Lock size={13} className="text-purple-400" /> Security</span>
                            <span className="font-bold text-white">{data.security_score}%</span>
                        </div>
                        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div className="h-full bg-purple-500 rounded-full" style={{ width: `${data.security_score}%` }} />
                        </div>
                    </div>

                    <div className="p-3.5 bg-[var(--surface-2)] rounded-xl border border-[var(--border-subtle)] space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                            <span className="text-zinc-400 flex items-center gap-1.5"><Zap size={13} className="text-amber-400" /> Scalability</span>
                            <span className="font-bold text-white">{data.scalability_score}%</span>
                        </div>
                        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div className="h-full bg-amber-500 rounded-full" style={{ width: `${data.scalability_score}%` }} />
                        </div>
                    </div>

                    <div className="p-3.5 bg-[var(--surface-2)] rounded-xl border border-[var(--border-subtle)] space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                            <span className="text-zinc-400 flex items-center gap-1.5"><LayoutGrid size={13} className="text-blue-400" /> Completeness</span>
                            <span className="font-bold text-white">{data.completeness_score}%</span>
                        </div>
                        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div className="h-full bg-blue-500 rounded-full" style={{ width: `${data.completeness_score}%` }} />
                        </div>
                    </div>

                    <div className="p-3.5 bg-[var(--surface-2)] rounded-xl border border-[var(--border-subtle)] space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                            <span className="text-zinc-400 flex items-center gap-1.5"><ShieldCheck size={13} className="text-emerald-400" /> Maintainability</span>
                            <span className="font-bold text-white">{data.maintainability_score}%</span>
                        </div>
                        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                            <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${data.maintainability_score}%` }} />
                        </div>
                    </div>
                </div>
            </div>

            {/* Executive Written Review */}
            <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-5 space-y-2">
                <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-500">Staff Architect Written Review</span>
                <p className="text-xs text-zinc-300 leading-relaxed">
                    {data.executive_summary}
                </p>
            </div>

            {/* Critique Findings List */}
            <div className="space-y-3">
                <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-zinc-200">
                        Detailed Findings & Remediation Steps ({data.critiques.length})
                    </span>
                </div>

                {data.critiques.map((c) => (
                    <div
                        key={c.id}
                        className="bg-[var(--surface-1)] border border-[var(--border-subtle)] hover:border-zinc-700 rounded-2xl p-5 space-y-3 transition-all"
                    >
                        <div className="flex items-start justify-between gap-4">
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <h4 className="text-sm font-semibold text-white">{c.title}</h4>
                                    {getSeverityBadge(c.severity)}
                                    <span className="text-[10px] font-mono uppercase text-zinc-500">[{c.category}]</span>
                                </div>
                                <p className="text-xs text-zinc-400 leading-relaxed">{c.description}</p>
                            </div>
                        </div>

                        {c.affected_items && c.affected_items.length > 0 && (
                            <div className="flex flex-wrap gap-1.5 pt-1">
                                {c.affected_items.map((item, idx) => (
                                    <span key={idx} className="text-[10px] font-mono px-2 py-0.5 rounded bg-[var(--surface-2)] text-zinc-300 border border-[var(--border-subtle)]">
                                        {item}
                                    </span>
                                ))}
                            </div>
                        )}

                        <div className="pt-2 border-t border-[var(--border-subtle)] flex items-start gap-2 bg-[var(--surface-2)]/40 p-3 rounded-xl">
                            <span className="text-[10px] uppercase font-bold text-blue-400 shrink-0 mt-0.5">Remediation:</span>
                            <span className="text-xs text-zinc-300">{c.remediation}</span>
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
