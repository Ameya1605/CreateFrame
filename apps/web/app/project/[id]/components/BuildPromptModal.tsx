'use client';

import React, { useState, useEffect } from 'react';
import api from '@/lib/api';
import {
    Terminal, Copy, Check, X, Loader2, Sparkles,
    Database, Globe, LayoutPanelTop, BookmarkCheck
} from 'lucide-react';

interface BuildPromptModalProps {
    projectId: number;
    featureId: number;
    featureName: string;
    isOpen: boolean;
    onClose: () => void;
    onShowToast: (msg: string, isSuccess?: boolean) => void;
}

export default function BuildPromptModal({
    projectId,
    featureId,
    featureName,
    isOpen,
    onClose,
    onShowToast,
}: BuildPromptModalProps) {
    const [target, setTarget] = useState<'cursor' | 'claude_code' | 'generic'>('cursor');
    const [promptText, setPromptText] = useState('');
    const [sliceSummary, setSliceSummary] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [copied, setCopied] = useState(false);

    const loadPrompt = async () => {
        setLoading(true);
        try {
            const res = await api.get(`/projects/${projectId}/features/${featureId}/build-prompt?target=${target}`);
            setPromptText(res.data.prompt);
            setSliceSummary(res.data.slice_summary);
        } catch (err: any) {
            onShowToast(err.response?.data?.detail || 'Failed to generate build prompt', false);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (isOpen) {
            loadPrompt();
        }
    }, [isOpen, target, featureId]);

    const handleCopy = () => {
        navigator.clipboard.writeText(promptText);
        setCopied(true);
        onShowToast('Prompt copied to clipboard!');
        setTimeout(() => setCopied(false), 2000);
    };

    const handleSaveTemplate = async () => {
        setSaving(true);
        try {
            await api.post(`/projects/${projectId}/features/${featureId}/build-prompt`, {
                target,
                save_as_template: true
            });
            onShowToast('Prompt saved to Project PromptTemplates!');
        } catch (err: any) {
            onShowToast(err.response?.data?.detail || 'Failed to save template', false);
        } finally {
            setSaving(false);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
            <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl w-full max-w-3xl flex flex-col max-h-[85vh] shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
                {/* Header */}
                <div className="px-6 py-4 border-b border-[var(--border-subtle)] flex items-center justify-between shrink-0">
                    <div>
                        <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-white">Per-Feature Build Prompt</h3>
                            <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-500/10 text-blue-400 border border-blue-500/20 font-medium">
                                {featureName}
                            </span>
                        </div>
                        <p className="text-xs text-zinc-400 mt-0.5">
                            Ready-to-paste instruction containing only the relevant slice of your spec.
                        </p>
                    </div>

                    <button
                        onClick={onClose}
                        className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-[var(--surface-2)] transition-all"
                    >
                        <X size={16} />
                    </button>
                </div>

                {/* Target Tabs */}
                <div className="px-6 py-2.5 bg-[var(--surface-2)] border-b border-[var(--border-subtle)] flex items-center justify-between shrink-0">
                    <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-400 font-medium">Target Agent:</span>
                        <div className="flex items-center bg-[var(--surface-1)] p-0.5 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold">
                            <button
                                onClick={() => setTarget('cursor')}
                                className={`px-3 py-1 rounded-lg transition-all ${
                                    target === 'cursor' ? 'bg-blue-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
                                }`}
                            >
                                Cursor Composer
                            </button>
                            <button
                                onClick={() => setTarget('claude_code')}
                                className={`px-3 py-1 rounded-lg transition-all ${
                                    target === 'claude_code' ? 'bg-purple-600 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
                                }`}
                            >
                                Claude Code CLI
                            </button>
                            <button
                                onClick={() => setTarget('generic')}
                                className={`px-3 py-1 rounded-lg transition-all ${
                                    target === 'generic' ? 'bg-zinc-700 text-white shadow' : 'text-zinc-400 hover:text-zinc-200'
                                }`}
                            >
                                Generic Agent
                            </button>
                        </div>
                    </div>

                    {/* Sliced Spec Badges */}
                    {sliceSummary && (
                        <div className="flex items-center gap-3 text-[11px] text-zinc-400">
                            <span className="flex items-center gap-1"><Database size={11} className="text-blue-400" /> {sliceSummary.schemas.length} tables</span>
                            <span className="flex items-center gap-1"><Globe size={11} className="text-purple-400" /> {sliceSummary.endpoints.length} routes</span>
                            <span className="flex items-center gap-1"><LayoutPanelTop size={11} className="text-pink-400" /> {sliceSummary.ui_components.length} views</span>
                        </div>
                    )}
                </div>

                {/* Prompt Body */}
                <div className="flex-1 overflow-y-auto p-6 bg-[var(--surface-0)] font-mono text-xs">
                    {loading ? (
                        <div className="h-64 flex flex-col items-center justify-center gap-2 text-zinc-400 font-sans">
                            <Loader2 size={20} className="animate-spin text-blue-500" />
                            <span>Slicing specification for {featureName}...</span>
                        </div>
                    ) : (
                        <textarea
                            value={promptText}
                            onChange={e => setPromptText(e.target.value)}
                            className="w-full h-80 bg-[var(--surface-1)] border border-[var(--border-subtle)] focus:border-blue-500/50 rounded-xl p-4 text-zinc-200 text-xs font-mono resize-none outline-none leading-relaxed"
                        />
                    )}
                </div>

                {/* Footer Actions */}
                <div className="px-6 py-4 bg-[var(--surface-1)] border-t border-[var(--border-subtle)] flex items-center justify-between shrink-0">
                    <button
                        onClick={handleSaveTemplate}
                        disabled={saving || loading}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-zinc-300 hover:text-white bg-[var(--surface-2)] border border-[var(--border-subtle)] hover:border-zinc-700 transition-all disabled:opacity-50"
                    >
                        {saving ? <Loader2 size={13} className="animate-spin" /> : <BookmarkCheck size={13} className="text-amber-400" />}
                        <span>Save as Template</span>
                    </button>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={onClose}
                            className="px-3 py-1.5 rounded-xl text-xs font-semibold text-zinc-400 hover:text-zinc-200 transition-all"
                        >
                            Close
                        </button>
                        <button
                            onClick={handleCopy}
                            disabled={loading || !promptText}
                            className="flex items-center gap-1.5 px-4 py-1.5 rounded-xl text-xs font-semibold bg-blue-600 hover:bg-blue-500 text-white transition-all shadow-md shadow-blue-600/20"
                        >
                            {copied ? <Check size={13} /> : <Copy size={13} />}
                            <span>{copied ? 'Copied!' : 'Copy to Clipboard'}</span>
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
