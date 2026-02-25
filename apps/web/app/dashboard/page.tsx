'use client';

import React, { useState, useEffect } from 'react';
import api from '@/lib/api';
import {
    Plus, Github, Loader2, LogOut, Cpu, Trash2,
    Folder, FolderOpen, ChevronRight, Sparkles,
    GitBranch, Zap, Search, X
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

    const deleteProject = async (id: number, e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!confirm('Remove this workspace from SpecOS? Your GitHub repo will not be affected.')) return;
        try {
            await api.delete(`/projects/${id}`);
            if (activeProject?.id === id) setActiveProject(null);
            await fetchInitialData();
        } catch (err) {
            console.error(err);
        }
    };

    const generateAllCode = async (projectId: number) => {
        setGeneratingAll(true);
        try {
            await api.post(`/projects/${projectId}/commit`);
            alert('Codebase committed to GitHub!');
        } catch (err) {
            alert('Generate failed. Check the backend logs.');
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
    const repoOwner = (url: string) => url?.split('/').slice(-2, -1)[0] || '';

    return (
        <div className="h-screen bg-[#0d0d0f] text-zinc-100 font-mono flex flex-col overflow-hidden">

            {/* ── Title Bar ── */}
            <div className="h-11 bg-[#111113] border-b border-zinc-800/60 flex items-center justify-between px-4 select-none shrink-0">
                <div className="flex items-center gap-3">
                    <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-zinc-700" />
                        <div className="w-3 h-3 rounded-full bg-zinc-700" />
                        <div className="w-3 h-3 rounded-full bg-zinc-700" />
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                        <Cpu size={14} className="text-blue-500" />
                        <span className="text-xs text-zinc-400 font-bold tracking-wider uppercase">SpecOS</span>
                        <span className="text-zinc-700 text-xs">— workspace</span>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2 text-xs text-zinc-500">
                        <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                        <span>{username}</span>
                    </div>
                    <button
                        onClick={handleLogout}
                        className="p-1.5 text-zinc-600 hover:text-zinc-300 transition-colors"
                        title="Sign out"
                    >
                        <LogOut size={14} />
                    </button>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">

                {/* ── Sidebar ── */}
                <div className="w-60 bg-[#111113] border-r border-zinc-800/60 flex flex-col shrink-0">
                    {/* Sidebar header */}
                    <div className="px-4 pt-4 pb-2 flex items-center justify-between">
                        <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-600">Explorer</span>
                        <div className="flex items-center gap-1">
                            <button
                                onClick={() => router.push('/new-project')}
                                title="New Project from scratch"
                                className="p-1 text-zinc-600 hover:text-blue-400 transition-colors"
                            >
                                <Sparkles size={13} />
                            </button>
                            <button
                                onClick={() => setShowNewPanel(v => !v)}
                                title="Link existing repo"
                                className="p-1 text-zinc-600 hover:text-white transition-colors"
                            >
                                <Plus size={13} />
                            </button>
                        </div>
                    </div>

                    {/* Search */}
                    <div className="px-3 pb-2">
                        <div className="flex items-center gap-2 bg-zinc-900/60 border border-zinc-800/60 rounded px-2 py-1">
                            <Search size={11} className="text-zinc-600 shrink-0" />
                            <input
                                value={sidebarSearch}
                                onChange={e => setSidebarSearch(e.target.value)}
                                placeholder="Filter workspaces..."
                                className="bg-transparent text-[11px] text-zinc-300 placeholder:text-zinc-700 outline-none w-full"
                            />
                        </div>
                    </div>

                    {/* Project list */}
                    <div className="flex-1 overflow-y-auto px-1">
                        {loading ? (
                            <div className="flex justify-center py-8">
                                <Loader2 size={16} className="animate-spin text-zinc-600" />
                            </div>
                        ) : filteredProjects.length === 0 ? (
                            <p className="text-[10px] text-zinc-700 px-4 py-4">No workspaces yet.</p>
                        ) : (
                            filteredProjects.map(p => (
                                <button
                                    key={p.id}
                                    onClick={() => setActiveProject(p)}
                                    className={`w-full flex items-center gap-2 px-3 py-1.5 rounded text-left transition-all group ${activeProject?.id === p.id
                                        ? 'bg-blue-600/15 text-white'
                                        : 'text-zinc-500 hover:bg-zinc-800/40 hover:text-zinc-300'
                                        }`}
                                >
                                    {activeProject?.id === p.id
                                        ? <FolderOpen size={13} className="text-blue-400 shrink-0" />
                                        : <Folder size={13} className="shrink-0" />
                                    }
                                    <span className="text-[12px] truncate flex-1 font-medium">{p.name}</span>
                                    <button
                                        onClick={(e) => deleteProject(p.id, e)}
                                        className="opacity-0 group-hover:opacity-100 p-0.5 text-zinc-600 hover:text-red-500 transition-all"
                                    >
                                        <Trash2 size={11} />
                                    </button>
                                </button>
                            ))
                        )}
                    </div>

                    {/* New project panel */}
                    {showNewPanel && (
                        <div className="border-t border-zinc-800/60 p-4 bg-[#0d0d0f]">
                            <div className="flex items-center justify-between mb-3">
                                <span className="text-[10px] font-bold uppercase tracking-widest text-zinc-500">Link Repository</span>
                                <button onClick={() => setShowNewPanel(false)} className="text-zinc-600 hover:text-white">
                                    <X size={13} />
                                </button>
                            </div>
                            <form onSubmit={createProject} className="space-y-3">
                                <select
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-2 text-xs text-zinc-300 outline-none focus:border-blue-500 transition-colors appearance-none"
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
                                    className="w-full bg-zinc-900 border border-zinc-700 rounded px-2 py-2 text-xs text-zinc-300 outline-none focus:border-blue-500 transition-colors placeholder:text-zinc-700"
                                    value={projectName}
                                    onChange={(e) => setProjectName(e.target.value)}
                                />
                                <button
                                    type="submit"
                                    disabled={!selectedRepo || creating}
                                    className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white text-xs font-bold py-2 rounded transition-colors flex items-center justify-center gap-1.5"
                                >
                                    {creating ? <Loader2 size={11} className="animate-spin" /> : <Plus size={11} />}
                                    {creating ? 'Creating...' : 'Create Workspace'}
                                </button>
                            </form>
                        </div>
                    )}
                </div>

                {/* ── Main Editor Area ── */}
                <div className="flex-1 flex flex-col overflow-hidden bg-[#0d0d0f]">
                    {activeProject ? (
                        <>
                            {/* Tab bar */}
                            <div className="h-9 border-b border-zinc-800/60 flex items-center shrink-0 bg-[#111113]">
                                <div className="flex items-center gap-2 px-4 py-1 border-r border-zinc-800/60 bg-[#0d0d0f] h-full">
                                    <Folder size={12} className="text-blue-400" />
                                    <span className="text-xs text-zinc-300">{activeProject.name}</span>
                                    <div className="w-1.5 h-1.5 rounded-full bg-green-500 ml-1" />
                                </div>
                            </div>

                            {/* Content */}
                            <div className="flex-1 overflow-auto p-8">
                                <div className="max-w-3xl mx-auto space-y-8">

                                    {/* Project header */}
                                    <div className="flex items-start justify-between">
                                        <div>
                                            <div className="flex items-center gap-2 text-blue-500 text-xs font-bold uppercase tracking-widest mb-2">
                                                <GitBranch size={12} />
                                                <span>main</span>
                                            </div>
                                            <h1 className="text-3xl font-bold text-white tracking-tight leading-tight">
                                                {activeProject.name}
                                            </h1>
                                            <p className="text-zinc-600 text-sm mt-1 font-mono">{activeProject.repo_url}</p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => router.push(`/project/${activeProject.id}`)}
                                                className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white text-xs font-bold rounded-lg transition-all border border-zinc-700"
                                            >
                                                Open Workspace
                                                <ChevronRight size={12} />
                                            </button>
                                            <button
                                                onClick={() => generateAllCode(activeProject.id)}
                                                disabled={generatingAll}
                                                className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-all shadow-lg shadow-blue-500/20"
                                            >
                                                {generatingAll
                                                    ? <Loader2 size={12} className="animate-spin" />
                                                    : <Zap size={12} />
                                                }
                                                {generatingAll ? 'Generating...' : 'Generate & Commit'}
                                            </button>
                                        </div>
                                    </div>

                                    {/* Divider */}
                                    <div className="border-t border-zinc-800/60" />

                                    {/* README-style spec preview */}
                                    <div className="space-y-2">
                                        <p className="text-[10px] uppercase tracking-widest font-bold text-zinc-600">README.spec</p>
                                        <div className="bg-[#111113] border border-zinc-800/60 rounded-xl p-6 font-mono text-sm leading-7">
                                            <div className="text-zinc-500">{`# ${activeProject.name}`}</div>
                                            <div className="text-zinc-700 mt-1">{`> Linked to ${activeProject.repo_url}`}</div>
                                            <div className="mt-4 text-zinc-500">
                                                Open the workspace editor to define your architecture layers —<br />
                                                <span className="text-blue-400">features</span>, <span className="text-emerald-400">schemas</span>, <span className="text-purple-400">endpoints</span>, and <span className="text-pink-400">UI components</span>.
                                            </div>
                                            <div className="mt-4 text-zinc-700">
                                                {`$ specos generate --all   # AI generates code for each layer`}
                                            </div>
                                        </div>
                                    </div>

                                    {/* Quick actions */}
                                    <div>
                                        <p className="text-[10px] uppercase tracking-widest font-bold text-zinc-600 mb-3">Quick Actions</p>
                                        <div className="grid grid-cols-3 gap-3">
                                            {[
                                                { label: 'Edit Architecture', desc: 'Add features, schemas, endpoints', icon: Folder, action: () => router.push(`/project/${activeProject.id}`) },
                                                { label: 'Generate Codebase', desc: 'AI writes all layers & commits', icon: Zap, action: () => generateAllCode(activeProject.id) },
                                                { label: 'New Project', desc: 'Scaffold from scratch with AI', icon: Sparkles, action: () => router.push('/new-project') },
                                            ].map(({ label, desc, icon: Icon, action }) => (
                                                <button
                                                    key={label}
                                                    onClick={action}
                                                    className="group text-left p-4 bg-[#111113] border border-zinc-800/60 rounded-xl hover:border-zinc-600 transition-all"
                                                >
                                                    <Icon size={16} className="text-zinc-600 group-hover:text-blue-400 transition-colors mb-3" />
                                                    <p className="text-xs font-bold text-zinc-300 group-hover:text-white transition-colors">{label}</p>
                                                    <p className="text-[10px] text-zinc-700 mt-0.5 leading-relaxed">{desc}</p>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        /* Empty state */
                        <div className="flex-1 flex flex-col items-center justify-center text-center p-12">
                            <div className="w-16 h-16 rounded-2xl bg-zinc-900 border border-zinc-800 flex items-center justify-center mb-6">
                                <Cpu size={28} className="text-zinc-700" />
                            </div>
                            <h2 className="text-xl font-bold text-zinc-400 mb-2">No workspace open</h2>
                            <p className="text-sm text-zinc-700 max-w-xs mb-8 leading-relaxed">
                                Select a workspace from the sidebar, or create a new one to start architecting.
                            </p>
                            <div className="flex items-center gap-3">
                                <button
                                    onClick={() => setShowNewPanel(true)}
                                    className="flex items-center gap-2 px-5 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-sm font-bold rounded-lg transition-all border border-zinc-700"
                                >
                                    <Plus size={14} /> Link Repo
                                </button>
                                <button
                                    onClick={() => router.push('/new-project')}
                                    className="flex items-center gap-2 px-5 py-2.5 bg-blue-600 hover:bg-blue-500 text-white text-sm font-bold rounded-lg transition-all shadow-lg shadow-blue-500/20"
                                >
                                    <Sparkles size={14} /> New with AI
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
