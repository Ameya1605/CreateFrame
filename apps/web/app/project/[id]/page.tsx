'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import api from '@/lib/api';
import {
    ArrowLeft, Database, Globe, Loader2, Code2,
    X, LayoutPanelTop, Flag, Activity, Sparkles,
    ChevronRight, ChevronDown, File, Folder, FolderOpen,
    Send, Trash2, Plus, Check, AlertCircle, Inbox,
    Zap, Play, GitBranch
} from 'lucide-react';

// ─── Types ────────────────────────────────────────────────────────────────────

interface GeneratedFile {
    type: 'schemas' | 'endpoints' | 'ui-components';
    itemId: number;
    fileName: string;
    filePath: string;
    code: string;
    committed: boolean;
}

interface FeatureImpl {
    featureId: number;
    files: GeneratedFile[];
    implementing: boolean;
    done: boolean;
}

interface TreeNode {
    name: string;
    type: 'file' | 'folder';
    path: string;
    children?: TreeNode[];
    hasCode?: boolean;
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function slug(s: string) {
    return s.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');
}

function pascal(s: string) {
    return s.split(/\s+/).map(w => w.charAt(0).toUpperCase() + w.slice(1)).join('');
}

// Derive what files a feature needs based on spec data
function deriveFilePlan(
    feature: any,
    schemas: any[],
    endpoints: any[],
    uiComponents: any[]
): Array<{ type: 'schemas' | 'endpoints' | 'ui-components'; item: any; fileName: string; filePath: string }> {
    const featureName = feature.name as string;
    const plan: Array<{ type: 'schemas' | 'endpoints' | 'ui-components'; item: any; fileName: string; filePath: string }> = [];

    // Find related schema (fuzzy match)
    const relatedSchema = schemas.find(s =>
        featureName.toLowerCase().includes(s.table_name.toLowerCase()) ||
        s.table_name.toLowerCase().includes(featureName.toLowerCase().split(' ')[0])
    );
    if (relatedSchema) {
        plan.push({
            type: 'schemas',
            item: relatedSchema,
            fileName: `${relatedSchema.table_name}.prisma`,
            filePath: `packages/database/${relatedSchema.table_name}.prisma`
        });
    }

    // Find related endpoints
    const relatedEndpoints = endpoints.filter(e =>
        e.route.toLowerCase().includes(slug(featureName)) ||
        slug(featureName).split('-').some((word: string) => word.length > 3 && e.route.toLowerCase().includes(word))
    );
    relatedEndpoints.slice(0, 2).forEach(ep => {
        plan.push({
            type: 'endpoints',
            item: ep,
            fileName: `${ep.method.toLowerCase()}_${ep.route.replace(/\//g, '_').replace(/^_/, '')}.py`,
            filePath: `apps/api/routes/${ep.method.toLowerCase()}_${ep.route.replace(/\//g, '_').replace(/^_/, '')}.py`
        });
    });

    // Find related UI component
    const relatedUI = uiComponents.find(c =>
        c.name.toLowerCase().includes(featureName.toLowerCase().split(' ')[0]) ||
        featureName.toLowerCase().includes(c.name.toLowerCase())
    ) || uiComponents.find(c => c.name === featureName);
    if (relatedUI) {
        plan.push({
            type: 'ui-components',
            item: relatedUI,
            fileName: `${pascal(relatedUI.name)}.tsx`,
            filePath: `apps/web/app/${pascal(relatedUI.name)}.tsx`
        });
    }

    // If nothing matched, create sensible defaults
    if (plan.length === 0) {
        const firstEndpoint = endpoints[0];
        const firstUI = uiComponents.find(c => c.type === 'page') || uiComponents[0];
        if (firstUI) {
            plan.push({
                type: 'ui-components',
                item: { ...firstUI, name: featureName },
                fileName: `${pascal(featureName)}.tsx`,
                filePath: `apps/web/app/${pascal(featureName)}.tsx`
            });
        }
        if (firstEndpoint) {
            plan.push({
                type: 'endpoints',
                item: { ...firstEndpoint, route: `/${slug(featureName)}` },
                fileName: `${slug(featureName)}.py`,
                filePath: `apps/api/routes/${slug(featureName)}.py`
            });
        }
    }

    return plan;
}

// ─── File Tree ────────────────────────────────────────────────────────────────

function TreeItem({ node, depth = 0, onSelect, selectedPath }: {
    node: TreeNode; depth?: number;
    onSelect: (n: TreeNode) => void; selectedPath: string;
}) {
    const [open, setOpen] = useState(depth < 2);
    const isSelected = node.path === selectedPath;

    if (node.type === 'folder') {
        return (
            <div>
                <button
                    onClick={() => setOpen(v => !v)}
                    className="w-full flex items-center gap-1.5 px-2 py-0.5 rounded text-zinc-600 hover:text-zinc-400 transition-colors"
                    style={{ paddingLeft: `${6 + depth * 12}px` }}
                >
                    {open ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
                    {open ? <FolderOpen size={11} className="text-blue-400/60 shrink-0" /> : <Folder size={11} className="text-zinc-700 shrink-0" />}
                    <span className="text-[11px] truncate">{node.name}</span>
                </button>
                {open && node.children?.map(c => (
                    <TreeItem key={c.path} node={c} depth={depth + 1} onSelect={onSelect} selectedPath={selectedPath} />
                ))}
            </div>
        );
    }

    return (
        <button
            onClick={() => onSelect(node)}
            className={`w-full flex items-center gap-1.5 py-0.5 rounded text-left transition-colors ${isSelected ? 'bg-blue-600/20 text-white' : 'text-zinc-600 hover:text-zinc-400'}`}
            style={{ paddingLeft: `${6 + depth * 12}px` }}
        >
            <File size={10} className={node.hasCode ? 'text-yellow-400 shrink-0' : 'text-zinc-800 shrink-0'} />
            <span className="text-[11px] truncate flex-1">{node.name}</span>
            {node.hasCode && <span className="w-1 h-1 rounded-full bg-yellow-400 mr-1 shrink-0" />}
        </button>
    );
}

// ─── Code Viewer ─────────────────────────────────────────────────────────────

function CodeViewer({ title, code, onChange, onClose }: {
    title: string; code: string;
    onChange: (v: string) => void; onClose: () => void;
}) {
    return (
        <div className="flex flex-col h-full bg-[#0a0a0c] border-l border-zinc-800/60">
            <div className="h-9 flex items-center justify-between px-3 border-b border-zinc-800/60 bg-[#111113] shrink-0">
                <div className="flex items-center gap-2">
                    <Code2 size={11} className="text-blue-400" />
                    <span className="text-[11px] text-zinc-400 font-mono">{title}</span>
                </div>
                <button onClick={onClose} className="p-1 text-zinc-600 hover:text-zinc-300"><X size={12} /></button>
            </div>
            <div className="flex flex-1 overflow-hidden font-mono">
                <div className="w-9 bg-[#111113] border-r border-zinc-800/40 flex flex-col items-end pt-3 pr-2 select-none overflow-hidden shrink-0">
                    {(code || '').split('\n').map((_, i) => (
                        <div key={i} className="text-[9px] text-zinc-800 leading-5">{i + 1}</div>
                    ))}
                </div>
                <textarea
                    className="flex-1 bg-transparent p-3 text-blue-200 resize-none outline-none text-[11px] leading-5"
                    value={code}
                    onChange={e => onChange(e.target.value)}
                    spellCheck={false}
                    placeholder="// Code appears here after generation"
                />
            </div>
        </div>
    );
}

// ─── Main ─────────────────────────────────────────────────────────────────────

const METHOD_COLOR: Record<string, string> = {
    GET: 'text-emerald-400', POST: 'text-blue-400',
    PUT: 'text-yellow-400', PATCH: 'text-orange-400', DELETE: 'text-red-400'
};

export default function ProjectDetail() {
    const { id } = useParams();
    const router = useRouter();

    const [project, setProject] = useState<any>(null);
    const [activeTab, setActiveTab] = useState('plan');
    const [loading, setLoading] = useState(true);
    const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

    // Spec data
    const [features, setFeatures] = useState<any[]>([]);
    const [schemas, setSchemas] = useState<any[]>([]);
    const [endpoints, setEndpoints] = useState<any[]>([]);
    const [uiComponents, setUiComponents] = useState<any[]>([]);

    // Plan tab state
    const [selectedFeature, setSelectedFeature] = useState<any>(null);
    const [filePlan, setFilePlan] = useState<ReturnType<typeof deriveFilePlan>>([]);
    const [implementations, setImplementations] = useState<Record<number, FeatureImpl>>({});
    const [openFile, setOpenFile] = useState<GeneratedFile | null>(null);

    // Drafts tray
    const [showDraftsTray, setShowDraftsTray] = useState(false);
    const [pushingAll, setPushingAll] = useState(false);

    // File tree
    const [treeVisible, setTreeVisible] = useState(true);
    const [selectedTreePath, setSelectedTreePath] = useState('');

    // Spec forms
    const [newFeature, setNewFeature] = useState('');
    const [newTable, setNewTable] = useState('');
    const [newRoute, setNewRoute] = useState('');
    const [newRouteMethod, setNewRouteMethod] = useState('GET');
    const [newUI, setNewUI] = useState('');

    const [genLogs, setGenLogs] = useState<string[]>([]);

    const showToast = useCallback((msg: string, ok = true) => {
        setToast({ msg, ok });
        setTimeout(() => setToast(null), 3000);
    }, []);

    useEffect(() => { fetchProjectData(); }, [id]);

    const fetchProjectData = async () => {
        setLoading(true);
        try {
            const [projRes, featRes, schemaRes, endRes, uiRes] = await Promise.all([
                api.get('/projects'),
                api.get(`/features?project_id=${id}`),
                api.get(`/schemas?project_id=${id}`),
                api.get(`/endpoints?project_id=${id}`),
                api.get(`/ui-components?project_id=${id}`),
            ]);
            const p = projRes.data.find((x: any) => x.id === Number(id));
            if (!p) { router.push('/dashboard'); return; }
            setProject(p);
            setFeatures(featRes.data);
            setSchemas(schemaRes.data);
            setEndpoints(endRes.data);
            setUiComponents(uiRes.data);
        } catch {
            showToast('Failed to load project', false);
        } finally {
            setLoading(false);
        }
    };

    const selectFeature = (f: any) => {
        setSelectedFeature(f);
        setOpenFile(null);
        const plan = deriveFilePlan(f, schemas, endpoints, uiComponents);
        setFilePlan(plan);
    };

    // Implement: generate all files for this feature
    const implementFeature = async (feature: any) => {
        const fid = feature.id;
        setImplementations(prev => ({
            ...prev,
            [fid]: { featureId: fid, files: [], implementing: true, done: false }
        }));
        setGenLogs([`> Bootstrapping workspace for "${feature.name}"...`]);

        const plan = deriveFilePlan(feature, schemas, endpoints, uiComponents);
        const generated: GeneratedFile[] = [];

        for (const p of plan) {
            setGenLogs(prev => [...prev.slice(-10), `> Generating ${p.fileName}...`]);
            try {
                const res = await api.post('/generate-code', {
                    item_type: p.type,
                    item_name: p.item.table_name || p.item.name || p.item.route || feature.name,
                    spec: JSON.stringify({ project, features, schemas, endpoints })
                });
                generated.push({
                    type: p.type,
                    itemId: p.item.id || 0,
                    fileName: p.fileName,
                    filePath: p.filePath,
                    code: res.data.code || '',
                    committed: false
                });
                setGenLogs(prev => [...prev.slice(-10), `  ✓ Built ${p.fileName}`]);
            } catch {
                generated.push({
                    type: p.type,
                    itemId: p.item.id || 0,
                    fileName: p.fileName,
                    filePath: p.filePath,
                    code: `// Generation failed for ${p.fileName}`,
                    committed: false
                });
                setGenLogs(prev => [...prev.slice(-10), `  ✗ Failed ${p.fileName}`]);
            }
        }

        setImplementations(prev => ({
            ...prev,
            [fid]: { featureId: fid, files: generated, implementing: false, done: true }
        }));
        setGenLogs(prev => [...prev.slice(-10), `> Completed implementation.`]);

        if (generated.length > 0) setOpenFile(generated[0]);
        showToast(`Generated ${generated.length} file${generated.length !== 1 ? 's' : ''} for "${feature.name}"`);
    };

    // Push all generated files for a feature to GitHub
    const pushFeature = async (feature: any) => {
        setPushingAll(true);
        try {
            await api.post(`/projects/${id}/commit`);
            setImplementations(prev => ({
                ...prev,
                [feature.id]: {
                    ...prev[feature.id],
                    files: prev[feature.id]?.files.map(f => ({ ...f, committed: true })) || []
                }
            }));
            showToast(`"${feature.name}" pushed to GitHub`);
        } catch {
            showToast('Push failed', false);
        } finally {
            setPushingAll(false);
        }
    };

    // Count all drafts across all features
    const allDraftFiles = Object.values(implementations)
        .flatMap(impl => impl.files.filter(f => !f.committed));

    const addItem = async (type: string, payload: any) => {
        try {
            const res = await api.post(`/${type}?project_id=${id}`, payload);
            if (type === 'features') setFeatures(f => [...f, res.data]);
            if (type === 'schemas') setSchemas(s => [...s, res.data]);
            if (type === 'endpoints') setEndpoints(e => [...e, res.data]);
            if (type === 'ui-components') setUiComponents(u => [...u, res.data]);
        } catch { showToast('Failed to add', false); }
    };

    const deleteItem = async (type: string, itemId: number) => {
        try {
            await api.delete(`/${type}/${itemId}`);
            if (type === 'features') { setFeatures(f => f.filter(i => i.id !== itemId)); if (selectedFeature?.id === itemId) setSelectedFeature(null); }
            if (type === 'schemas') setSchemas(s => s.filter(i => i.id !== itemId));
            if (type === 'endpoints') setEndpoints(e => e.filter(i => i.id !== itemId));
            if (type === 'ui-components') setUiComponents(u => u.filter(i => i.id !== itemId));
        } catch { showToast('Delete failed', false); }
    };

    // Build file tree from all generated implementations
    const buildTree = (): TreeNode[] => {
        const repoName = project?.repo_url?.split('/').pop() || 'repo';
        const allFiles = Object.values(implementations).flatMap(i => i.files);

        const dbFiles = allFiles.filter(f => f.type === 'schemas');
        const apiFiles = allFiles.filter(f => f.type === 'endpoints');
        const uiFiles = allFiles.filter(f => f.type === 'ui-components');

        return [{
            name: repoName, type: 'folder', path: '/',
            children: [
                ...(dbFiles.length ? [{
                    name: 'packages/database', type: 'folder' as const, path: '/packages/database',
                    children: dbFiles.map(f => ({ name: f.fileName, type: 'file' as const, path: `/${f.filePath}`, hasCode: true }))
                }] : []),
                ...(apiFiles.length ? [{
                    name: 'apps/api/routes', type: 'folder' as const, path: '/apps/api',
                    children: apiFiles.map(f => ({ name: f.fileName, type: 'file' as const, path: `/${f.filePath}`, hasCode: !f.committed }))
                }] : []),
                ...(uiFiles.length ? [{
                    name: 'apps/web/app', type: 'folder' as const, path: '/apps/web',
                    children: uiFiles.map(f => ({ name: f.fileName, type: 'file' as const, path: `/${f.filePath}`, hasCode: !f.committed }))
                }] : []),
                { name: 'README.md', type: 'file' as const, path: '/README.md' },
            ]
        }];
    };

    const handleTreeSelect = (node: TreeNode) => {
        setSelectedTreePath(node.path);
        const allFiles = Object.values(implementations).flatMap(i => i.files);
        const match = allFiles.find(f => `/${f.filePath}` === node.path);
        if (match) setOpenFile(match);
    };

    const NavItem = ({ tabId, icon: Icon, label, color }: any) => (
        <button
            onClick={() => setActiveTab(tabId)}
            className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-left transition-all ${activeTab === tabId ? 'bg-zinc-800/60 text-white' : 'text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800/30'}`}
        >
            <Icon size={14} className={activeTab === tabId ? color : ''} />
            <span className="text-xs font-medium">{label}</span>
        </button>
    );

    if (loading) return (
        <div className="h-screen bg-[#0d0d0f] flex items-center justify-center">
            <Loader2 className="animate-spin text-blue-500" size={24} />
        </div>
    );

    const impl = selectedFeature ? implementations[selectedFeature.id] : null;
    const implementedFileIds = new Set(
        Object.values(implementations).flatMap(i => i.files.map(f => f.filePath))
    );

    return (
        <div className="h-screen bg-[#0d0d0f] text-zinc-100 font-mono flex flex-col overflow-hidden">

            {/* Title bar */}
            <div className="h-11 bg-[#111113] border-b border-zinc-800/60 flex items-center justify-between px-4 shrink-0">
                <div className="flex items-center gap-2">
                    <button onClick={() => router.push('/dashboard')} className="text-zinc-600 hover:text-zinc-300 transition-colors">
                        <ArrowLeft size={14} />
                    </button>
                    <span className="text-zinc-700 text-xs">/</span>
                    <span className="text-xs text-zinc-400">{project?.name}</span>
                    {selectedFeature && activeTab === 'plan' && (
                        <>
                            <span className="text-zinc-700 text-xs">/</span>
                            <span className="text-xs text-yellow-400">{selectedFeature.name}</span>
                        </>
                    )}
                </div>

                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setShowDraftsTray(v => !v)}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold transition-all border ${allDraftFiles.length > 0 ? 'border-yellow-500/40 bg-yellow-500/10 text-yellow-400' : 'border-zinc-800 text-zinc-600 hover:text-zinc-400'}`}
                    >
                        <Inbox size={12} />
                        {allDraftFiles.length} draft{allDraftFiles.length !== 1 ? 's' : ''}
                    </button>
                    <button
                        onClick={() => selectedFeature && pushFeature(selectedFeature)}
                        disabled={!selectedFeature || !impl?.done || pushingAll}
                        className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-30 text-white text-xs font-bold rounded-lg transition-all"
                    >
                        {pushingAll ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                        Push
                    </button>
                </div>
            </div>

            <div className="flex flex-1 overflow-hidden">

                {/* Left nav */}
                <div className="w-44 bg-[#111113] border-r border-zinc-800/60 flex flex-col shrink-0 py-3 px-2">
                    <p className="text-[9px] uppercase tracking-widest text-zinc-700 font-bold px-3 py-1 mb-1">Layers</p>
                    <NavItem tabId="plan" icon={Flag} label="Features" color="text-yellow-400" />
                    <NavItem tabId="database" icon={Database} label="Data" color="text-blue-400" />
                    <NavItem tabId="api" icon={Globe} label="API" color="text-purple-400" />
                    <NavItem tabId="ui" icon={LayoutPanelTop} label="UI" color="text-pink-400" />
                    <div className="my-2 border-t border-zinc-800/60" />
                    <NavItem tabId="overview" icon={Activity} label="Overview" color="text-emerald-400" />

                    <div className="mt-auto pt-4 border-t border-zinc-800/60 px-2">
                        <div className="flex items-center gap-1.5 text-zinc-700 text-[10px]">
                            <GitBranch size={11} />
                            <span className="truncate">{project?.repo_url?.split('/').pop()}</span>
                        </div>
                    </div>
                </div>

                {/* ── PLAN TAB ── */}
                {activeTab === 'plan' && (
                    <div className="flex flex-1 overflow-hidden">

                        {/* Feature list */}
                        <div className="w-56 border-r border-zinc-800/60 flex flex-col shrink-0 bg-[#0f0f11]">
                            <div className="px-3 pt-3 pb-2 border-b border-zinc-800/60">
                                <div className="flex items-center gap-2 bg-[#111113] border border-zinc-800 rounded px-2 py-1.5">
                                    <Plus size={10} className="text-zinc-700 shrink-0" />
                                    <input
                                        value={newFeature}
                                        onChange={e => setNewFeature(e.target.value)}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter' && newFeature.trim()) {
                                                addItem('features', { name: newFeature.trim(), status: 'planned' });
                                                setNewFeature('');
                                            }
                                        }}
                                        placeholder="New feature..."
                                        className="flex-1 bg-transparent text-[11px] text-zinc-300 placeholder:text-zinc-700 outline-none"
                                    />
                                </div>
                            </div>

                            <div className="flex-1 overflow-y-auto py-1">
                                {features.map((f, i) => {
                                    const fImpl = implementations[f.id];
                                    const isSelected = selectedFeature?.id === f.id;
                                    return (
                                        <button
                                            key={f.id}
                                            onClick={() => selectFeature(f)}
                                            className={`w-full flex items-center gap-2 px-3 py-2 text-left transition-all group ${isSelected ? 'bg-blue-600/15 text-white' : 'text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/30'}`}
                                        >
                                            <span className="text-[9px] text-zinc-700 w-4 shrink-0">{i + 1}</span>
                                            <span className="flex-1 text-[11px] truncate">{f.name}</span>
                                            {fImpl?.done && (
                                                <div className="shrink-0">
                                                    {fImpl.files.every(fi => fi.committed)
                                                        ? <Check size={10} className="text-green-500" />
                                                        : <span className="w-1.5 h-1.5 rounded-full bg-yellow-400 block" />
                                                    }
                                                </div>
                                            )}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Feature detail / implementation panel */}
                        <div className="flex-1 flex overflow-hidden">
                            {!selectedFeature ? (
                                <div className="flex-1 flex items-center justify-center text-center p-12">
                                    <div>
                                        <Flag size={28} className="text-zinc-800 mx-auto mb-3" />
                                        <p className="text-sm text-zinc-600">Select a feature to see its implementation plan</p>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex-1 flex flex-col overflow-hidden">
                                    {/* Feature header */}
                                    <div className="px-6 py-4 border-b border-zinc-800/60 bg-[#0f0f11] shrink-0">
                                        <div className="flex items-start justify-between">
                                            <div>
                                                <h2 className="text-base font-bold text-white">{selectedFeature.name}</h2>
                                                <p className="text-xs text-zinc-600 mt-0.5">
                                                    {filePlan.length} file{filePlan.length !== 1 ? 's' : ''} to generate
                                                </p>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                {impl?.done && !impl.files.every(f => f.committed) && (
                                                    <>
                                                        <button
                                                            onClick={() => {
                                                                setSelectedFeature(null);
                                                                showToast('Saved as draft');
                                                            }}
                                                            className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 text-xs font-bold rounded-lg transition-all"
                                                        >
                                                            Keep as Draft
                                                        </button>
                                                        <button
                                                            onClick={() => pushFeature(selectedFeature)}
                                                            disabled={pushingAll}
                                                            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-all shadow-lg shadow-blue-500/20"
                                                        >
                                                            {pushingAll ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
                                                            Commit & Push
                                                        </button>
                                                    </>
                                                )}
                                                {!impl?.done && !impl?.implementing && (
                                                    <button
                                                        onClick={() => implementFeature(selectedFeature)}
                                                        className="flex items-center gap-1.5 px-4 py-2 bg-orange-500 hover:bg-orange-400 text-white text-xs font-bold rounded-lg transition-all shadow-lg shadow-orange-500/20"
                                                    >
                                                        <Zap size={11} />
                                                        Implement Plan
                                                    </button>
                                                )}
                                                {impl?.implementing && (
                                                    <div className="flex items-center gap-2 text-xs text-zinc-500 bg-zinc-800/40 px-3 py-2 rounded-lg">
                                                        <Loader2 size={12} className="animate-spin text-orange-500" />
                                                        Generating files...
                                                    </div>
                                                )}
                                                {impl?.done && (
                                                    <button
                                                        onClick={() => {
                                                            if (confirm('Discard these generated files?')) {
                                                                setImplementations(prev => {
                                                                    const next = { ...prev };
                                                                    delete next[selectedFeature.id];
                                                                    return next;
                                                                });
                                                                setOpenFile(null);
                                                            }
                                                        }}
                                                        className="p-2 text-zinc-700 hover:text-red-500 transition-colors"
                                                        title="Discard implementation"
                                                    >
                                                        <Trash2 size={14} />
                                                    </button>
                                                )}
                                            </div>
                                        </div>
                                    </div>

                                    {/* File plan list */}
                                    <div className="flex-1 overflow-hidden flex">
                                        <div className="w-72 border-r border-zinc-800/60 overflow-y-auto shrink-0">
                                            {/* Plan (before implementing) */}
                                            {!impl?.done && (
                                                <div className="p-4 space-y-1">
                                                    <p className="text-[9px] font-bold uppercase tracking-widest text-zinc-600 px-1 mb-3">Files to generate</p>
                                                    {filePlan.map((p, i) => (
                                                        <div key={i} className="flex items-center gap-2.5 px-3 py-2 bg-[#111113] border border-zinc-800/60 rounded-lg">
                                                            <File size={11} className={
                                                                p.type === 'schemas' ? 'text-blue-400/60 shrink-0' :
                                                                    p.type === 'endpoints' ? 'text-purple-400/60 shrink-0' :
                                                                        'text-pink-400/60 shrink-0'
                                                            } />
                                                            <div className="flex-1 min-w-0">
                                                                <p className="text-[11px] text-zinc-300 truncate">{p.fileName}</p>
                                                                <p className="text-[9px] text-zinc-700 truncate">{p.filePath}</p>
                                                            </div>
                                                            <span className={`text-[9px] font-bold uppercase shrink-0 ${p.type === 'schemas' ? 'text-blue-600' : p.type === 'endpoints' ? 'text-purple-600' : 'text-pink-600'}`}>
                                                                {p.type === 'schemas' ? 'db' : p.type === 'endpoints' ? 'api' : 'ui'}
                                                            </span>
                                                        </div>
                                                    ))}
                                                    {filePlan.length === 0 && (
                                                        <p className="text-xs text-zinc-700 py-4 text-center">No spec items matched. Add schemas/endpoints/UI first.</p>
                                                    )}
                                                    {filePlan.length > 0 && (
                                                        <button
                                                            onClick={() => implementFeature(selectedFeature)}
                                                            className="w-full mt-4 flex items-center justify-center gap-2 py-3 bg-orange-500 hover:bg-orange-400 text-white text-xs font-bold rounded-lg transition-all"
                                                        >
                                                            <Play size={11} />
                                                            Implement Plan
                                                        </button>
                                                    )}
                                                </div>
                                            )}

                                            {/* Generated files (after implementing) */}
                                            {impl?.implementing && (
                                                <div className="p-4 flex flex-col h-full bg-[#0a0a0c]">
                                                    <div className="flex items-center gap-2 mb-4">
                                                        <Loader2 size={12} className="animate-spin text-orange-500" />
                                                        <span className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest">Live Implementation</span>
                                                    </div>
                                                    <div className="flex-1 font-mono text-[10px] space-y-1 overflow-y-auto text-zinc-400">
                                                        {genLogs.map((log, i) => (
                                                            <div key={i} className="animate-in fade-in slide-in-from-left-2 duration-200">
                                                                {log}
                                                            </div>
                                                        ))}
                                                        <div className="animate-pulse text-zinc-700">_</div>
                                                    </div>
                                                </div>
                                            )}

                                            {impl?.done && (
                                                <div className="p-4 space-y-1">
                                                    <p className="text-[9px] font-bold uppercase tracking-widest text-zinc-600 px-1 mb-3">Generated files — click to review</p>
                                                    {impl.files.map((f, i) => (
                                                        <button
                                                            key={i}
                                                            onClick={() => setOpenFile(f)}
                                                            className={`w-full flex items-center gap-2.5 px-3 py-2.5 rounded-lg border transition-all text-left ${openFile?.filePath === f.filePath
                                                                ? 'bg-blue-600/15 border-blue-500/30 text-white'
                                                                : 'bg-[#111113] border-zinc-800/60 text-zinc-400 hover:border-zinc-700 hover:text-zinc-300'
                                                                }`}
                                                        >
                                                            <File size={11} className={f.committed ? 'text-green-500 shrink-0' : 'text-yellow-400 shrink-0'} />
                                                            <div className="flex-1 min-w-0">
                                                                <p className="text-[11px] truncate">{f.fileName}</p>
                                                                <p className="text-[9px] text-zinc-700 truncate">{f.filePath}</p>
                                                            </div>
                                                            {f.committed
                                                                ? <Check size={10} className="text-green-500 shrink-0" />
                                                                : <span className="text-[9px] text-yellow-400 font-bold shrink-0">DRAFT</span>
                                                            }
                                                        </button>
                                                    ))}

                                                    {!impl.files.every(f => f.committed) && (
                                                        <button
                                                            onClick={() => pushFeature(selectedFeature)}
                                                            disabled={pushingAll}
                                                            className="w-full mt-4 flex items-center justify-center gap-2 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-all"
                                                        >
                                                            {pushingAll ? <Loader2 size={11} className="animate-spin" /> : <Send size={11} />}
                                                            Commit & Push to GitHub
                                                        </button>
                                                    )}
                                                    {impl.files.every(f => f.committed) && (
                                                        <div className="flex items-center justify-center gap-2 py-3 text-green-500 text-xs font-bold">
                                                            <Check size={12} /> Pushed to GitHub
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </div>

                                        {/* Code viewer (right side of detail panel) */}
                                        {openFile ? (
                                            <div className="flex-1 overflow-hidden">
                                                <CodeViewer
                                                    title={openFile.fileName}
                                                    code={openFile.code}
                                                    onChange={(code) => {
                                                        setOpenFile(f => f ? { ...f, code } : f);
                                                        setImplementations(prev => {
                                                            const impl = prev[selectedFeature.id];
                                                            if (!impl) return prev;
                                                            return {
                                                                ...prev,
                                                                [selectedFeature.id]: {
                                                                    ...impl,
                                                                    files: impl.files.map(fi =>
                                                                        fi.filePath === openFile.filePath ? { ...fi, code } : fi
                                                                    )
                                                                }
                                                            };
                                                        });
                                                    }}
                                                    onClose={() => setOpenFile(null)}
                                                />
                                            </div>
                                        ) : (
                                            <div className="flex-1 flex items-center justify-center text-center p-8">
                                                <div>
                                                    <Code2 size={24} className="text-zinc-800 mx-auto mb-3" />
                                                    <p className="text-xs text-zinc-700">
                                                        {impl?.done ? 'Click a file to review its code' : 'Implement the plan to generate code'}
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* File tree (right side) */}
                        {treeVisible && (
                            <div className="w-52 bg-[#111113] border-l border-zinc-800/60 flex flex-col shrink-0">
                                <div className="h-9 border-b border-zinc-800/60 flex items-center justify-between px-3 shrink-0">
                                    <span className="text-[9px] font-bold uppercase tracking-widest text-zinc-600">Files</span>
                                    <button onClick={() => setTreeVisible(false)} className="text-zinc-700 hover:text-zinc-400"><X size={11} /></button>
                                </div>
                                <div className="flex-1 overflow-y-auto py-2">
                                    {buildTree().map(n => (
                                        <TreeItem key={n.path} node={n} onSelect={handleTreeSelect} selectedPath={selectedTreePath} />
                                    ))}
                                </div>
                            </div>
                        )}
                        {!treeVisible && (
                            <button onClick={() => setTreeVisible(true)} className="w-8 bg-[#111113] border-l border-zinc-800/60 flex items-center justify-center text-zinc-700 hover:text-zinc-400 transition-colors shrink-0">
                                <ChevronRight size={12} className="rotate-180" />
                            </button>
                        )}
                    </div>
                )}

                {/* ── DATA TAB (plain spec editor) ── */}
                {activeTab === 'database' && (
                    <div className="flex-1 overflow-auto p-6 space-y-4">
                        <div className="flex items-center gap-2 mb-4">
                            <Database size={14} className="text-blue-400" />
                            <h2 className="text-sm font-bold text-zinc-300">Data Layer</h2>
                            <span className="text-zinc-700 text-xs">({schemas.length})</span>
                        </div>
                        <div className="flex items-center gap-2 bg-[#111113] border border-zinc-800 rounded-lg px-3 py-2">
                            <Plus size={11} className="text-zinc-700" />
                            <input value={newTable} onChange={e => setNewTable(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter' && newTable.trim()) { addItem('schemas', { table_name: newTable.trim(), fields: [] }); setNewTable(''); } }}
                                placeholder="Table name... (Enter)" className="flex-1 bg-transparent text-xs text-zinc-300 placeholder:text-zinc-700 outline-none" />
                        </div>
                        <div className="space-y-1">
                            {schemas.map(s => (
                                <div key={s.id} className="group flex items-center gap-3 px-3 py-2.5 bg-[#111113] border border-zinc-800/60 rounded-lg hover:border-zinc-700 transition-all">
                                    <span className="text-blue-700 text-[10px] font-bold w-12 text-right shrink-0">model</span>
                                    <span className="flex-1 text-xs text-blue-300">{s.table_name}</span>
                                    <span className="text-zinc-700 text-[9px]">{s.fields?.length || 0} fields</span>
                                    <button onClick={() => deleteItem('schemas', s.id)} className="opacity-0 group-hover:opacity-100 text-zinc-700 hover:text-red-500 transition-all"><Trash2 size={12} /></button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ── API TAB ── */}
                {activeTab === 'api' && (
                    <div className="flex-1 overflow-auto p-6 space-y-4">
                        <div className="flex items-center gap-2 mb-4">
                            <Globe size={14} className="text-purple-400" />
                            <h2 className="text-sm font-bold text-zinc-300">API Endpoints</h2>
                            <span className="text-zinc-700 text-xs">({endpoints.length})</span>
                        </div>
                        <div className="flex items-center gap-2 bg-[#111113] border border-zinc-800 rounded-lg px-3 py-2">
                            <select value={newRouteMethod} onChange={e => setNewRouteMethod(e.target.value)} className={`bg-transparent text-[10px] font-bold uppercase outline-none cursor-pointer w-14 shrink-0 ${METHOD_COLOR[newRouteMethod]}`}>
                                {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => <option key={m} value={m}>{m}</option>)}
                            </select>
                            <input value={newRoute} onChange={e => setNewRoute(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter' && newRoute.trim()) { addItem('endpoints', { method: newRouteMethod, route: newRoute.trim(), request_schema: {}, response_schema: {} }); setNewRoute(''); } }}
                                placeholder="/route (Enter)" className="flex-1 bg-transparent text-xs text-zinc-300 placeholder:text-zinc-700 outline-none" />
                        </div>
                        <div className="space-y-1">
                            {endpoints.map(ep => (
                                <div key={ep.id} className="group flex items-center gap-3 px-3 py-2.5 bg-[#111113] border border-zinc-800/60 rounded-lg hover:border-zinc-700 transition-all">
                                    <span className={`text-[10px] font-bold w-14 text-right shrink-0 ${METHOD_COLOR[ep.method] || 'text-zinc-500'}`}>{ep.method}</span>
                                    <span className="flex-1 text-xs text-zinc-300 font-mono">{ep.route}</span>
                                    <button onClick={() => deleteItem('endpoints', ep.id)} className="opacity-0 group-hover:opacity-100 text-zinc-700 hover:text-red-500 transition-all"><Trash2 size={12} /></button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ── UI TAB ── */}
                {activeTab === 'ui' && (
                    <div className="flex-1 overflow-auto p-6 space-y-4">
                        <div className="flex items-center gap-2 mb-4">
                            <LayoutPanelTop size={14} className="text-pink-400" />
                            <h2 className="text-sm font-bold text-zinc-300">UI Components</h2>
                            <span className="text-zinc-700 text-xs">({uiComponents.length})</span>
                        </div>
                        <div className="flex items-center gap-2 bg-[#111113] border border-zinc-800 rounded-lg px-3 py-2">
                            <Plus size={11} className="text-zinc-700" />
                            <input value={newUI} onChange={e => setNewUI(e.target.value)}
                                onKeyDown={e => { if (e.key === 'Enter' && newUI.trim()) { addItem('ui-components', { name: newUI.trim(), type: 'page' }); setNewUI(''); } }}
                                placeholder="Component name... (Enter)" className="flex-1 bg-transparent text-xs text-zinc-300 placeholder:text-zinc-700 outline-none" />
                        </div>
                        <div className="space-y-1">
                            {uiComponents.map(c => (
                                <div key={c.id} className="group flex items-center gap-3 px-3 py-2.5 bg-[#111113] border border-zinc-800/60 rounded-lg hover:border-zinc-700 transition-all">
                                    <span className="text-pink-700 text-[10px] font-bold w-14 text-right shrink-0 capitalize">{c.type}</span>
                                    <span className="flex-1 text-xs text-pink-200">{c.name}</span>
                                    <button onClick={() => deleteItem('ui-components', c.id)} className="opacity-0 group-hover:opacity-100 text-zinc-700 hover:text-red-500 transition-all"><Trash2 size={12} /></button>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ── OVERVIEW TAB ── */}
                {activeTab === 'overview' && (
                    <div className="flex-1 overflow-auto p-6 space-y-4">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity size={14} className="text-emerald-400" />
                            <h2 className="text-sm font-bold text-zinc-300">Overview</h2>
                        </div>
                        <div className="grid grid-cols-3 gap-3">
                            {[
                                { label: 'Features', value: features.length, color: 'text-yellow-400' },
                                { label: 'Tables', value: schemas.length, color: 'text-blue-400' },
                                { label: 'Endpoints', value: endpoints.length, color: 'text-purple-400' },
                                { label: 'UI Components', value: uiComponents.length, color: 'text-pink-400' },
                                { label: 'Implemented', value: Object.values(implementations).filter(i => i.done).length, color: 'text-green-400' },
                            ].map(({ label, value, color }) => (
                                <div key={label} className="bg-[#111113] border border-zinc-800/60 rounded-xl p-4">
                                    <p className="text-[9px] text-zinc-700 uppercase tracking-widest mb-1">{label}</p>
                                    <p className={`text-xl font-bold ${color}`}>{value}</p>
                                </div>
                            ))}
                        </div>
                        <div className="bg-[#111113] border border-zinc-800/60 rounded-xl p-5 font-mono text-xs leading-6">
                            <div className="text-zinc-600">{`# ${project?.name}`}</div>
                            <div className="text-zinc-700">{`repo: ${project?.repo_url}`}</div>
                            <div className="mt-2 text-blue-400">{`features:  ${features.map((f: any) => f.name).join(', ') || '—'}`}</div>
                            <div className="text-emerald-400">{`tables:    ${schemas.map((s: any) => s.table_name).join(', ') || '—'}`}</div>
                        </div>
                    </div>
                )}
            </div>

            {/* Drafts tray */}
            {showDraftsTray && (
                <div className="fixed bottom-14 right-4 w-80 bg-[#111113] border border-zinc-800 rounded-xl shadow-2xl z-50 overflow-hidden">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800/60">
                        <div className="flex items-center gap-2">
                            <Inbox size={13} className="text-yellow-400" />
                            <span className="text-xs font-bold text-zinc-300">{allDraftFiles.length} draft{allDraftFiles.length !== 1 ? 's' : ''}</span>
                        </div>
                        <button onClick={() => setShowDraftsTray(false)} className="text-zinc-600 hover:text-zinc-300"><X size={13} /></button>
                    </div>
                    <div className="max-h-64 overflow-y-auto divide-y divide-zinc-800/40">
                        {allDraftFiles.length === 0 ? (
                            <p className="text-xs text-zinc-700 px-4 py-6 text-center">No drafts. Implement a feature to generate code.</p>
                        ) : allDraftFiles.map((f, i) => (
                            <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                                <File size={11} className="text-yellow-400 shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-[11px] text-zinc-300 truncate">{f.fileName}</p>
                                    <p className="text-[9px] text-zinc-600 truncate">{f.filePath}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                    {allDraftFiles.length > 0 && (
                        <div className="px-4 py-3 border-t border-zinc-800/60">
                            <button
                                onClick={() => { if (selectedFeature) pushFeature(selectedFeature); }}
                                disabled={pushingAll || !selectedFeature}
                                className="w-full flex items-center justify-center gap-2 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-bold rounded-lg transition-all"
                            >
                                {pushingAll ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                                Push All to GitHub
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Toast */}
            {toast && (
                <div className={`fixed bottom-4 left-1/2 -translate-x-1/2 px-4 py-2 rounded-lg text-xs font-bold shadow-lg z-[100] flex items-center gap-2 ${toast.ok ? 'bg-green-600 text-white' : 'bg-red-600 text-white'}`}>
                    {toast.ok ? <Check size={12} /> : <AlertCircle size={12} />}
                    {toast.msg}
                </div>
            )}
        </div>
    );
}
