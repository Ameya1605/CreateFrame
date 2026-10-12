'use client';

import React, { useState } from 'react';
import api from '@/lib/api';
import {
    MessageSquare, Send, Loader2, Sparkles, AlertTriangle,
    ShieldAlert, Database, Globe, LayoutPanelTop, CheckCircle2,
    ArrowRight, CornerDownRight, HelpCircle
} from 'lucide-react';
import MathRenderer from './MathRenderer';

interface ChatReference {
    type: string;
    id?: number;
    title: string;
    detail?: string;
}

interface Message {
    role: 'user' | 'assistant';
    content: string;
    references?: ChatReference[];
    impactData?: any;
}

interface ArchitectureChatProps {
    projectId: number;
    onNavigateToItem?: (type: string, id?: number) => void;
}

export default function ArchitectureChat({ projectId, onNavigateToItem }: ArchitectureChatProps) {
    const [messages, setMessages] = useState<Message[]>([
        {
            role: 'assistant',
            content: "👋 Hello! I'm your **Architecture Companion**. Ask questions about how your backend, database, and frontend connect, or run an impact query like: \n\n*\"What breaks if I rename users.email?\"* or *\"Where is authentication handled?\"*",
        }
    ]);
    const [input, setInput] = useState('');
    const [loading, setLoading] = useState(false);
    const [mode, setMode] = useState<'chat' | 'impact'>('chat');

    const handleSend = async (textToSend?: string) => {
        const queryText = (textToSend || input).trim();
        if (!queryText || loading) return;

        const newMessages: Message[] = [...messages, { role: 'user', content: queryText }];
        setMessages(newMessages);
        setInput('');
        setLoading(true);

        // Check if query is an impact question
        const isImpactQuery = mode === 'impact' ||
            queryText.toLowerCase().includes('what breaks') ||
            queryText.toLowerCase().includes('rename ') ||
            queryText.toLowerCase().includes('delete table') ||
            queryText.toLowerCase().includes('drop ');

        try {
            if (isImpactQuery) {
                const res = await api.post(`/projects/${projectId}/impact-analysis`, {
                    query: queryText
                });
                const data = res.data;
                const assistantMsg: Message = {
                    role: 'assistant',
                    content: data.ai_summary || `Impact analysis for **\`${data.target}\`** (${data.action}):`,
                    impactData: data,
                    references: [
                        ...data.breaking_routes.map((r: any) => ({ type: 'endpoint', title: r.identifier, detail: r.reason })),
                        ...data.downstream_relations.map((rel: any) => ({ type: 'schema', title: rel.identifier, detail: rel.reason })),
                        ...data.breaking_components.map((c: any) => ({ type: 'ui_component', title: c.identifier, detail: c.reason }))
                    ]
                };
                setMessages([...newMessages, assistantMsg]);
            } else {
                const res = await api.post(`/projects/${projectId}/chat`, {
                    message: queryText,
                    history: messages.map(m => ({ role: m.role, content: m.content }))
                });
                const data = res.data;
                const assistantMsg: Message = {
                    role: 'assistant',
                    content: data.answer,
                    references: data.references
                };
                setMessages([...newMessages, assistantMsg]);
            }
        } catch (err: any) {
            setMessages([
                ...newMessages,
                {
                    role: 'assistant',
                    content: `⚠️ Error processing query: ${err.response?.data?.detail || err.message}`
                }
            ]);
        } finally {
            setLoading(false);
        }
    };

    const getRefIcon = (type: string) => {
        switch (type) {
            case 'endpoint': return <Globe size={12} className="text-purple-400" />;
            case 'schema': return <Database size={12} className="text-blue-400" />;
            case 'ui_component': return <LayoutPanelTop size={12} className="text-pink-400" />;
            default: return <Sparkles size={12} className="text-amber-400" />;
        }
    };

    return (
        <div className="flex flex-col h-full bg-[var(--surface-0)] overflow-hidden">
            {/* Header */}
            <div className="px-6 py-3.5 border-b border-[var(--border-subtle)] bg-[var(--surface-1)] flex items-center justify-between shrink-0">
                <div className="flex items-center gap-2.5">
                    <div className="w-8 h-8 rounded-xl bg-blue-600/15 border border-blue-500/25 flex items-center justify-center text-blue-400">
                        <MessageSquare size={16} />
                    </div>
                    <div>
                        <h3 className="text-xs font-bold text-white">Architecture Chat & Impact Analysis</h3>
                        <p className="text-[11px] text-zinc-400">Ask structural questions or simulate schema refactoring impacts.</p>
                    </div>
                </div>

                {/* Mode Selector */}
                <div className="flex items-center bg-[var(--surface-2)] p-0.5 rounded-xl border border-[var(--border-subtle)] text-xs font-semibold">
                    <button
                        onClick={() => setMode('chat')}
                        className={`px-3 py-1 rounded-lg transition-all ${
                            mode === 'chat'
                                ? 'bg-blue-600 text-white shadow'
                                : 'text-zinc-400 hover:text-zinc-200'
                        }`}
                    >
                        Chat Mode
                    </button>
                    <button
                        onClick={() => setMode('impact')}
                        className={`px-3 py-1 rounded-lg transition-all ${
                            mode === 'impact'
                                ? 'bg-orange-600 text-white shadow'
                                : 'text-zinc-400 hover:text-zinc-200'
                        }`}
                    >
                        Impact Mode
                    </button>
                </div>
            </div>

            {/* Messages Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-5">
                {messages.map((m, idx) => (
                    <div
                        key={idx}
                        className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}
                    >
                        <div
                            className={`max-w-2xl rounded-2xl p-4 text-xs leading-relaxed ${
                                m.role === 'user'
                                    ? 'bg-blue-600 text-white rounded-br-none shadow-md shadow-blue-600/10'
                                    : 'bg-[var(--surface-1)] text-zinc-200 border border-[var(--border-subtle)] rounded-bl-none shadow-sm'
                            }`}
                        >
                            {m.role === 'user' ? (
                                <div className="whitespace-pre-wrap">{m.content}</div>
                            ) : (
                                <MathRenderer content={m.content} />
                            )}

                            {/* Impact Details Card */}
                            {m.impactData && (
                                <div className="mt-4 pt-3 border-t border-[var(--border-subtle)] space-y-3">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] uppercase font-bold text-zinc-400">Severity</span>
                                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                                            m.impactData.severity === 'high'
                                                ? 'bg-red-500/15 text-red-400 border border-red-500/30'
                                                : m.impactData.severity === 'medium'
                                                ? 'bg-amber-500/15 text-amber-400 border border-amber-500/30'
                                                : 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                                        }`}>
                                            {m.impactData.severity} Severity
                                        </span>
                                    </div>

                                    {/* Breaking Routes */}
                                    {m.impactData.breaking_routes.length > 0 && (
                                        <div className="bg-[var(--surface-2)] p-2.5 rounded-xl border border-[var(--border-subtle)]">
                                            <div className="text-[11px] font-bold text-red-400 flex items-center gap-1.5 mb-1.5">
                                                <ShieldAlert size={12} />
                                                <span>{m.impactData.breaking_routes.length} Breaking Routes</span>
                                            </div>
                                            <div className="space-y-1">
                                                {m.impactData.breaking_routes.map((r: any, i: number) => (
                                                    <div key={i} className="text-[11px] font-mono text-zinc-300 flex items-center justify-between">
                                                        <span>{r.identifier}</span>
                                                        <span className="text-[10px] text-zinc-500">{r.reason}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Downstream Foreign Keys */}
                                    {m.impactData.downstream_relations.length > 0 && (
                                        <div className="bg-[var(--surface-2)] p-2.5 rounded-xl border border-[var(--border-subtle)]">
                                            <div className="text-[11px] font-bold text-amber-400 flex items-center gap-1.5 mb-1.5">
                                                <Database size={12} />
                                                <span>{m.impactData.downstream_relations.length} Downstream Foreign Keys</span>
                                            </div>
                                            <div className="space-y-1">
                                                {m.impactData.downstream_relations.map((rel: any, i: number) => (
                                                    <div key={i} className="text-[11px] font-mono text-zinc-300 flex items-center justify-between">
                                                        <span>{rel.identifier}</span>
                                                        <span className="text-[10px] text-zinc-500">{rel.reason}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Action Checklist */}
                                    {m.impactData.recommended_actions.length > 0 && (
                                        <div className="space-y-1 pt-1">
                                            <span className="text-[10px] uppercase font-bold text-zinc-400">Recommended Migration Checklist</span>
                                            {m.impactData.recommended_actions.map((act: string, i: number) => (
                                                <div key={i} className="flex items-start gap-1.5 text-[11px] text-zinc-300">
                                                    <CheckCircle2 size={12} className="text-blue-400 shrink-0 mt-0.5" />
                                                    <span>{act}</span>
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}

                            {/* Grounded References Badges */}
                            {m.references && m.references.length > 0 && !m.impactData && (
                                <div className="mt-3 pt-3 border-t border-[var(--border-subtle)] space-y-1.5">
                                    <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">
                                        Referenced Spec Entities
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {m.references.map((ref, rIdx) => (
                                            <button
                                                key={rIdx}
                                                onClick={() => onNavigateToItem && onNavigateToItem(ref.type, ref.id)}
                                                className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-[var(--surface-2)] border border-[var(--border-subtle)] hover:border-zinc-600 transition-all text-[11px] text-zinc-300"
                                            >
                                                {getRefIcon(ref.type)}
                                                <span className="font-mono">{ref.title}</span>
                                                <CornerDownRight size={10} className="text-zinc-500 ml-0.5" />
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                ))}

                {loading && (
                    <div className="flex items-center gap-2 text-xs text-zinc-400 bg-[var(--surface-1)] border border-[var(--border-subtle)] p-3 rounded-2xl w-fit">
                        <Loader2 size={13} className="animate-spin text-blue-400" />
                        <span>Analyzing architecture graph & dependencies...</span>
                    </div>
                )}
            </div>

            {/* Suggestion Chips */}
            <div className="px-6 py-2 bg-[var(--surface-1)] border-t border-[var(--border-subtle)] flex items-center gap-2 overflow-x-auto text-[11px]">
                <span className="text-zinc-500 shrink-0 font-medium">Try:</span>
                <button
                    onClick={() => handleSend("Where is authentication handled?")}
                    className="px-2.5 py-1 rounded-lg bg-[var(--surface-2)] hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-[var(--border-subtle)] transition-all shrink-0"
                >
                    Where is auth handled?
                </button>
                <button
                    onClick={() => handleSend("What breaks if I rename users.email?")}
                    className="px-2.5 py-1 rounded-lg bg-[var(--surface-2)] hover:bg-zinc-800 text-orange-400 hover:text-orange-300 border border-[var(--border-subtle)] transition-all shrink-0"
                >
                    What breaks if I rename users.email?
                </button>
                <button
                    onClick={() => handleSend("Which endpoints require Bearer auth?")}
                    className="px-2.5 py-1 rounded-lg bg-[var(--surface-2)] hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200 border border-[var(--border-subtle)] transition-all shrink-0"
                >
                    Which endpoints require auth?
                </button>
            </div>

            {/* Input Footer */}
            <div className="p-4 bg-[var(--surface-1)] border-t border-[var(--border-subtle)]">
                <form
                    onSubmit={e => {
                        e.preventDefault();
                        handleSend();
                    }}
                    className="flex items-center gap-2 bg-[var(--surface-2)] border border-[var(--border-subtle)] focus-within:border-blue-500/50 rounded-2xl p-1.5 px-3 transition-all"
                >
                    <input
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        placeholder={mode === 'impact' ? "e.g., What breaks if I rename users.email to email_address?" : "Ask anything about your architecture spec..."}
                        className="flex-1 bg-transparent text-xs text-zinc-100 placeholder:text-zinc-500 outline-none"
                    />
                    <button
                        type="submit"
                        disabled={!input.trim() || loading}
                        className="p-2 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:opacity-30 disabled:cursor-not-allowed text-white transition-all shadow-md shadow-blue-600/20"
                    >
                        <Send size={13} />
                    </button>
                </form>
            </div>
        </div>
    );
}
