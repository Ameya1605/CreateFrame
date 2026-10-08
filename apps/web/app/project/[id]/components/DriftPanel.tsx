'use client';

import React, { useState, useEffect } from 'react';
import {
    ShieldAlert, CheckCircle2, AlertTriangle, ArrowRightLeft,
    RefreshCw, GitPullRequest, GitBranch, Save, Terminal,
    Layers, Check, Trash2, ArrowUpRight, Copy, CheckCheck, Loader2
} from 'lucide-react';
import {
    fetchDrift, syncDrift, fetchProjectSettings,
    updateProjectSettings, checkPRDrift
} from '@/lib/api';

interface DriftItem {
    layer: 'table' | 'route' | 'component';
    key: string;
    status: 'in_sync' | 'spec_only' | 'scan_only' | 'conflict' | 'deleted_in_code';
    details: {
        spec_summary?: string;
        scan_summary?: string;
        columns_only_in_spec?: string[];
        columns_only_in_code?: string[];
        conflict_reason?: string;
    };
}

interface DriftReport {
    summary: {
        is_clean: boolean;
        total_items: number;
        drift_count: number;
        in_sync_count: number;
        spec_only_count: number;
        scan_only_count: number;
        conflicts_count: number;
        deleted_in_code_count: number;
    };
    items: DriftItem[];
    snapshot_id?: number | null;
    last_synced_at?: string | null;
}

export default function DriftPanel({
    projectId,
    onSpecUpdated,
    onShowToast
}: {
    projectId: number;
    onSpecUpdated?: () => void;
    onShowToast: (msg: string, ok?: boolean) => void;
}) {
    const [loading, setLoading] = useState(true);
    const [syncing, setSyncing] = useState(false);
    const [report, setReport] = useState<DriftReport | null>(null);
    const [filter, setFilter] = useState<'all' | 'conflicts' | 'code_only' | 'spec_only'>('all');

    // Governance settings
    const [targetBranch, setTargetBranch] = useState('main');
    const [governanceMode, setGovernanceMode] = useState<'direct' | 'pr'>('direct');
    const [savingSettings, setSavingSettings] = useState(false);

    // PR Check Simulation
    const [checkingPR, setCheckingPR] = useState(false);
    const [prCheckResult, setPRCheckResult] = useState<string | null>(null);
    const [copiedComment, setCopiedComment] = useState(false);

    const loadData = async () => {
        setLoading(true);
        try {
            const [driftRes, settingsRes] = await Promise.all([
                fetchDrift(projectId),
                fetchProjectSettings(projectId).catch(() => ({ target_branch: 'main', governance_mode: 'direct' }))
            ]);
            setReport(driftRes);
            if (settingsRes) {
                setTargetBranch(settingsRes.target_branch || 'main');
                setGovernanceMode(settingsRes.governance_mode || 'direct');
            }
        } catch {
            onShowToast('Failed to load drift status', false);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (projectId) loadData();
    }, [projectId]);

    const handleSyncSingle = async (item: DriftItem, action: 'accept_code' | 'delete') => {
        setSyncing(true);
        try {
            await syncDrift(projectId, [{ layer: item.layer, key: item.key, action }]);
            onShowToast(`Resolved ${item.key} (${action.replace('_', ' ')})`);
            await loadData();
            if (onSpecUpdated) onSpecUpdated();
        } catch {
            onShowToast('Failed to apply sync resolution', false);
        } finally {
            setSyncing(false);
        }
    };

    const handleSyncAllClean = async () => {
        setSyncing(true);
        try {
            const res = await syncDrift(projectId);
            onShowToast(res.message || 'Auto-synced all matching components');
            await loadData();
            if (onSpecUpdated) onSpecUpdated();
        } catch {
            onShowToast('Failed to sync changes', false);
        } finally {
            setSyncing(false);
        }
    };

    const handleSaveSettings = async () => {
        setSavingSettings(true);
        try {
            await updateProjectSettings(projectId, {
                target_branch: targetBranch,
                governance_mode: governanceMode
            });
            onShowToast('Governance & branch settings saved');
        } catch {
            onShowToast('Failed to save settings', false);
        } finally {
            setSavingSettings(false);
        }
    };

    const handleTestPRCheck = async () => {
        setCheckingPR(true);
        try {
            const res = await checkPRDrift(projectId);
            setPRCheckResult(res.comment_markdown);
            onShowToast('PR Drift Check completed');
        } catch {
            onShowToast('Failed to run PR drift check', false);
        } finally {
            setCheckingPR(false);
        }
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center justify-center h-full p-12 text-zinc-500">
                <Loader2 size={24} className="animate-spin mb-3 text-orange-400" />
                <p className="text-xs font-mono">Comparing spec.json against codebase AST scan...</p>
            </div>
        );
    }

    const summary = report?.summary;
    const items = report?.items || [];
    const filteredItems = items.filter(item => {
        if (filter === 'conflicts') return item.status === 'conflict';
        if (filter === 'code_only') return item.status === 'scan_only';
        if (filter === 'spec_only') return item.status === 'spec_only';
        return true;
    });

    return (
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {/* Top Status Card */}
            <div className={`p-6 rounded-2xl border ${
                summary?.is_clean
                    ? 'bg-emerald-950/20 border-emerald-800/40'
                    : 'bg-orange-950/20 border-orange-800/40'
            }`}>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="flex items-start gap-3">
                        <div className={`p-2.5 rounded-xl ${
                            summary?.is_clean ? 'bg-emerald-500/10 text-emerald-400' : 'bg-orange-500/10 text-orange-400'
                        }`}>
                            {summary?.is_clean ? <CheckCircle2 size={24} /> : <ShieldAlert size={24} />}
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-zinc-100 flex items-center gap-2">
                                {summary?.is_clean ? 'Spec & Code In Sync' : 'Architectural Drift Detected'}
                                <span className={`text-[11px] px-2 py-0.5 rounded-full font-mono font-medium ${
                                    summary?.is_clean
                                        ? 'bg-emerald-500/20 text-emerald-300'
                                        : 'bg-orange-500/20 text-orange-300'
                                }`}>
                                    {summary?.drift_count || 0} drift item{summary?.drift_count !== 1 ? 's' : ''}
                                </span>
                            </h2>
                            <p className="text-xs text-zinc-400 mt-1">
                                {summary?.is_clean
                                    ? 'Your spec.json matches routes and ORM models in your GitHub repository.'
                                    : 'Codebase changes differ from active spec.json. Resolve conflicts or merge to keep your spec true.'}
                                {report?.last_synced_at && (
                                    <span className="block mt-0.5 text-zinc-500 font-mono text-[10px]">
                                        Last Synced: {new Date(report.last_synced_at).toLocaleString()} (Snapshot #{report.snapshot_id})
                                    </span>
                                )}
                            </p>
                        </div>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={loadData}
                            disabled={loading || syncing}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-zinc-700 bg-[var(--surface-2)] hover:bg-[var(--surface-3)] text-xs text-zinc-300 transition-colors"
                        >
                            <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                            <span>Rescan</span>
                        </button>
                        {(!summary?.is_clean) && (
                            <button
                                onClick={handleSyncAllClean}
                                disabled={syncing}
                                className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-orange-600 hover:bg-orange-500 text-xs font-semibold text-white shadow-md shadow-orange-600/20 transition-all"
                            >
                                {syncing ? <Loader2 size={13} className="animate-spin" /> : <ArrowRightLeft size={13} />}
                                <span>Sync All Clean</span>
                            </button>
                        )}
                    </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mt-5 pt-5 border-t border-zinc-800/60">
                    <div className="p-3 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)]">
                        <div className="text-[10px] text-zinc-500 uppercase tracking-wide font-mono">In Sync</div>
                        <div className="text-xl font-bold text-emerald-400 mt-1">{summary?.in_sync_count ?? 0}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)]">
                        <div className="text-[10px] text-zinc-500 uppercase tracking-wide font-mono">Code Only</div>
                        <div className="text-xl font-bold text-amber-400 mt-1">{summary?.scan_only_count ?? 0}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)]">
                        <div className="text-[10px] text-zinc-500 uppercase tracking-wide font-mono">Spec Only</div>
                        <div className="text-xl font-bold text-blue-400 mt-1">{summary?.spec_only_count ?? 0}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)]">
                        <div className="text-[10px] text-zinc-500 uppercase tracking-wide font-mono">Conflicts</div>
                        <div className="text-xl font-bold text-red-400 mt-1">{summary?.conflicts_count ?? 0}</div>
                    </div>
                    <div className="p-3 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)]">
                        <div className="text-[10px] text-zinc-500 uppercase tracking-wide font-mono">Deleted in Code</div>
                        <div className="text-xl font-bold text-zinc-400 mt-1">{summary?.deleted_in_code_count ?? 0}</div>
                    </div>
                </div>
            </div>

            {/* Filter Tabs & Detailed Drift List */}
            <div className="space-y-4">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5 p-1 rounded-xl bg-[var(--surface-1)] border border-[var(--border-subtle)] text-xs">
                        <button
                            onClick={() => setFilter('all')}
                            className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                                filter === 'all' ? 'bg-zinc-800 text-white' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            All ({items.length})
                        </button>
                        <button
                            onClick={() => setFilter('conflicts')}
                            className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                                filter === 'conflicts' ? 'bg-red-500/20 text-red-300' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            Conflicts ({summary?.conflicts_count || 0})
                        </button>
                        <button
                            onClick={() => setFilter('code_only')}
                            className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                                filter === 'code_only' ? 'bg-amber-500/20 text-amber-300' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            Code Only ({summary?.scan_only_count || 0})
                        </button>
                        <button
                            onClick={() => setFilter('spec_only')}
                            className={`px-3 py-1 rounded-lg font-medium transition-colors ${
                                filter === 'spec_only' ? 'bg-blue-500/20 text-blue-300' : 'text-zinc-400 hover:text-zinc-200'
                            }`}
                        >
                            Spec Only ({summary?.spec_only_count || 0})
                        </button>
                    </div>
                </div>

                {filteredItems.length === 0 ? (
                    <div className="p-12 text-center rounded-2xl bg-[var(--surface-1)] border border-[var(--border-subtle)]">
                        <CheckCircle2 size={32} className="mx-auto text-emerald-400 mb-2 opacity-80" />
                        <p className="text-xs text-zinc-300 font-medium">No items matching current filter</p>
                    </div>
                ) : (
                    <div className="space-y-2.5">
                        {filteredItems.map((item, idx) => {
                            const isConflict = item.status === 'conflict';
                            const isScanOnly = item.status === 'scan_only';
                            const isSpecOnly = item.status === 'spec_only';
                            const isDeleted = item.status === 'deleted_in_code';
                            const isInSync = item.status === 'in_sync';

                            return (
                                <div
                                    key={`${item.layer}-${item.key}-${idx}`}
                                    className={`p-4 rounded-xl border transition-all ${
                                        isConflict
                                            ? 'bg-red-950/15 border-red-900/40'
                                            : isScanOnly
                                            ? 'bg-amber-950/15 border-amber-900/30'
                                            : isSpecOnly
                                            ? 'bg-blue-950/15 border-blue-900/30'
                                            : isDeleted
                                            ? 'bg-zinc-900/60 border-zinc-800'
                                            : 'bg-[var(--surface-1)] border-[var(--border-subtle)] opacity-80'
                                    }`}
                                >
                                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                                        <div className="flex items-center gap-3">
                                            <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded bg-zinc-800 text-zinc-300 border border-zinc-700">
                                                {item.layer}
                                            </span>
                                            <div>
                                                <div className="flex items-center gap-2">
                                                    <span className="font-mono text-xs font-semibold text-zinc-100">{item.key}</span>
                                                    {isConflict && (
                                                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-red-500/20 text-red-300 font-medium">
                                                            ⚔️ Conflict
                                                        </span>
                                                    )}
                                                    {isScanOnly && (
                                                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-medium">
                                                            ⚠️ Added in Code
                                                        </span>
                                                    )}
                                                    {isSpecOnly && (
                                                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-300 font-medium">
                                                            📝 Spec Only
                                                        </span>
                                                    )}
                                                    {isDeleted && (
                                                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-zinc-700 text-zinc-300 font-medium">
                                                            🗑️ Deleted in Code
                                                        </span>
                                                    )}
                                                    {isInSync && (
                                                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 font-medium">
                                                            ✓ In Sync
                                                        </span>
                                                    )}
                                                </div>

                                                {/* Details */}
                                                {item.details.conflict_reason && (
                                                    <p className="text-[11px] text-red-300 mt-1">{item.details.conflict_reason}</p>
                                                )}
                                                {item.details.columns_only_in_code && item.details.columns_only_in_code.length > 0 && (
                                                    <p className="text-[11px] text-amber-300 mt-0.5">
                                                        Code has extra fields: <span className="font-mono">{item.details.columns_only_in_code.join(', ')}</span>
                                                    </p>
                                                )}
                                                {item.details.columns_only_in_spec && item.details.columns_only_in_spec.length > 0 && (
                                                    <p className="text-[11px] text-blue-300 mt-0.5">
                                                        Spec has extra fields: <span className="font-mono">{item.details.columns_only_in_spec.join(', ')}</span>
                                                    </p>
                                                )}
                                            </div>
                                        </div>

                                        {/* Action Buttons */}
                                        <div className="flex items-center gap-2 shrink-0">
                                            {(isScanOnly || isConflict) && (
                                                <button
                                                    onClick={() => handleSyncSingle(item, 'accept_code')}
                                                    disabled={syncing}
                                                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-[11px] font-medium transition-colors"
                                                >
                                                    <Check size={11} />
                                                    <span>Accept in Spec</span>
                                                </button>
                                            )}
                                            {isDeleted && (
                                                <button
                                                    onClick={() => handleSyncSingle(item, 'delete')}
                                                    disabled={syncing}
                                                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-red-600/80 hover:bg-red-600 text-white text-[11px] font-medium transition-colors"
                                                >
                                                    <Trash2 size={11} />
                                                    <span>Delete from Spec</span>
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* PR Governance & CI Integration Section */}
            <div className="p-6 rounded-2xl bg-[var(--surface-1)] border border-[var(--border-subtle)] space-y-4">
                <div className="flex items-center gap-2">
                    <GitPullRequest size={18} className="text-blue-400" />
                    <h3 className="text-sm font-semibold text-zinc-100">PR Governance & CI GitHub Action</h3>
                </div>
                <p className="text-xs text-zinc-400">
                    Control how CreateFrame writes architectural changes back to GitHub. Choose whether to push directly or create atomic Pull Requests on a dedicated branch.
                </p>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                    <div>
                        <label className="text-[11px] font-mono text-zinc-400 block mb-1.5">Target Base Branch</label>
                        <div className="flex items-center gap-2">
                            <GitBranch size={14} className="text-zinc-500" />
                            <input
                                type="text"
                                value={targetBranch}
                                onChange={e => setTargetBranch(e.target.value)}
                                className="flex-1 bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded-xl px-3 py-1.5 text-xs text-zinc-100 font-mono outline-none focus:border-blue-500"
                                placeholder="main"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="text-[11px] font-mono text-zinc-400 block mb-1.5">Governance Workflow</label>
                        <select
                            value={governanceMode}
                            onChange={e => setGovernanceMode(e.target.value as 'direct' | 'pr')}
                            className="w-full bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded-xl px-3 py-1.5 text-xs text-zinc-100 font-mono outline-none focus:border-blue-500"
                        >
                            <option value="direct">Direct Push (Writes to default branch)</option>
                            <option value="pr">Pull Request (Proposes to createframe/proposed-*)</option>
                        </select>
                    </div>
                </div>

                <div className="flex items-center justify-between pt-2">
                    <button
                        onClick={handleSaveSettings}
                        disabled={savingSettings}
                        className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold transition-all"
                    >
                        {savingSettings ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                        <span>Save Governance Settings</span>
                    </button>

                    <button
                        onClick={handleTestPRCheck}
                        disabled={checkingPR}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-zinc-700 bg-[var(--surface-2)] hover:bg-[var(--surface-3)] text-zinc-300 text-xs transition-colors"
                    >
                        {checkingPR ? <Loader2 size={12} className="animate-spin" /> : <Terminal size={12} />}
                        <span>Simulate PR Comment Check</span>
                    </button>
                </div>

                {prCheckResult && (
                    <div className="mt-4 p-4 rounded-xl bg-[var(--surface-0)] border border-[var(--border-subtle)] font-mono text-xs">
                        <div className="flex items-center justify-between mb-2">
                            <span className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold">GitHub PR Bot Comment Preview</span>
                            <button
                                onClick={() => {
                                    navigator.clipboard.writeText(prCheckResult);
                                    setCopiedComment(true);
                                    setTimeout(() => setCopiedComment(false), 2000);
                                }}
                                className="flex items-center gap-1 text-[11px] text-zinc-400 hover:text-white"
                            >
                                {copiedComment ? <CheckCheck size={12} className="text-emerald-400" /> : <Copy size={12} />}
                                <span>{copiedComment ? 'Copied' : 'Copy'}</span>
                            </button>
                        </div>
                        <pre className="text-zinc-300 whitespace-pre-wrap leading-relaxed">{prCheckResult}</pre>
                    </div>
                )}
            </div>
        </div>
    );
}
