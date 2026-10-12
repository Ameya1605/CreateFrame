'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
    ArrowLeft, ChevronRight, Github, Rocket,
    Database, Check, Loader2, Sparkles,
    X, Plus, Terminal, Layout, Globe,
    Lock, Unlock, Shield, ShieldCheck,
    AlertCircle, Layers, Lightbulb, Code2
} from 'lucide-react';
import api from '@/lib/api';

const METHOD_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    GET: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/30' },
    POST: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
    PUT: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/30' },
    PATCH: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/30' },
    DELETE: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
};

const SUGGESTIONS = [
    {
        title: 'SaaS Platform',
        desc: 'Multi-tenant subscription app with billing, team permissions, and analytics',
    },
    {
        title: 'Social Community',
        desc: 'User profiles, feed of posts, comments, likes, and direct messaging',
    },
    {
        title: 'Developer Tool API',
        desc: 'API key authentication, rate limiting, webhook dispatching, and audit logs',
    },
    {
        title: 'Marketplace',
        desc: 'Buyer/seller accounts, product catalog, cart checkout, and review ratings',
    }
];

export default function NewProjectWizard() {
    const router = useRouter();
    const [currentStep, setCurrentStep] = useState(1);
    const [loading, setLoading] = useState(false);
    const [brainstorming, setBrainstorming] = useState(false);
    const [username, setUsername] = useState('');
    const [mounted, setMounted] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);

    useEffect(() => {
        setMounted(true);
        if (typeof window !== 'undefined') {
            if (!localStorage.getItem('token')) {
                router.push('/');
            }
            setUsername(localStorage.getItem('username') || 'you');
        }
    }, [router]);

    // Step 1 - Identity
    const [repoName, setRepoName] = useState('');
    const [isPrivate, setIsPrivate] = useState(false);
    const [withAuth, setWithAuth] = useState(true);

    // Step 2 - Describe
    const [projectDescription, setProjectDescription] = useState('');

    // Step 3 - Editable spec
    const [features, setFeatures] = useState<string[]>([]);
    const [schemas, setSchemas] = useState<any[]>([]);
    const [endpoints, setEndpoints] = useState<any[]>([]);
    const [uiComponents, setUiComponents] = useState<any[]>([]);
    const [specActiveTab, setSpecActiveTab] = useState<'features' | 'schemas' | 'endpoints' | 'ui'>('features');

    // Inline add states
    const [newFeature, setNewFeature] = useState('');
    const [newTable, setNewTable] = useState('');
    const [newRoute, setNewRoute] = useState('');
    const [newRouteMethod, setNewRouteMethod] = useState('GET');
    const [newComponent, setNewComponent] = useState('');

    const handleBrainstorm = async () => {
        if (!projectDescription) return;
        setBrainstorming(true);
        setErrorMessage(null);
        try {
            const res = await api.post('/brainstorm-architecture', { description: projectDescription });
            setFeatures(res.data.features || []);
            setSchemas(res.data.schemas || []);
            const suggestedEndpoints = (res.data.features || []).map((f: string) => ({
                method: 'GET',
                route: `/${f.toLowerCase().replace(/\s+/g, '-')}`,
                request_schema: {},
                response_schema: {}
            }));
            const suggestedUI = (res.data.features || []).map((f: string) => ({
                name: f,
                type: 'page'
            }));
            setEndpoints(suggestedEndpoints);
            setUiComponents(suggestedUI);
            setCurrentStep(3);
        } catch {
            setErrorMessage('AI architecture generation failed. Please check your credentials or retry.');
        } finally {
            setBrainstorming(false);
        }
    };

    const handleCreate = async () => {
        setLoading(true);
        setErrorMessage(null);
        try {
            const repoRes = await api.post(`/github/create-repo?name=${repoName}&private=${isPrivate}`);
            const repoUrl = repoRes.data.html_url;
            const projRes = await api.post('/projects/initialize', { name: repoName, repo_url: repoUrl });
            const projectId = projRes.data.id;

            await Promise.all([
                ...features.map(f => api.post(`/features?project_id=${projectId}`, { name: f, status: 'planned' })),
                ...schemas.map(s => api.post(`/schemas?project_id=${projectId}`, s)),
                ...endpoints.map(e => api.post(`/endpoints?project_id=${projectId}`, e)),
                ...uiComponents.map(c => api.post(`/ui-components?project_id=${projectId}`, c)),
            ]);

            await api.post(`/projects/${projectId}/commit`);
            router.push(`/project/${projectId}`);
        } catch {
            setErrorMessage('Failed to initialize project. Please check if repository name already exists on your GitHub.');
        } finally {
            setLoading(false);
        }
    };

    const steps = [
        { id: 1, label: 'Identity' },
        { id: 2, label: 'Blueprint' },
        { id: 3, label: 'Spec Editor' },
        { id: 4, label: 'Launch' },
    ];

    if (!mounted) {
        return (
            <div className="min-h-screen bg-[var(--surface-0)] text-zinc-100 flex items-center justify-center">
                <Loader2 className="w-6 h-6 animate-spin text-zinc-600" />
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[var(--surface-0)] text-zinc-100 flex flex-col antialiased">
            {/* Top Navigation */}
            <div className="h-14 bg-[var(--surface-1)] border-b border-[var(--border-subtle)] flex items-center justify-between px-6 shrink-0 sticky top-0 z-30">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => router.push('/dashboard')}
                        className="flex items-center gap-2 text-zinc-400 hover:text-white text-xs font-medium px-2.5 py-1.5 rounded-lg hover:bg-[var(--surface-2)] transition-all"
                    >
                        <ArrowLeft size={14} /> Back to dashboard
                    </button>
                    <span className="text-zinc-700">/</span>
                    <span className="text-xs font-medium text-zinc-300">New Project Wizard</span>
                </div>

                {/* Step Pill Stepper */}
                <div className="flex items-center gap-2">
                    {steps.map((s, idx) => {
                        const isActive = currentStep === s.id;
                        const isDone = currentStep > s.id;
                        return (
                            <React.Fragment key={s.id}>
                                <button
                                    onClick={() => {
                                        if (isDone || (s.id === 2 && repoName) || (s.id === 3 && features.length > 0)) {
                                            setCurrentStep(s.id);
                                        }
                                    }}
                                    disabled={!isDone && !isActive && (s.id > currentStep + 1)}
                                    className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-all ${
                                        isActive
                                            ? 'bg-blue-600/20 text-blue-400 border border-blue-500/40'
                                            : isDone
                                            ? 'bg-[var(--surface-2)] text-zinc-300 hover:text-white border border-[var(--border-subtle)]'
                                            : 'text-zinc-600 border border-transparent'
                                    }`}
                                >
                                    <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] ${
                                        isDone ? 'bg-emerald-500/20 text-emerald-400' : isActive ? 'bg-blue-600 text-white' : 'bg-zinc-800 text-zinc-500'
                                    }`}>
                                        {isDone ? <Check size={10} strokeWidth={3} /> : s.id}
                                    </span>
                                    <span>{s.label}</span>
                                </button>
                                {idx < steps.length - 1 && (
                                    <div className={`w-4 h-0.5 rounded-full ${currentStep > s.id ? 'bg-emerald-500/40' : 'bg-zinc-800'}`} />
                                )}
                            </React.Fragment>
                        );
                    })}
                </div>
            </div>

            {/* Error Banner */}
            {errorMessage && (
                <div className="max-w-2xl mx-auto w-full px-6 pt-6">
                    <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start justify-between gap-3 text-red-300 text-xs">
                        <div className="flex items-start gap-2.5">
                            <AlertCircle size={16} className="text-red-400 shrink-0 mt-0.5" />
                            <span>{errorMessage}</span>
                        </div>
                        <button onClick={() => setErrorMessage(null)} className="text-red-400 hover:text-red-200">
                            <X size={14} />
                        </button>
                    </div>
                </div>
            )}

            {/* Main Content Area */}
            <div className="max-w-2xl mx-auto w-full px-6 py-12 flex-1 flex flex-col justify-center">

                {/* ── Step 1: Identity ── */}
                {currentStep === 1 && (
                    <div className="space-y-8 animate-fade">
                        <div>
                            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold mb-3">
                                <span>Step 1</span>
                                <span className="text-zinc-600">•</span>
                                <span>Repository Identity</span>
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Name your project.</h1>
                            <p className="text-zinc-400 text-sm">We'll automatically set up this GitHub repository with the initial spec and architecture.</p>
                        </div>

                        <div className="space-y-4">
                            {/* Repo Input Box */}
                            <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] focus-within:border-blue-500/60 focus-within:ring-2 focus-within:ring-blue-500/15 rounded-xl p-2 transition-all">
                                <label className="text-[11px] font-medium text-zinc-500 px-3 pt-1 block">GitHub Repository</label>
                                <div className="flex items-center px-3 pb-1 pt-0.5">
                                    <div className="flex items-center gap-1.5 text-zinc-400 text-sm font-mono shrink-0 select-none mr-1.5">
                                        <Github size={14} className="text-zinc-500" />
                                        <span>github.com/{username}/</span>
                                    </div>
                                    <input
                                        type="text"
                                        placeholder="project-name"
                                        autoFocus
                                        className="flex-1 bg-transparent text-sm font-semibold text-white outline-none placeholder:text-zinc-700 font-mono"
                                        value={repoName}
                                        onChange={e => setRepoName(e.target.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-_]/g, ''))}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter' && repoName) {
                                                setCurrentStep(2);
                                            }
                                        }}
                                    />
                                </div>
                            </div>

                            {/* Configuration Options */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                                <div
                                    onClick={() => setIsPrivate(!isPrivate)}
                                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                                        isPrivate
                                            ? 'bg-blue-600/10 border-blue-500/40 text-white'
                                            : 'bg-[var(--surface-1)] border-[var(--border-subtle)] hover:border-[var(--border-default)] text-zinc-400'
                                    }`}
                                >
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            {isPrivate ? <Lock size={16} className="text-blue-400" /> : <Unlock size={16} className="text-zinc-500" />}
                                            <span className="text-sm font-semibold text-zinc-200">Visibility</span>
                                        </div>
                                        <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${
                                            isPrivate ? 'bg-blue-600 border-blue-600 text-white' : 'border-zinc-700'
                                        }`}>
                                            {isPrivate && <Check size={11} strokeWidth={3} />}
                                        </div>
                                    </div>
                                    <p className="text-xs text-zinc-500">
                                        {isPrivate ? 'Private repo (only you and your team)' : 'Public repo (visible to anyone)'}
                                    </p>
                                </div>

                                <div
                                    onClick={() => setWithAuth(!withAuth)}
                                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                                        withAuth
                                            ? 'bg-blue-600/10 border-blue-500/40 text-white'
                                            : 'bg-[var(--surface-1)] border-[var(--border-subtle)] hover:border-[var(--border-default)] text-zinc-400'
                                    }`}
                                >
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            {withAuth ? <ShieldCheck size={16} className="text-blue-400" /> : <Shield size={16} className="text-zinc-500" />}
                                            <span className="text-sm font-semibold text-zinc-200">Authentication</span>
                                        </div>
                                        <div className={`w-4 h-4 rounded border flex items-center justify-center transition-all ${
                                            withAuth ? 'bg-blue-600 border-blue-600 text-white' : 'border-zinc-700'
                                        }`}>
                                            {withAuth && <Check size={11} strokeWidth={3} />}
                                        </div>
                                    </div>
                                    <p className="text-xs text-zinc-500">
                                        {withAuth ? 'Pre-configured User model, JWT & auth routes' : 'No authentication starter needed'}
                                    </p>
                                </div>
                            </div>
                        </div>

                        <div className="pt-2 flex justify-end">
                            <button
                                onClick={() => setCurrentStep(2)}
                                disabled={!repoName}
                                className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-xl shadow-lg shadow-blue-600/20 transition-all hover:scale-[1.01]"
                            >
                                Continue to Blueprint <ChevronRight size={15} />
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Step 2: Describe & Brainstorm ── */}
                {currentStep === 2 && (
                    <div className="space-y-6 animate-fade">
                        <div>
                            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-orange-500/10 border border-orange-500/20 text-orange-400 text-xs font-semibold mb-3">
                                <span>Step 2</span>
                                <span className="text-zinc-600">•</span>
                                <span>AI Architecture Blueprint</span>
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight text-white mb-2">What are you building?</h1>
                            <p className="text-zinc-400 text-sm">Provide a high-level summary. CreateFrame will derive database models, endpoints, and frontend features.</p>
                        </div>

                        <div className="space-y-4">
                            <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] focus-within:border-orange-500/60 focus-within:ring-2 focus-within:ring-orange-500/15 rounded-xl p-3 transition-all">
                                <textarea
                                    placeholder="e.g. A developer bookmarking platform where users can save code snippets, categorize them with tags, generate documentation with AI, and share public links."
                                    className="w-full bg-transparent text-sm text-zinc-100 outline-none h-36 resize-none placeholder:text-zinc-600 leading-relaxed"
                                    value={projectDescription}
                                    onChange={e => setProjectDescription(e.target.value)}
                                    autoFocus
                                />
                            </div>

                            {/* Quick Starter Chips */}
                            <div>
                                <p className="text-[11px] font-semibold text-zinc-500 mb-2 flex items-center gap-1.5">
                                    <Lightbulb size={12} className="text-amber-400" /> Need inspiration? Click a template:
                                </p>
                                <div className="grid grid-cols-2 gap-2">
                                    {SUGGESTIONS.map((s, idx) => (
                                        <button
                                            key={idx}
                                            type="button"
                                            onClick={() => setProjectDescription(s.desc)}
                                            className="text-left p-2.5 rounded-lg bg-[var(--surface-1)] border border-[var(--border-subtle)] hover:border-zinc-700 hover:bg-[var(--surface-2)] transition-all group"
                                        >
                                            <p className="text-xs font-semibold text-zinc-300 group-hover:text-white">{s.title}</p>
                                            <p className="text-[10px] text-zinc-500 truncate mt-0.5">{s.desc}</p>
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Action Buttons */}
                            <div className="space-y-2 pt-2">
                                <button
                                    onClick={handleBrainstorm}
                                    disabled={!projectDescription || brainstorming}
                                    className="w-full flex items-center justify-center gap-2 py-3.5 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-400 hover:to-amber-400 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition-all text-xs shadow-lg shadow-orange-500/20"
                                >
                                    {brainstorming ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                                    {brainstorming ? 'AI is drafting your architecture & models...' : 'Generate Full Architecture Spec'}
                                </button>

                                <div className="flex items-center gap-3 py-1">
                                    <div className="flex-1 h-px bg-[var(--border-subtle)]" />
                                    <span className="text-[10px] text-zinc-600 font-semibold uppercase tracking-wider">or proceed manually</span>
                                    <div className="flex-1 h-px bg-[var(--border-subtle)]" />
                                </div>

                                <button
                                    onClick={() => setCurrentStep(3)}
                                    className="w-full py-2.5 border border-[var(--border-subtle)] hover:border-zinc-700 bg-[var(--surface-1)] text-zinc-400 hover:text-zinc-200 text-xs font-medium rounded-xl transition-all"
                                >
                                    Start with an empty spec
                                </button>
                            </div>
                        </div>

                        <div className="flex items-center justify-between pt-2">
                            <button
                                onClick={() => setCurrentStep(1)}
                                className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                            >
                                <ArrowLeft size={13} /> Back to Identity
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Step 3: Edit Spec ── */}
                {currentStep === 3 && (
                    <div className="space-y-6 animate-fade">
                        <div>
                            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold mb-3">
                                <span>Step 3</span>
                                <span className="text-zinc-600">•</span>
                                <span>Spec Editor</span>
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Review & refine your spec.</h1>
                            <p className="text-zinc-400 text-sm">Fine-tune features, database schemas, endpoints, and UI views before creating the repository.</p>
                        </div>

                        {/* Segmented Filter Tabs */}
                        <div className="flex items-center gap-1.5 p-1 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl">
                            <button
                                onClick={() => setSpecActiveTab('features')}
                                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                                    specActiveTab === 'features' ? 'bg-blue-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                                }`}
                            >
                                <Check size={13} />
                                <span>Features ({features.length})</span>
                            </button>
                            <button
                                onClick={() => setSpecActiveTab('schemas')}
                                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                                    specActiveTab === 'schemas' ? 'bg-emerald-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                                }`}
                            >
                                <Database size={13} />
                                <span>Tables ({schemas.length})</span>
                            </button>
                            <button
                                onClick={() => setSpecActiveTab('endpoints')}
                                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                                    specActiveTab === 'endpoints' ? 'bg-purple-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                                }`}
                            >
                                <Terminal size={13} />
                                <span>API ({endpoints.length})</span>
                            </button>
                            <button
                                onClick={() => setSpecActiveTab('ui')}
                                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-semibold transition-all ${
                                    specActiveTab === 'ui' ? 'bg-pink-600 text-white shadow-sm' : 'text-zinc-400 hover:text-zinc-200'
                                }`}
                            >
                                <Layout size={13} />
                                <span>UI ({uiComponents.length})</span>
                            </button>
                        </div>

                        {/* Spec Items Container */}
                        <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl overflow-hidden divide-y divide-[var(--border-subtle)]">
                            {/* Features Tab */}
                            {specActiveTab === 'features' && (
                                <>
                                    <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border-subtle)]">
                                        {features.length === 0 ? (
                                            <p className="p-6 text-center text-xs text-zinc-500">No features specified yet. Add one below.</p>
                                        ) : (
                                            features.map((f, i) => (
                                                <div key={i} className="flex items-center gap-3 px-4 py-2.5 group hover:bg-[var(--surface-2)] transition-colors">
                                                    <span className="text-zinc-500 text-xs w-5 text-right font-mono shrink-0">{i + 1}.</span>
                                                    <input
                                                        value={f}
                                                        onChange={e => setFeatures(features.map((v, idx) => idx === i ? e.target.value : v))}
                                                        className="flex-1 bg-transparent text-xs text-zinc-200 outline-none focus:text-white"
                                                    />
                                                    <button
                                                        onClick={() => setFeatures(features.filter((_, idx) => idx !== i))}
                                                        className="text-zinc-600 hover:text-red-400 p-1 opacity-60 group-hover:opacity-100 transition-all"
                                                        title="Remove feature"
                                                    >
                                                        <X size={13} />
                                                    </button>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2.5 px-4 py-3 bg-[var(--surface-2)]">
                                        <Plus size={14} className="text-zinc-400 shrink-0" />
                                        <input
                                            value={newFeature}
                                            onChange={e => setNewFeature(e.target.value)}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter' && newFeature.trim()) {
                                                    setFeatures([...features, newFeature.trim()]);
                                                    setNewFeature('');
                                                }
                                            }}
                                            placeholder="Type a feature and press Enter (e.g. User Authentication, Stripe Checkout)..."
                                            className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 outline-none"
                                        />
                                    </div>
                                </>
                            )}

                            {/* Schemas Tab */}
                            {specActiveTab === 'schemas' && (
                                <>
                                    <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border-subtle)]">
                                        {schemas.length === 0 ? (
                                            <p className="p-6 text-center text-xs text-zinc-500">No database tables yet. Add one below.</p>
                                        ) : (
                                            schemas.map((s, i) => (
                                                <div key={i} className="flex items-center gap-3 px-4 py-2.5 group hover:bg-[var(--surface-2)] transition-colors">
                                                    <span className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">
                                                        MODEL
                                                    </span>
                                                    <input
                                                        value={s.table_name}
                                                        onChange={e => setSchemas(schemas.map((v, idx) => idx === i ? { ...v, table_name: e.target.value } : v))}
                                                        className="flex-1 bg-transparent text-xs text-zinc-200 outline-none font-mono focus:text-white"
                                                    />
                                                    <span className="text-[11px] text-zinc-500">{s.fields?.length || 0} fields</span>
                                                    <button
                                                        onClick={() => setSchemas(schemas.filter((_, idx) => idx !== i))}
                                                        className="text-zinc-600 hover:text-red-400 p-1 opacity-60 group-hover:opacity-100 transition-all"
                                                        title="Remove table"
                                                    >
                                                        <X size={13} />
                                                    </button>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2.5 px-4 py-3 bg-[var(--surface-2)]">
                                        <Plus size={14} className="text-zinc-400 shrink-0" />
                                        <input
                                            value={newTable}
                                            onChange={e => setNewTable(e.target.value)}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter' && newTable.trim()) {
                                                    setSchemas([...schemas, { table_name: newTable.trim(), fields: [] }]);
                                                    setNewTable('');
                                                }
                                            }}
                                            placeholder="Table name (e.g. orders, profiles, invoices)..."
                                            className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 outline-none font-mono"
                                        />
                                    </div>
                                </>
                            )}

                            {/* Endpoints Tab */}
                            {specActiveTab === 'endpoints' && (
                                <>
                                    <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border-subtle)]">
                                        {endpoints.length === 0 ? (
                                            <p className="p-6 text-center text-xs text-zinc-500">No API endpoints yet. Add one below.</p>
                                        ) : (
                                            endpoints.map((ep, i) => {
                                                const badge = METHOD_COLORS[ep.method] || { bg: 'bg-zinc-800', text: 'text-zinc-300', border: 'border-zinc-700' };
                                                return (
                                                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 group hover:bg-[var(--surface-2)] transition-colors">
                                                        <select
                                                            value={ep.method}
                                                            onChange={e => setEndpoints(endpoints.map((v, idx) => idx === i ? { ...v, method: e.target.value } : v))}
                                                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase outline-none cursor-pointer border ${badge.bg} ${badge.text} ${badge.border}`}
                                                        >
                                                            {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => <option key={m} value={m} className="bg-zinc-900 text-white">{m}</option>)}
                                                        </select>
                                                        <input
                                                            value={ep.route}
                                                            onChange={e => setEndpoints(endpoints.map((v, idx) => idx === i ? { ...v, route: e.target.value } : v))}
                                                            className="flex-1 bg-transparent text-xs text-zinc-200 outline-none font-mono focus:text-white"
                                                        />
                                                        <button
                                                            onClick={() => setEndpoints(endpoints.filter((_, idx) => idx !== i))}
                                                            className="text-zinc-600 hover:text-red-400 p-1 opacity-60 group-hover:opacity-100 transition-all"
                                                            title="Remove endpoint"
                                                        >
                                                            <X size={13} />
                                                        </button>
                                                    </div>
                                                );
                                            })
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2.5 px-4 py-3 bg-[var(--surface-2)]">
                                        <select
                                            value={newRouteMethod}
                                            onChange={e => setNewRouteMethod(e.target.value)}
                                            className={`px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase outline-none cursor-pointer border ${METHOD_COLORS[newRouteMethod]?.bg} ${METHOD_COLORS[newRouteMethod]?.text} ${METHOD_COLORS[newRouteMethod]?.border}`}
                                        >
                                            {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => <option key={m} value={m} className="bg-zinc-900 text-white">{m}</option>)}
                                        </select>
                                        <input
                                            value={newRoute}
                                            onChange={e => setNewRoute(e.target.value)}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter' && newRoute.trim()) {
                                                    const routeFormatted = newRoute.trim().startsWith('/') ? newRoute.trim() : `/${newRoute.trim()}`;
                                                    setEndpoints([...endpoints, { method: newRouteMethod, route: routeFormatted, request_schema: {}, response_schema: {} }]);
                                                    setNewRoute('');
                                                }
                                            }}
                                            placeholder="/api/v1/resource (press Enter)..."
                                            className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 outline-none font-mono"
                                        />
                                    </div>
                                </>
                            )}

                            {/* UI Tab */}
                            {specActiveTab === 'ui' && (
                                <>
                                    <div className="max-h-72 overflow-y-auto divide-y divide-[var(--border-subtle)]">
                                        {uiComponents.length === 0 ? (
                                            <p className="p-6 text-center text-xs text-zinc-500">No UI components yet. Add one below.</p>
                                        ) : (
                                            uiComponents.map((c, i) => (
                                                <div key={i} className="flex items-center gap-3 px-4 py-2.5 group hover:bg-[var(--surface-2)] transition-colors">
                                                    <select
                                                        value={c.type}
                                                        onChange={e => setUiComponents(uiComponents.map((v, idx) => idx === i ? { ...v, type: e.target.value } : v))}
                                                        className="px-1.5 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-pink-500/10 text-pink-400 border border-pink-500/20 outline-none cursor-pointer shrink-0"
                                                    >
                                                        {['page', 'component', 'layout'].map(t => <option key={t} value={t} className="bg-zinc-900 text-white">{t}</option>)}
                                                    </select>
                                                    <input
                                                        value={c.name}
                                                        onChange={e => setUiComponents(uiComponents.map((v, idx) => idx === i ? { ...v, name: e.target.value } : v))}
                                                        className="flex-1 bg-transparent text-xs text-zinc-200 outline-none focus:text-white"
                                                    />
                                                    <button
                                                        onClick={() => setUiComponents(uiComponents.filter((_, idx) => idx !== i))}
                                                        className="text-zinc-600 hover:text-red-400 p-1 opacity-60 group-hover:opacity-100 transition-all"
                                                        title="Remove component"
                                                    >
                                                        <X size={13} />
                                                    </button>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                    <div className="flex items-center gap-2.5 px-4 py-3 bg-[var(--surface-2)]">
                                        <Plus size={14} className="text-zinc-400 shrink-0" />
                                        <input
                                            value={newComponent}
                                            onChange={e => setNewComponent(e.target.value)}
                                            onKeyDown={e => {
                                                if (e.key === 'Enter' && newComponent.trim()) {
                                                    setUiComponents([...uiComponents, { name: newComponent.trim(), type: 'page' }]);
                                                    setNewComponent('');
                                                }
                                            }}
                                            placeholder="Component or page name (e.g. PricingTable, DashboardHeader)..."
                                            className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 outline-none"
                                        />
                                    </div>
                                </>
                            )}
                        </div>

                        {/* Navigation Buttons */}
                        <div className="flex items-center justify-between pt-4">
                            <button
                                onClick={() => setCurrentStep(2)}
                                className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                            >
                                <ArrowLeft size={13} /> Back to Blueprint
                            </button>
                            <button
                                onClick={() => setCurrentStep(4)}
                                disabled={features.length === 0 && schemas.length === 0 && endpoints.length === 0}
                                className="flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-xl shadow-lg shadow-blue-600/20 transition-all hover:scale-[1.01]"
                            >
                                Proceed to Launch <ChevronRight size={15} />
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Step 4: Launch ── */}
                {currentStep === 4 && (
                    <div className="space-y-8 animate-fade">
                        <div>
                            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-semibold mb-3">
                                <span>Step 4</span>
                                <span className="text-zinc-600">•</span>
                                <span>Ready to Deploy</span>
                            </div>
                            <h1 className="text-3xl font-bold tracking-tight text-white mb-2">Ready to ship.</h1>
                            <p className="text-zinc-400 text-sm">We'll create the GitHub repository, commit the full spec, and initialize your project workspace.</p>
                        </div>

                        {/* Architecture Summary Manifest */}
                        <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl p-5 space-y-4">
                            <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
                                <div className="flex items-center gap-2 font-mono text-xs text-zinc-200 font-bold">
                                    <Github size={14} className="text-zinc-400" />
                                    <span>{username}/{repoName}</span>
                                </div>
                                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-zinc-800 text-zinc-400 border border-zinc-700">
                                    {isPrivate ? 'Private' : 'Public'}
                                </span>
                            </div>

                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                                <div className="p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                                    <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Features</span>
                                    <span className="text-lg font-bold text-blue-400">{features.length}</span>
                                </div>
                                <div className="p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                                    <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Tables</span>
                                    <span className="text-lg font-bold text-emerald-400">{schemas.length}</span>
                                </div>
                                <div className="p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                                    <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Endpoints</span>
                                    <span className="text-lg font-bold text-purple-400">{endpoints.length}</span>
                                </div>
                                <div className="p-3 rounded-lg bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                                    <span className="text-[10px] text-zinc-500 uppercase font-semibold block">UI Views</span>
                                    <span className="text-lg font-bold text-pink-400">{uiComponents.length}</span>
                                </div>
                            </div>

                            <div className="pt-2 font-mono text-xs text-zinc-400 space-y-1.5 bg-[var(--surface-0)] p-3 rounded-lg border border-[var(--border-subtle)]">
                                <div className="flex justify-between">
                                    <span className="text-zinc-500">Tech Stack:</span>
                                    <span className="text-zinc-300">Next.js 15 · FastAPI · PostgreSQL</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-zinc-500">Authentication:</span>
                                    <span className={withAuth ? 'text-amber-400' : 'text-zinc-500'}>
                                        {withAuth ? 'Enabled (JWT + Users table)' : 'Disabled'}
                                    </span>
                                </div>
                            </div>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center justify-between pt-2">
                            <button
                                onClick={() => setCurrentStep(3)}
                                className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
                            >
                                <ArrowLeft size={13} /> Edit Spec
                            </button>
                            <button
                                onClick={handleCreate}
                                disabled={loading}
                                className="flex items-center gap-2.5 px-8 py-3.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 text-white font-semibold rounded-xl shadow-xl shadow-blue-600/25 transition-all text-xs hover:scale-[1.01]"
                            >
                                {loading ? <Loader2 size={16} className="animate-spin" /> : <Rocket size={16} />}
                                {loading ? 'Creating repository & committing...' : 'Initialize & First Commit'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
