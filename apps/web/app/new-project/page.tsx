'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
    ArrowLeft, ChevronRight, Github, Rocket,
    Database, Check, Loader2, Sparkles,
    X, Plus, Terminal, Layout, Globe,
    Pencil, Trash2
} from 'lucide-react';
import api from '@/lib/api';

const METHOD_COLORS: Record<string, string> = {
    GET: 'text-emerald-400',
    POST: 'text-blue-400',
    PUT: 'text-yellow-400',
    PATCH: 'text-orange-400',
    DELETE: 'text-red-400',
};

export default function NewProjectWizard() {
    const router = useRouter();
    const [currentStep, setCurrentStep] = useState(1);
    const [loading, setLoading] = useState(false);
    const [brainstorming, setBrainstorming] = useState(false);

    React.useEffect(() => {
        if (typeof window !== 'undefined' && !localStorage.getItem('token')) {
            router.push('/');
        }
    }, [router]);

    // Step 1
    const [repoName, setRepoName] = useState('');
    const [isPrivate, setIsPrivate] = useState(false);
    const [withAuth, setWithAuth] = useState(true);

    // Step 2 — describe
    const [projectDescription, setProjectDescription] = useState('');

    // Step 3 — editable spec (after brainstorm)
    const [features, setFeatures] = useState<string[]>([]);
    const [schemas, setSchemas] = useState<any[]>([]);
    const [endpoints, setEndpoints] = useState<any[]>([]);
    const [uiComponents, setUiComponents] = useState<any[]>([]);

    // inline add states
    const [newFeature, setNewFeature] = useState('');
    const [newTable, setNewTable] = useState('');
    const [newRoute, setNewRoute] = useState('');
    const [newRouteMethod, setNewRouteMethod] = useState('GET');
    const [newComponent, setNewComponent] = useState('');

    const handleBrainstorm = async () => {
        if (!projectDescription) return;
        setBrainstorming(true);
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
            alert('AI brainstorm failed. Check authentication and try again.');
        } finally {
            setBrainstorming(false);
        }
    };

    const handleCreate = async () => {
        setLoading(true);
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
            alert('Failed to initialize. Check if repo name already exists on GitHub.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#0d0d0f] text-zinc-100 font-mono">
            {/* Title bar */}
            <div className="h-11 bg-[#111113] border-b border-zinc-800/60 flex items-center px-6 gap-4">
                <button
                    onClick={() => router.push('/dashboard')}
                    className="flex items-center gap-2 text-zinc-600 hover:text-zinc-300 text-xs transition-colors"
                >
                    <ArrowLeft size={13} /> dashboard
                </button>
                <span className="text-zinc-700">/</span>
                <span className="text-xs text-zinc-500">new-project.spec</span>

                {/* Step indicator */}
                <div className="ml-auto flex items-center gap-1">
                    {[1, 2, 3, 4].map(n => (
                        <div key={n} className={`w-6 h-1 rounded-full transition-all ${currentStep >= n ? 'bg-blue-500' : 'bg-zinc-800'}`} />
                    ))}
                </div>
            </div>

            <div className="max-w-2xl mx-auto px-6 py-16">

                {/* ── Step 1: Identity ── */}
                {currentStep === 1 && (
                    <div className="space-y-10 animate-fade">
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[10px] font-black font-sans">1</span>
                                <span className="text-zinc-500 text-sm font-sans">Identity</span>
                            </div>
                            <h1 className="text-4xl font-bold tracking-tight text-white mb-2">Name your project.</h1>
                            <p className="text-zinc-600 text-sm">This becomes your GitHub repository name.</p>
                        </div>

                        <div className="space-y-4">
                            <div className="relative">
                                <div className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-700 text-sm font-bold select-none">
                                    github.com/{localStorage.getItem('username') || 'you'}/
                                </div>
                                <input
                                    type="text"
                                    placeholder="my-project"
                                    className="w-full bg-[#111113] border border-zinc-800 rounded-xl pl-[220px] pr-4 py-4 text-lg font-bold text-white outline-none focus:border-blue-500 transition-colors placeholder:text-zinc-800"
                                    value={repoName}
                                    onChange={e => setRepoName(e.target.value.toLowerCase().replace(/\s+/g, '-'))}
                                    style={{ paddingLeft: `${(localStorage.getItem('username')?.length || 3) + 22}ch` }}
                                />
                            </div>

                            <label className="flex items-center gap-4 p-4 bg-[#111113] border border-zinc-800 rounded-xl cursor-pointer hover:border-zinc-700 transition-all">
                                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all shrink-0 ${isPrivate ? 'bg-blue-600 border-blue-600' : 'border-zinc-700'}`}>
                                    {isPrivate && <Check size={12} className="text-white" />}
                                </div>
                                <input type="checkbox" className="hidden" checked={isPrivate} onChange={e => setIsPrivate(e.target.checked)} />
                                <div>
                                    <p className="text-sm font-bold text-zinc-300">Private repository</p>
                                    <p className="text-xs text-zinc-600">Only accessible to you and collaborators</p>
                                </div>
                            </label>

                            <label className="flex items-center gap-4 p-4 bg-[#111113] border border-zinc-800 rounded-xl cursor-pointer hover:border-zinc-700 transition-all">
                                <div className={`w-5 h-5 rounded border-2 flex items-center justify-center transition-all shrink-0 ${withAuth ? 'bg-blue-600 border-blue-600' : 'border-zinc-700'}`}>
                                    {withAuth && <Check size={12} className="text-white" />}
                                </div>
                                <input type="checkbox" className="hidden" checked={withAuth} onChange={e => setWithAuth(e.target.checked)} />
                                <div>
                                    <p className="text-sm font-bold text-zinc-300">Include authentication</p>
                                    <p className="text-xs text-zinc-600">Adds users table, session handling, and protected routes</p>
                                </div>
                            </label>
                        </div>

                        <button
                            onClick={() => setCurrentStep(2)}
                            disabled={!repoName}
                            className="flex items-center gap-2 px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-30 text-white text-sm font-bold rounded-xl transition-all"
                        >
                            Continue <ChevronRight size={16} />
                        </button>
                    </div>
                )}

                {/* ── Step 2: Describe & Brainstorm ── */}
                {currentStep === 2 && (
                    <div className="space-y-10 animate-fade">
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-orange-500 text-white text-[10px] font-black font-sans">2</span>
                                <span className="text-zinc-500 text-sm font-sans">Blueprint</span>
                            </div>
                            <h1 className="text-4xl font-bold tracking-tight text-white mb-2">What are we building?</h1>
                            <p className="text-zinc-600 text-sm">Describe it — AI will draft your architecture.</p>
                        </div>

                        <div className="space-y-4">
                            <textarea
                                placeholder="e.g. A SaaS platform where freelancers can list services and clients book them with integrated payments and reviews."
                                className="w-full bg-[#111113] border border-zinc-800 rounded-xl p-5 text-sm text-zinc-200 outline-none focus:border-orange-500 transition-colors h-40 resize-none placeholder:text-zinc-700 leading-relaxed"
                                value={projectDescription}
                                onChange={e => setProjectDescription(e.target.value)}
                            />

                            <button
                                onClick={handleBrainstorm}
                                disabled={!projectDescription || brainstorming}
                                className="w-full flex items-center justify-center gap-3 py-4 bg-orange-500 hover:bg-orange-400 disabled:opacity-30 text-white font-bold rounded-xl transition-all text-sm"
                            >
                                {brainstorming ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                                {brainstorming ? 'AI is designing your architecture...' : 'Generate Architecture Draft'}
                            </button>

                            <div className="flex items-center gap-3">
                                <div className="flex-1 h-px bg-zinc-800" />
                                <span className="text-[10px] text-zinc-700 font-bold uppercase tracking-widest">or skip</span>
                                <div className="flex-1 h-px bg-zinc-800" />
                            </div>

                            <button
                                onClick={() => setCurrentStep(3)}
                                className="w-full py-3 border border-zinc-800 hover:border-zinc-700 text-zinc-500 hover:text-zinc-300 text-sm font-bold rounded-xl transition-all"
                            >
                                Start with empty spec
                            </button>
                        </div>

                        <button onClick={() => setCurrentStep(1)} className="text-xs text-zinc-700 hover:text-zinc-400 transition-colors">← back</button>
                    </div>
                )}

                {/* ── Step 3: Edit Spec ── */}
                {currentStep === 3 && (
                    <div className="space-y-8 animate-fade">
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-blue-600 text-white text-[10px] font-black font-sans">3</span>
                                <span className="text-zinc-500 text-sm font-sans">Spec Editor</span>
                            </div>
                            <h1 className="text-4xl font-bold tracking-tight text-white mb-2">Refine the spec.</h1>
                            <p className="text-zinc-600 text-sm">Edit, add, or remove anything before we write code.</p>
                        </div>

                        {/* Features */}
                        <section>
                            <div className="flex items-center gap-2 mb-3">
                                <Check size={13} className="text-blue-400" />
                                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Features</span>
                                <span className="text-zinc-700 text-[10px]">({features.length})</span>
                            </div>
                            <div className="bg-[#111113] border border-zinc-800 rounded-xl overflow-hidden">
                                {features.map((f, i) => (
                                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 border-b border-zinc-800/50 last:border-0 group hover:bg-zinc-900/30 transition-colors">
                                        <span className="text-zinc-600 text-xs w-4 text-right shrink-0">{i + 1}</span>
                                        <input
                                            value={f}
                                            onChange={e => setFeatures(features.map((v, idx) => idx === i ? e.target.value : v))}
                                            className="flex-1 bg-transparent text-sm text-zinc-300 outline-none focus:text-white"
                                        />
                                        <button onClick={() => setFeatures(features.filter((_, idx) => idx !== i))}
                                            className="opacity-0 group-hover:opacity-100 text-zinc-700 hover:text-red-500 transition-all">
                                            <X size={12} />
                                        </button>
                                    </div>
                                ))}
                                <div className="flex items-center gap-3 px-4 py-2.5">
                                    <Plus size={12} className="text-zinc-700 shrink-0" />
                                    <input
                                        value={newFeature}
                                        onChange={e => setNewFeature(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter' && newFeature.trim()) { setFeatures([...features, newFeature.trim()]); setNewFeature(''); } }}
                                        placeholder="Add feature... (press Enter)"
                                        className="flex-1 bg-transparent text-sm text-zinc-600 placeholder:text-zinc-800 outline-none focus:text-zinc-300"
                                    />
                                </div>
                            </div>
                        </section>

                        {/* Schemas */}
                        <section>
                            <div className="flex items-center gap-2 mb-3">
                                <Database size={13} className="text-emerald-400" />
                                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Database Tables</span>
                                <span className="text-zinc-700 text-[10px]">({schemas.length})</span>
                            </div>
                            <div className="bg-[#111113] border border-zinc-800 rounded-xl overflow-hidden">
                                {schemas.map((s, i) => (
                                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 border-b border-zinc-800/50 last:border-0 group hover:bg-zinc-900/30">
                                        <span className="text-emerald-600 text-[10px] font-bold w-12 uppercase shrink-0">model</span>
                                        <input
                                            value={s.table_name}
                                            onChange={e => setSchemas(schemas.map((v, idx) => idx === i ? { ...v, table_name: e.target.value } : v))}
                                            className="flex-1 bg-transparent text-sm text-emerald-300 outline-none"
                                        />
                                        <span className="text-zinc-700 text-[10px]">{s.fields?.length || 0} fields</span>
                                        <button onClick={() => setSchemas(schemas.filter((_, idx) => idx !== i))}
                                            className="opacity-0 group-hover:opacity-100 text-zinc-700 hover:text-red-500 transition-all">
                                            <X size={12} />
                                        </button>
                                    </div>
                                ))}
                                <div className="flex items-center gap-3 px-4 py-2.5">
                                    <Plus size={12} className="text-zinc-700 shrink-0" />
                                    <input
                                        value={newTable}
                                        onChange={e => setNewTable(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter' && newTable.trim()) { setSchemas([...schemas, { table_name: newTable.trim(), fields: [] }]); setNewTable(''); } }}
                                        placeholder="Add table... (press Enter)"
                                        className="flex-1 bg-transparent text-sm text-zinc-600 placeholder:text-zinc-800 outline-none focus:text-zinc-300"
                                    />
                                </div>
                            </div>
                        </section>

                        {/* Endpoints */}
                        <section>
                            <div className="flex items-center gap-2 mb-3">
                                <Terminal size={13} className="text-purple-400" />
                                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">API Endpoints</span>
                                <span className="text-zinc-700 text-[10px]">({endpoints.length})</span>
                            </div>
                            <div className="bg-[#111113] border border-zinc-800 rounded-xl overflow-hidden">
                                {endpoints.map((ep, i) => (
                                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 border-b border-zinc-800/50 last:border-0 group hover:bg-zinc-900/30">
                                        <select
                                            value={ep.method}
                                            onChange={e => setEndpoints(endpoints.map((v, idx) => idx === i ? { ...v, method: e.target.value } : v))}
                                            className={`bg-transparent text-[10px] font-bold uppercase outline-none cursor-pointer w-14 shrink-0 ${METHOD_COLORS[ep.method] || 'text-zinc-400'}`}
                                        >
                                            {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => <option key={m} value={m}>{m}</option>)}
                                        </select>
                                        <input
                                            value={ep.route}
                                            onChange={e => setEndpoints(endpoints.map((v, idx) => idx === i ? { ...v, route: e.target.value } : v))}
                                            className="flex-1 bg-transparent text-sm text-zinc-300 outline-none font-mono"
                                        />
                                        <button onClick={() => setEndpoints(endpoints.filter((_, idx) => idx !== i))}
                                            className="opacity-0 group-hover:opacity-100 text-zinc-700 hover:text-red-500 transition-all">
                                            <X size={12} />
                                        </button>
                                    </div>
                                ))}
                                <div className="flex items-center gap-3 px-4 py-2.5">
                                    <select
                                        value={newRouteMethod}
                                        onChange={e => setNewRouteMethod(e.target.value)}
                                        className={`bg-transparent text-[10px] font-bold uppercase outline-none cursor-pointer w-14 shrink-0 ${METHOD_COLORS[newRouteMethod]}`}
                                    >
                                        {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => <option key={m} value={m}>{m}</option>)}
                                    </select>
                                    <input
                                        value={newRoute}
                                        onChange={e => setNewRoute(e.target.value)}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter' && newRoute.trim()) {
                                                setEndpoints([...endpoints, { method: newRouteMethod, route: newRoute.trim(), request_schema: {}, response_schema: {} }]);
                                                setNewRoute('');
                                            }
                                        }}
                                        placeholder="/route (press Enter)"
                                        className="flex-1 bg-transparent text-sm text-zinc-600 placeholder:text-zinc-800 outline-none font-mono focus:text-zinc-300"
                                    />
                                </div>
                            </div>
                        </section>

                        {/* UI Components */}
                        <section>
                            <div className="flex items-center gap-2 mb-3">
                                <Layout size={13} className="text-pink-400" />
                                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">UI Components</span>
                                <span className="text-zinc-700 text-[10px]">({uiComponents.length})</span>
                            </div>
                            <div className="bg-[#111113] border border-zinc-800 rounded-xl overflow-hidden">
                                {uiComponents.map((c, i) => (
                                    <div key={i} className="flex items-center gap-3 px-4 py-2.5 border-b border-zinc-800/50 last:border-0 group hover:bg-zinc-900/30">
                                        <select
                                            value={c.type}
                                            onChange={e => setUiComponents(uiComponents.map((v, idx) => idx === i ? { ...v, type: e.target.value } : v))}
                                            className="bg-transparent text-[10px] font-bold uppercase text-pink-500 outline-none cursor-pointer w-20 shrink-0"
                                        >
                                            {['page', 'component', 'layout'].map(t => <option key={t} value={t}>{t}</option>)}
                                        </select>
                                        <input
                                            value={c.name}
                                            onChange={e => setUiComponents(uiComponents.map((v, idx) => idx === i ? { ...v, name: e.target.value } : v))}
                                            className="flex-1 bg-transparent text-sm text-zinc-300 outline-none"
                                        />
                                        <button onClick={() => setUiComponents(uiComponents.filter((_, idx) => idx !== i))}
                                            className="opacity-0 group-hover:opacity-100 text-zinc-700 hover:text-red-500 transition-all">
                                            <X size={12} />
                                        </button>
                                    </div>
                                ))}
                                <div className="flex items-center gap-3 px-4 py-2.5">
                                    <Plus size={12} className="text-zinc-700 shrink-0" />
                                    <input
                                        value={newComponent}
                                        onChange={e => setNewComponent(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter' && newComponent.trim()) { setUiComponents([...uiComponents, { name: newComponent.trim(), type: 'page' }]); setNewComponent(''); } }}
                                        placeholder="Add component... (press Enter)"
                                        className="flex-1 bg-transparent text-sm text-zinc-600 placeholder:text-zinc-800 outline-none focus:text-zinc-300"
                                    />
                                </div>
                            </div>
                        </section>

                        <div className="flex items-center justify-between pt-4">
                            <button onClick={() => setCurrentStep(2)} className="text-xs text-zinc-700 hover:text-zinc-400 transition-colors">← back</button>
                            <button
                                onClick={() => setCurrentStep(4)}
                                disabled={features.length === 0}
                                className="flex items-center gap-2 px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-30 text-white text-sm font-bold rounded-xl transition-all"
                            >
                                Looks good <ChevronRight size={16} />
                            </button>
                        </div>
                    </div>
                )}

                {/* ── Step 4: Launch ── */}
                {currentStep === 4 && (
                    <div className="space-y-10 animate-fade">
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <span className="inline-flex items-center justify-center w-5 h-5 rounded-full bg-green-600 text-white text-[10px] font-black font-sans">4</span>
                                <span className="text-zinc-500 text-sm font-sans">Launch</span>
                            </div>
                            <h1 className="text-4xl font-bold tracking-tight text-white mb-2">Ready to ship.</h1>
                            <p className="text-zinc-600 text-sm">We'll create the repo, commit your spec, and generate initial code.</p>
                        </div>

                        {/* Summary */}
                        <div className="bg-[#111113] border border-zinc-800 rounded-xl p-5 font-mono text-sm space-y-1.5">
                            <div className="text-zinc-600">{`# ${repoName}`}</div>
                            <div className="text-zinc-700">{`visibility:  ${isPrivate ? 'private' : 'public'}`}</div>
                            <div className="text-zinc-700">{`stack:       Next.js · FastAPI · PostgreSQL`}</div>
                            <div className={`${withAuth ? 'text-yellow-400' : 'text-zinc-700'}`}>{`auth:        ${withAuth ? 'yes — JWT + users table' : 'no'}`}</div>
                            <div className="mt-2 text-blue-400">{`features:    ${features.length}`}</div>
                            <div className="text-emerald-400">{`tables:      ${schemas.length}${withAuth ? ' + 1 (users)' : ''}`}</div>
                            <div className="text-purple-400">{`endpoints:   ${endpoints.length}${withAuth ? ' + auth routes' : ''}`}</div>
                            <div className="text-pink-400">{`ui:          ${uiComponents.length} components`}</div>
                        </div>

                        <div className="flex items-center justify-between">
                            <button onClick={() => setCurrentStep(3)} className="text-xs text-zinc-700 hover:text-zinc-400 transition-colors">← edit spec</button>
                            <button
                                onClick={handleCreate}
                                disabled={loading}
                                className="flex items-center gap-3 px-10 py-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-bold rounded-xl transition-all shadow-xl shadow-blue-500/20 text-sm"
                            >
                                {loading ? <Loader2 size={16} className="animate-spin" /> : <Rocket size={16} />}
                                {loading ? 'Creating repository...' : 'Initialize & First Commit'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
