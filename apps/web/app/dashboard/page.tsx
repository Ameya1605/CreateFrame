'use client';

import React, { useState, useEffect } from 'react';
import api from '@/lib/api';
import {
    Plus, Github, Loader2, LogOut, Cpu, Trash2,
    Folder, FolderOpen, ChevronRight, Sparkles,
    GitBranch, Zap, Search, X, Database, Globe,
    LayoutPanelTop, Clock
} from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function Dashboard() {
    const router = useRouter();
    const [projects, setProjects] = useState<any[]>([]);
    const [githubRepos, setGithubRepos] = useState<any[]>([]);
    const [selectedRepo, setSelectedRepo] = useState('');
    const [projectName, setProjectName] = useState('');
    const [loading, setLoading] = useState(true);
    const [creating, setCreating] = useState(false);
    const [username, setUsername] = useState('');
    const [activeProject, setActiveProject] = useState<any>(null);
    const [sidebarSearch, setSidebarSearch] = useState('');
    const [showNewPanel, setShowNewPanel] = useState(false);
    const [generatingAll, setGeneratingAll] = useState(false);
    const [confirmDelete, setConfirmDelete] = useState<number | null>(null);

    useEffect(() => {
        setUsername(localStorage.getItem('username') || '');
        fetchInitialData();
    }, []);

    const fetchInitialData = async () => {
        setLoading(true);
        try {
            const results = await Promise.allSettled([
                api.get('/projects'),
                api.get('/github/repos')
            ]);
            const projResult = results[0];
            const repoResult = results[1];
            if (projResult.status === 'fulfilled') {
                setProjects(projResult.value.data);
                if (projResult.value.data.length > 0 && !activeProject) {
                    setActiveProject(projResult.value.data[0]);
                }
            } else if ((projResult as any).reason?.response?.status === 401) {
                localStorage.clear();
                router.push('/');
                return;
            }
            if (repoResult.status === 'fulfilled') {
                setGithubRepos(repoResult.value.data);
            }
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const createProject = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!selectedRepo) return;
        setCreating(true);
        try {
            const res = await api.post('/projects', {
                name: projectName || selectedRepo.split('/')[1],
                repo_url: selectedRepo
            });
            setProjectName('');
            setSelectedRepo('');
            setShowNewPanel(false);
            await fetchInitialData();
            router.push(`/project/${res.data.id}`);
        } catch (err) {
            console.error(err);
        } finally {
            setCreating(false);
        }
    };

    const deleteProject = async (id: number) => {
        try {
            await api.delete(`/projects/${id}`);
            if (activeProject?.id === id) setActiveProject(null);
            setConfirmDelete(null);
            await fetchInitialData();
        } catch (err) {
            console.error(err);
        }
    };

    const generateAllCode = async (projectId: number) => {
        setGeneratingAll(true);
        try {
            await api.post(`/projects/${projectId}/commit`);
        } catch {
            // handled silently
        } finally {
            setGeneratingAll(false);
        }
    };

    const handleLogout = () => {
        localStorage.clear();
        router.push('/');
    };

    const filteredProjects = projects.filter(p =>
        p.name.toLowerCase().includes(sidebarSearch.toLowerCase())
    );

    const repoShortName = (url: string) => url?.split('/').pop() || url;

    return (
        <div className="h-screen bg-[var(--surface-0)] text-zinc-100 flex flex-col overflow-hidden">

            {/* ── Title Bar ── */}
            <div className="h-12 bg-[var(--surface-1)] border-b border-[var(--border)] flex items-center justify-between px-5 select-none shrink-0 gradient-border">
                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2.5">
                        <div className="bg-blue-500/10 p-1.5 rounded-lg">
                            <Cpu size={14} className="text-blue-400" />
                        </div>
                        <span className="text-sm text-zinc-300 font-bold tracking-wider uppercase">CreateFrame</span>
                        <span className="text-zinc-600 text-xs font-medium">workspace</span>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2.5 text-sm text-zinc-400">
                        <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                        <span className="font-medium">{username}</span>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="p-2 text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 rounded-lg transition-all"
                        title="Sign out"
                    >
                        <LogOut size={15} />
                    </button>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">

                {/* ── Sidebar ── */}
                <div className="w-64 bg-[var(--surface-1)] border-r border-[var(--border)] flex flex-col shrink-0">
                    {/* Sidebar header */}
                    <div className="px-4 pt-4 pb-3 flex items-center justify-between">
                        <span className="text-xs font-semibold uppercase tracking-widest text-zinc-500">Explorer</span>
                        <div className="flex items-center gap-1">
                            <button
                                onClick={() => router.push('/new-project')}
                                title="New Project from scratch"
                                className="p-1.5 text-zinc-500 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-all"
                            >
                                <Sparkles size={14} />
                            </button>
                            <button
                                onClick={() => setShowNewPanel(v => !v)}
                                title="Link existing repo"
                                className="p-1.5 text-zinc-500 hover:text-white hover:bg-zinc-800 rounded-lg transition-all"
                            >
                                <Plus size={14} />
                            </button>
                        </div>
                    </div>

                    {/* Search */}
                    <div className="px-3 pb-3">
                        <div className="flex items-center gap-2 bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-3 py-2 focus-within:border-blue-500/40 transition-colors">
                            <Search size={13} className="text-zinc-500 shrink-0" />
                            <input
                                value={sidebarSearch}
                                onChange={e => setSidebarSearch(e.target.value)}
                                placeholder="Filter workspaces..."
                                className="bg-transparent text-xs text-zinc-300 placeholder:text-zinc-600 outline-none w-full"
                            />
                        </div>
                    </div>

                    {/* Project list */}
                    <div className="flex-1 overflow-y-auto px-2 space-y-0.5">
                        {loading ? (
                            <div className="space-y-2 px-2 py-4">
                                {[1, 2, 3].map(i => (
                                    <div key={i} className="skeleton h-9 w-full" />
                                ))}
                            </div>
                        ) : filteredProjects.length === 0 ? (
                            <div className="px-4 py-8 text-center">
                                <Folder size={24} className="text-zinc-700 mx-auto mb-2" />
                                <p className="text-xs text-zinc-600">No workspaces yet.</p>
                            </div>
                        ) : (
                            filteredProjects.map(p => (
                                <div
                                    key={p.id}
                                    role="button"
                                    tabIndex={0}
                                    onClick={() => setActiveProject(p)}
                                    onKeyDown={(e) => {
                                        if (e.key === 'Enter' || e.key === ' ') {
                                            e.preventDefault();
                                            setActiveProject(p);
                                        }
                                    }}
                                    className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg text-left transition-all group cursor-pointer ${activeProject?.id === p.id
                                        ? 'bg-blue-500/10 text-white border border-blue-500/20'
                                        : 'text-zinc-400 hover:bg-[var(--surface-2)] hover:text-zinc-200 border border-transparent'
                                        }`}
                                >
                                    {activeProject?.id === p.id
                                        ? <FolderOpen size={15} className="text-blue-400 shrink-0" />
                                        : <Folder size={15} className="text-zinc-600 shrink-0" />
                                    }
                                    <div className="flex-1 min-w-0">
                                        <span className="text-[13px] truncate block font-medium">{p.name}</span>
                                        <span className="text-[11px] text-zinc-600 truncate block">{repoShortName(p.repo_url)}</span>
                                    </div>
                                    {confirmDelete === p.id ? (
                                        <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                                            <button
                                                onClick={() => deleteProject(p.id)}
                                                className="text-[10px] px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded font-bold hover:bg-red-500/30 transition-colors"
                                            >
                                                Yes
                                            </button>
                                            <button
                                                onClick={() => setConfirmDelete(null)}
                                                className="text-[10px] px-1.5 py-0.5 bg-zinc-800 text-zinc-400 rounded font-bold hover:bg-zinc-700 transition-colors"
                                            >
                                                No
                                            </button>
                                        </div>
                                    ) : (
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setConfirmDelete(p.id);
                                            }}
                                            className="opacity-0 group-hover:opacity-100 p-1 text-zinc-600 hover:text-red-400 transition-all rounded hover:bg-red-500/10"
                                        >
                                            <Trash2 size={12} />
                                        </button>
                                    )}
                                </div>
                            ))
                        )}
                    </div>

                    {/* New project panel */}
                    {showNewPanel && (
                        <div className="border-t border-[var(--border)] p-4 bg-[var(--surface-0)] animate-slide-up">
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-xs font-semibold uppercase tracking-widest text-zinc-400">Link Repository</span>
                                <button onClick={() => setShowNewPanel(false)} className="p-1 text-zinc-600 hover:text-white rounded hover:bg-zinc-800 transition-all">
                                    <X size={14} />
                                </button>
                            </div>
                            <form onSubmit={createProject} className="space-y-3">
                                <select
                                    className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-xs text-zinc-300 outline-none focus:border-blue-500/50 transition-colors appearance-none cursor-pointer"
                                    value={selectedRepo}
                                    onChange={(e) => {
                                        if (e.target.value === 'NEW') router.push('/new-project');
                                        else setSelectedRepo(e.target.value);
                                    }}
                                    required
                                >
                                    <option value="">Select repo...</option>
                                    <option value="NEW">✦ Create new repo</option>
                                    {githubRepos.map((repo: any) => (
                                        <option key={repo.id} value={repo.full_name}>{repo.full_name}</option>
                                    ))}
                                </select>
                                <input
                                    type="text"
                                    placeholder="Workspace name (optional)"
                                    className="w-full bg-[var(--surface-2)] border border-[var(--border)] rounded-lg px-3 py-2.5 text-xs text-zinc-300 outline-none focus:border-blue-500/50 transition-colors placeholder:text-zinc-600"
                                    value={projectName}
                                    onChange={(e) => setProjectName(e.target.value)}
                                />
                                <button
                                    type="submit"
                                    disabled={!selectedRepo || creating}
                                    className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-bold py-2.5 rounded-lg transition-all flex items-center justify-center gap-2 active:scale-[0.98]"
                                >
                                    {creating ? <Loader2 size={13} className="animate-spin" /> : <Plus size={13} />}
                                    {creating ? 'Creating...' : 'Create Workspace'}
                                </button>
                            </form>
                        </div>
                    )}
                </div>

                {/* ── Main Editor Area ── */}
                <div className="flex-1 flex flex-col overflow-hidden bg-[var(--surface-0)]">
                    {activeProject ? (
                        <>
                            {/* Tab bar */}
                            <div className="h-10 border-b border-[var(--border)] flex items-center shrink-0 bg-[var(--surface-1)]">
                                <div className="flex items-center gap-2.5 px-5 py-2 border-r border-[var(--border)] bg-[var(--surface-0)] h-full">
                                    <Folder size={13} className="text-blue-400" />
                                    <span className="text-[13px] text-zinc-300 font-medium">{activeProject.name}</span>
                                    <div className="w-2 h-2 rounded-full bg-emerald-400 ml-1" />
                                </div>
                            </div>

                            {/* Content */}
                            <div className="flex-1 overflow-auto p-8 sm:p-10">
                                <div className="max-w-3xl mx-auto space-y-8 animate-fade">

                                    {/* Project header */}
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <div className="flex items-center gap-2 text-blue-400 text-xs font-semibold uppercase tracking-widest mb-2">
                                                <GitBranch size={13} />
                                                <span>main</span>
                                            </div>
                                            <h1 className="text-2xl sm:text-3xl font-bold text-white tracking-tight leading-tight">
                                                {activeProject.name}
                                            </h1>
                                            <p className="text-zinc-500 text-sm mt-1.5 font-mono">{activeProject.repo_url}</p>
                                        </div>
                                        <div className="flex items-center gap-2.5">
                                            <button
                                                onClick={() => router.push(`/project/${activeProject.id}`)}
                                                className="btn-secondary text-xs"
                                            >
                                                Open Workspace
                                                <ChevronRight size={13} />
                                            </button>
                                            <button
                                                onClick={() => generateAllCode(activeProject.id)}
                                                disabled={generatingAll}
                                                className="btn-primary text-xs"
                                            >
                                                {generatingAll
                                                    ? <Loader2 size={13} className="animate-spin" />
                                                    : <Zap size={13} />
                                                }
                                                {generatingAll ? 'Generating...' : 'Generate & Commit'}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Divider */}
                                    <div className="border-t border-[var(--border)]" />

                                    {/* README-style spec preview */}
                                    <div className="space-y-2">
                                        <p className="text-xs uppercase tracking-widest font-semibold text-zinc-500">README.spec</p>
                                        <div className="bg-[var(--surface-1)] border border-[var(--border)] rounded-xl p-6 font-mono text-sm leading-7">
                                            <div className="text-zinc-400">{`# ${activeProject.name}`}</div>
                                            <div className="text-zinc-600 mt-1">{`> Linked to ${activeProject.repo_url}`}</div>
                                            <div className="mt-4 text-zinc-400">
                                                Open the workspace editor to define your architecture layers —<br />
                                                <span className="text-blue-400">features</span>, <span className="text-emerald-400">schemas</span>, <span className="text-purple-400">endpoints</span>, and <span className="text-pink-400">UI components</span>.
                                            </div>
                                            <div className="mt-4 text-zinc-600">
                                                {`$ createframe generate --all   # AI generates code for each layer`}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Quick actions */}
                                    <div>
                                        <p className="text-xs uppercase tracking-widest font-semibold text-zinc-500 mb-4">Quick Actions</p>
                                        <div className="grid grid-cols-3 gap-4 stagger-children">
                                            {[
                                                { label: 'Edit Architecture', desc: 'Add features, schemas, endpoints', icon: Folder, color: 'group-hover:text-blue-400 group-hover:border-blue-500/30', action: () => router.push(`/project/${activeProject.id}`) },
                                                { label: 'Generate Codebase', desc: 'AI writes all layers & commits', icon: Zap, color: 'group-hover:text-amber-400 group-hover:border-amber-500/30', action: () => generateAllCode(activeProject.id) },
                                                { label: 'New Project', desc: 'Scaffold from scratch with AI', icon: Sparkles, color: 'group-hover:text-purple-400 group-hover:border-purple-500/30', action: () => router.push('/new-project') },
                                            ].map(({ label, desc, icon: Icon, color, action }) => (
                                                <button
                                                    key={label}
                                                    onClick={action}
                                                    className={`group text-left p-5 bg-[var(--surface-1)] border border-[var(--border)] rounded-xl hover:bg-[var(--surface-2)] transition-all duration-200 ${color}`}
                                                >
                                                    <Icon size={18} className="text-zinc-600 group-hover:scale-110 transition-all mb-3" />
                                                    <p className="text-sm font-semibold text-zinc-300 group-hover:text-white transition-colors">{label}</p>
                                                    <p className="text-xs text-zinc-600 mt-1 leading-relaxed">{desc}</p>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        /* Empty state */
                        <div className="flex-1 flex flex-col items-center justify-center text-center p-12 animate-fade">
                            <div className="w-20 h-20 rounded-2xl bg-[var(--surface-2)] border border-[var(--border)] flex items-center justify-center mb-6">
                                <Cpu size={32} className="text-zinc-600" />
                            </div>
                            <h2 className="text-xl font-bold text-zinc-300 mb-2">No workspace open</h2>
                            <p className="text-sm text-zinc-500 max-w-xs mb-8 leading-relaxed">
                                Select a workspace from the sidebar, or create a new one to start architecting.
                            </p>
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={() => setShowNewPanel(true)}
                                    className="btn-secondary text-sm"
                                >
                                    <Plus size={15} /> Link Repo
                                </button>
                                <button
                                    onClick={() => router.push('/new-project')}
                                    className="btn-primary text-sm"
                                >
                                    <Sparkles size={15} /> New with AI
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
