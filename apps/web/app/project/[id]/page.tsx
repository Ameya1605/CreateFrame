'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import api from '@/lib/api';
import { fetchRecommendations, applyRecommendation, dismissRecommendation } from '@/lib/api';
import {
    ArrowLeft, Database, Globe, Loader2, Code2,
    X, LayoutPanelTop, Flag, Activity, Sparkles,
    ChevronRight, ChevronDown, File, Folder, FolderOpen,
    Send, Trash2, Plus, Check, AlertCircle, Inbox,
    Zap, Play, GitBranch, Lightbulb, Eye, EyeOff,
    Brain, ShieldAlert, TrendingUp, Info, Copy, CheckCheck, RefreshCw,
    MessageSquare, Award, BookOpen, Terminal, FileText
} from 'lucide-react';
import DriftPanel from './components/DriftPanel';
import ERDView from './components/ERDView';
import ArchitectureChat from './components/ArchitectureChat';
import DesignCritique from './components/DesignCritique';
import BuildPromptModal from './components/BuildPromptModal';
import DocToSpecModal from './components/DocToSpecModal';
import ADRView from './components/ADRView';

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
        const isTpl = relatedUI.type === 'template';
        const isVue = relatedUI.name.toLowerCase().endsWith('.vue') || relatedUI.type === 'vue';
        const isSvelte = relatedUI.name.toLowerCase().endsWith('.svelte') || relatedUI.type === 'svelte';
        const ext = isTpl ? 'html' : isVue ? 'vue' : isSvelte ? 'svelte' : 'tsx';
        const fileName = isTpl ? `${slug(relatedUI.name)}.${ext}` : `${pascal(relatedUI.name)}.${ext}`;
        const filePath = isTpl ? `templates/${fileName}` : isVue ? `src/views/${fileName}` : `apps/web/app/${fileName}`;
        plan.push({
            type: 'ui-components',
            item: relatedUI,
            fileName,
            filePath
        });
    }

    // If nothing matched, create sensible defaults
    if (plan.length === 0) {
        const firstEndpoint = endpoints[0];
        const firstUI = uiComponents.find(c => c.type === 'page' || c.type === 'template') || uiComponents[0];
        if (firstUI) {
            const isTpl = firstUI.type === 'template';
            const ext = isTpl ? 'html' : 'tsx';
            plan.push({
                type: 'ui-components',
                item: { ...firstUI, name: featureName },
                fileName: isTpl ? `${slug(featureName)}.html` : `${pascal(featureName)}.tsx`,
                filePath: isTpl ? `templates/${slug(featureName)}.html` : `apps/web/app/${pascal(featureName)}.tsx`
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

// ─── File Tree Component ──────────────────────────────────────────────────────

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
                    className="w-full flex items-center gap-1.5 px-2 py-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)] transition-colors text-left font-mono"
                    style={{ paddingLeft: `${8 + depth * 14}px` }}
                >
                    {open ? <ChevronDown size={11} className="text-zinc-500" /> : <ChevronRight size={11} className="text-zinc-500" />}
                    {open ? <FolderOpen size={12} className="text-blue-400 shrink-0" /> : <Folder size={12} className="text-zinc-500 shrink-0" />}
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
            className={`w-full flex items-center gap-1.5 py-1 rounded text-left transition-colors font-mono ${
                isSelected
                    ? 'bg-blue-600/20 text-blue-300 font-semibold border-l-2 border-blue-500'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)]'
            }`}
            style={{ paddingLeft: `${8 + depth * 14}px` }}
        >
            <File size={11} className={node.hasCode ? 'text-amber-400 shrink-0' : 'text-zinc-600 shrink-0'} />
            <span className="text-[11px] truncate flex-1">{node.name}</span>
            {node.hasCode && <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5 shrink-0" />}
        </button>
    );
}

// ─── Code Viewer Component ────────────────────────────────────────────────────

function CodeViewer({ title, code, onChange, onClose }: {
    title: string; code: string;
    onChange: (v: string) => void; onClose: () => void;
}) {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(code);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="flex flex-col h-full bg-[var(--surface-0)] border-l border-[var(--border-subtle)]">
            {/* Header */}
            <div className="h-10 flex items-center justify-between px-3 border-b border-[var(--border-subtle)] bg-[var(--surface-1)] shrink-0">
                <div className="flex items-center gap-2">
                    <Code2 size={13} className="text-blue-400" />
                    <span className="text-xs font-mono font-medium text-zinc-200">{title}</span>
                </div>
                <div className="flex items-center gap-1">
                    <button
                        onClick={handleCopy}
                        className="flex items-center gap-1 px-2 py-1 rounded text-[11px] text-zinc-400 hover:text-white hover:bg-[var(--surface-2)] transition-all"
                        title="Copy code"
                    >
                        {copied ? <CheckCheck size={12} className="text-emerald-400" /> : <Copy size={12} />}
                        <span className="hidden sm:inline">{copied ? 'Copied' : 'Copy'}</span>
                    </button>
                    <button
                        onClick={onClose}
                        className="p-1 rounded text-zinc-500 hover:text-zinc-200 hover:bg-[var(--surface-2)] transition-all"
                    >
                        <X size={14} />
                    </button>
                </div>
            </div>

            {/* Code Body with Line Numbers */}
            <div className="flex flex-1 overflow-hidden font-mono text-[11px] leading-relaxed">
                <div className="w-10 bg-[var(--surface-1)] border-r border-[var(--border-subtle)] flex flex-col items-end pt-3 pr-2 select-none overflow-hidden shrink-0 text-zinc-600">
                    {(code || '').split('\n').map((_, i) => (
                        <div key={i} className="text-[10px] leading-5">{i + 1}</div>
                    ))}
                </div>
                <textarea
                    className="flex-1 bg-transparent p-3 text-blue-100/90 resize-none outline-none leading-5 selection:bg-blue-600/30 font-mono"
                    value={code}
                    onChange={e => onChange(e.target.value)}
                    spellCheck={false}
                    placeholder="// Generated source code will appear here"
                />
            </div>
        </div>
    );
}

// ─── Main Project Detail ──────────────────────────────────────────────────────

const METHOD_COLORS: Record<string, { bg: string; text: string; border: string }> = {
    GET: { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20' },
    POST: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20' },
    PUT: { bg: 'bg-amber-500/10', text: 'text-amber-400', border: 'border-amber-500/20' },
    PATCH: { bg: 'bg-orange-500/10', text: 'text-orange-400', border: 'border-orange-500/20' },
    DELETE: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/20' }
};

export default function ProjectDetail() {
    const { id } = useParams();
    const router = useRouter();

    const [project, setProject] = useState<any>(null);
    const [activeTab, setActiveTab] = useState<'plan' | 'database' | 'api' | 'ui' | 'erd' | 'drift' | 'chat' | 'critique' | 'adrs' | 'overview' | 'insights'>('plan');
    const [loading, setLoading] = useState(true);
    const [mounted, setMounted] = useState(false);
    const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
    const [showBuildPrompt, setShowBuildPrompt] = useState(false);
    const [showDocToSpec, setShowDocToSpec] = useState(false);

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

    // Drafts tray & modal
    const [showDraftsTray, setShowDraftsTray] = useState(false);
    const [pushingAll, setPushingAll] = useState(false);
    const [discardModalOpen, setDiscardModalOpen] = useState(false);

    // File tree
    const [treeVisible, setTreeVisible] = useState(true);
    const [selectedTreePath, setSelectedTreePath] = useState('');

    // Spec forms
    const [newFeature, setNewFeature] = useState('');
    const [newTable, setNewTable] = useState('');
    const [newRoute, setNewRoute] = useState('');
    const [newRouteMethod, setNewRouteMethod] = useState('GET');
    const [newUI, setNewUI] = useState('');
    const [newUIType, setNewUIType] = useState<'page' | 'template' | 'component' | 'layout'>('template');
    const [newUIRoute, setNewUIRoute] = useState('');
    const [selectedViewCode, setSelectedViewCode] = useState<{ name: string; code?: string; type: string; route?: string } | null>(null);

    const [genLogs, setGenLogs] = useState<string[]>([]);

    // Recommendations
    const [recommendations, setRecommendations] = useState<any>(null);
    const [recsLoading, setRecsLoading] = useState(false);
    const [applyingRecId, setApplyingRecId] = useState<string | null>(null);

    const [rescanning, setRescanning] = useState(false);

    const showToast = useCallback((msg: string, ok = true) => {
        setToast({ msg, ok });
        setTimeout(() => setToast(null), 3500);
    }, []);

    useEffect(() => {
        setMounted(true);
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

            if (featRes.data.length > 0 && !selectedFeature) {
                selectFeature(featRes.data[0]);
            }
        } catch {
            showToast('Failed to load project details', false);
        } finally {
            setLoading(false);
        }
    };

    const handleRescan = async () => {
        setRescanning(true);
        try {
            const res = await api.post('/import-from-repo', { project_id: Number(id) });
            showToast(res.data?.message || 'Repository scanned successfully!');
            await fetchProjectData();
        } catch (err: any) {
            showToast(err.response?.data?.detail || 'Scan failed. Check GitHub repository permissions.', false);
        } finally {
            setRescanning(false);
        }
    };

    // Recommendations
    const loadRecommendations = async () => {
        if (!id) return;
        setRecsLoading(true);
        try {
            const data = await fetchRecommendations(Number(id));
            setRecommendations(data);
        } catch {
            // non-critical
        } finally {
            setRecsLoading(false);
        }
    };

    useEffect(() => {
        if (!loading && project) loadRecommendations();
    }, [loading, project?.id]);

    const handleApplyRec = async (recId: string) => {
        setApplyingRecId(recId);
        try {
            await applyRecommendation(Number(id), recId);
            showToast('Recommendation applied successfully!');
            await fetchProjectData();
        } catch {
            showToast('Failed to apply recommendation', false);
        } finally {
            setApplyingRecId(null);
        }
    };

    const handleDismissRec = async (recId: string) => {
        try {
            await dismissRecommendation(Number(id), recId);
            await loadRecommendations();
            showToast('Recommendation dismissed');
        } catch {
            showToast('Failed to dismiss', false);
        }
    };

    const selectFeature = (f: any) => {
        setSelectedFeature(f);
        setOpenFile(null);
        const plan = deriveFilePlan(f, schemas, endpoints, uiComponents);
        setFilePlan(plan);
    };

    // Implement feature: generate code for plan
    const implementFeature = async (feature: any) => {
        const fid = feature.id;
        setImplementations(prev => ({
            ...prev,
            [fid]: { featureId: fid, files: [], implementing: true, done: false }
        }));
        setGenLogs([`> Initializing code generator for "${feature.name}"...`]);

        const plan = deriveFilePlan(feature, schemas, endpoints, uiComponents);
        const generated: GeneratedFile[] = [];

        for (const p of plan) {
            setGenLogs(prev => [...prev.slice(-10), `> Synthesizing ${p.fileName}...`]);
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
                setGenLogs(prev => [...prev.slice(-10), `  ✓ Generated ${p.fileName}`]);
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
        setGenLogs(prev => [...prev.slice(-10), `> Completed generating all files.`]);

        if (generated.length > 0) setOpenFile(generated[0]);
        showToast(`Generated ${generated.length} file${generated.length !== 1 ? 's' : ''} for "${feature.name}"`);
    };

    // Push feature files to GitHub
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
            showToast(`"${feature.name}" committed and pushed to GitHub!`);
        } catch {
            showToast('Push failed. Please check repository permissions.', false);
        } finally {
            setPushingAll(false);
        }
    };

    const confirmDiscard = () => {
        if (!selectedFeature) return;
        setImplementations(prev => {
            const next = { ...prev };
            delete next[selectedFeature.id];
            return next;
        });
        setOpenFile(null);
        setDiscardModalOpen(false);
        showToast('Generated drafts discarded');
    };

    // Count all drafts
    const allDraftFiles = Object.values(implementations)
        .flatMap(impl => impl.files.filter(f => !f.committed));

    const addItem = async (type: string, payload: any) => {
        try {
            const res = await api.post(`/${type}?project_id=${id}`, payload);
            if (type === 'features') setFeatures(f => [...f, res.data]);
            if (type === 'schemas') setSchemas(s => [...s, res.data]);
            if (type === 'endpoints') setEndpoints(e => [...e, res.data]);
            if (type === 'ui-components') setUiComponents(u => [...u, res.data]);
            showToast('Item added to spec');
        } catch { showToast('Failed to add item', false); }
    };

    const deleteItem = async (type: string, itemId: number) => {
        try {
            await api.delete(`/${type}/${itemId}`);
            if (type === 'features') {
                setFeatures(f => f.filter(i => i.id !== itemId));
                if (selectedFeature?.id === itemId) setSelectedFeature(null);
            }
            if (type === 'schemas') setSchemas(s => s.filter(i => i.id !== itemId));
            if (type === 'endpoints') setEndpoints(e => e.filter(i => i.id !== itemId));
            if (type === 'ui-components') setUiComponents(u => u.filter(i => i.id !== itemId));
            showToast('Item deleted');
        } catch { showToast('Delete failed', false); }
    };

    // Build file tree
    const buildTree = (): TreeNode[] => {
        const repoName = project?.repo_url?.split('/').pop() || project?.name || 'repository';
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

    const NavItem = ({ tabId, icon: Icon, label, color }: any) => {
        const isActive = activeTab === tabId;
        return (
            <button
                onClick={() => setActiveTab(tabId)}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-xl text-left transition-all ${
                    isActive
                        ? 'bg-[var(--surface-2)] text-white shadow-sm font-semibold'
                        : 'text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)]/60'
                }`}
            >
                <div className="flex items-center gap-2.5">
                    <Icon size={14} className={isActive ? color : 'text-zinc-500'} />
                    <span className="text-xs">{label}</span>
                </div>
                {tabId === 'insights' && recommendations && recommendations.critical_count > 0 && (
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                )}
            </button>
        );
    };

    if (!mounted || loading) {
        return (
            <div className="h-screen bg-[var(--surface-0)] flex flex-col items-center justify-center gap-3">
                <Loader2 className="animate-spin text-blue-500" size={28} />
                <p className="text-xs text-zinc-400">Loading project architecture...</p>
            </div>
        );
    }

    const impl = selectedFeature ? implementations[selectedFeature.id] : null;

    return (
        <div className="h-screen bg-[var(--surface-0)] text-zinc-100 flex flex-col overflow-hidden antialiased">

            {/* Top Navigation Bar */}
            <div className="h-14 bg-[var(--surface-1)] border-b border-[var(--border-subtle)] flex items-center justify-between px-5 shrink-0 z-30">
                <div className="flex items-center gap-3">
                    <button
                        onClick={() => router.push('/dashboard')}
                        className="flex items-center gap-1.5 text-zinc-400 hover:text-white text-xs font-medium px-2 py-1 rounded-lg hover:bg-[var(--surface-2)] transition-all"
                    >
                        <ArrowLeft size={14} /> Dashboard
                    </button>
                    <span className="text-zinc-700">/</span>
                    <span className="text-xs font-semibold text-zinc-200">{project?.name}</span>

                    {selectedFeature && activeTab === 'plan' && (
                        <>
                            <span className="text-zinc-700">/</span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20 font-medium">
                                {selectedFeature.name}
                            </span>
                        </>
                    )}
                </div>

                <div className="flex items-center gap-2.5">
                    <button
                        onClick={() => setShowDocToSpec(true)}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border border-purple-500/30 bg-purple-500/10 text-purple-300 hover:bg-purple-500/20"
                        title="Convert PRD doc or wireframe into spec"
                    >
                        <Sparkles size={13} className="text-purple-400" />
                        <span>PRD to Spec</span>
                    </button>

                    <button
                        onClick={handleRescan}
                        disabled={rescanning}
                        title="Rescan repository with AST parser"
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border border-[var(--border-subtle)] text-zinc-300 hover:text-white hover:bg-[var(--surface-2)] disabled:opacity-50"
                    >
                        <RefreshCw size={13} className={rescanning ? "animate-spin text-blue-400" : "text-blue-400"} />
                        <span>{rescanning ? 'Scanning...' : 'Rescan Repo'}</span>
                    </button>

                    <button
                        onClick={() => setShowDraftsTray(v => !v)}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold transition-all border ${
                            allDraftFiles.length > 0
                                ? 'border-amber-500/30 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20'
                                : 'border-[var(--border-subtle)] text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)]'
                        }`}
                    >
                        <Inbox size={13} />
                        <span>{allDraftFiles.length} draft{allDraftFiles.length !== 1 ? 's' : ''}</span>
                    </button>

                    <button
                        onClick={() => selectedFeature && pushFeature(selectedFeature)}
                        disabled={!selectedFeature || !impl?.done || pushingAll}
                        className="flex items-center gap-2 px-4 py-1.5 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 disabled:opacity-30 disabled:cursor-not-allowed text-white text-xs font-semibold rounded-xl shadow-md shadow-blue-600/20 transition-all hover:scale-[1.01]"
                    >
                        {pushingAll ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                        <span>Commit & Push</span>
                    </button>
                </div>
            </div>

            {/* Main Application Body */}
            <div className="flex flex-1 overflow-hidden">

                {/* Left Sidebar - Navigation */}
                <div className="w-52 bg-[var(--surface-1)] border-r border-[var(--border-subtle)] flex flex-col shrink-0 py-4 px-3">
                    <p className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold px-3 mb-2">Architecture</p>
                    <div className="space-y-1">
                        <NavItem tabId="plan" icon={Flag} label="Features & Plan" color="text-amber-400" />
                        <NavItem tabId="database" icon={Database} label="Data Models" color="text-blue-400" />
                        <NavItem tabId="api" icon={Globe} label="API Routes" color="text-purple-400" />
                        <NavItem tabId="ui" icon={LayoutPanelTop} label="UI Views" color="text-pink-400" />
                        <NavItem tabId="erd" icon={Database} label="ERD & Exports" color="text-cyan-400" />
                    </div>

                    <div className="my-3 border-t border-[var(--border-subtle)]" />

                    <p className="text-[10px] uppercase tracking-wider text-zinc-500 font-bold px-3 mb-2">Smarter AI</p>
                    <div className="space-y-1">
                        <NavItem tabId="chat" icon={MessageSquare} label="Chat & Impact" color="text-blue-400" />
                        <NavItem tabId="critique" icon={Award} label="Design Critique" color="text-amber-400" />
                        <NavItem tabId="drift" icon={ShieldAlert} label="Drift & Sync" color="text-orange-400" />
                        <NavItem tabId="adrs" icon={BookOpen} label="Decision Records" color="text-emerald-400" />
                        <NavItem tabId="insights" icon={Brain} label="AI Insights" color="text-purple-400" />
                        <NavItem tabId="overview" icon={Activity} label="Spec Overview" color="text-zinc-400" />
                    </div>

                    {recommendations && recommendations.total_count > 0 && (
                        <div className="px-3 mt-3">
                            <div className="p-2.5 rounded-xl bg-[var(--surface-2)] border border-[var(--border-subtle)]">
                                <div className="flex items-center justify-between text-[11px] mb-1">
                                    <span className="text-zinc-400">Recommendations</span>
                                    <span className="font-bold text-zinc-200">{recommendations.total_count}</span>
                                </div>
                                {recommendations.critical_count > 0 && (
                                    <span className="inline-block px-1.5 py-0.5 rounded text-[10px] font-bold bg-red-500/15 text-red-400">
                                        {recommendations.critical_count} critical issues
                                    </span>
                                )}
                            </div>
                        </div>
                    )}

                    <div className="mt-auto pt-3 border-t border-[var(--border-subtle)] px-2">
                        <a
                            href={project?.repo_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-2 text-zinc-500 hover:text-zinc-300 text-xs font-mono truncate transition-colors"
                        >
                            <GitBranch size={13} className="shrink-0" />
                            <span className="truncate">{project?.repo_url?.split('/').pop() || 'repo'}</span>
                        </a>
                    </div>
                </div>

                {/* ── PLAN TAB: Features, Generator & Code Viewer ── */}
                {activeTab === 'plan' && (
                    <div className="flex flex-1 overflow-hidden">

                        {/* Feature List Column */}
                        <div className="w-64 border-r border-[var(--border-subtle)] flex flex-col shrink-0 bg-[var(--surface-1)]">
                            <div className="p-3 border-b border-[var(--border-subtle)]">
                                <div className="flex items-center gap-2 bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded-xl px-2.5 py-1.5 focus-within:border-blue-500/50 transition-all">
                                    <Plus size={13} className="text-zinc-400 shrink-0" />
                                    <input
                                        value={newFeature}
                                        onChange={e => setNewFeature(e.target.value)}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter' && newFeature.trim()) {
                                                addItem('features', { name: newFeature.trim(), status: 'planned' });
                                                setNewFeature('');
                                            }
                                        }}
                                        placeholder="Add new feature..."
                                        className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 outline-none"
                                    />
                                </div>
                            </div>

                            <div className="flex-1 overflow-y-auto p-2 space-y-1">
                                {features.length === 0 ? (
                                    <div className="p-3 text-center rounded-xl bg-[var(--surface-2)]/40 border border-[var(--border-subtle)] mt-2">
                                        <p className="text-[11px] text-zinc-400 mb-2">No features defined yet.</p>
                                        <button
                                            onClick={handleRescan}
                                            disabled={rescanning}
                                            className="w-full flex items-center justify-center gap-1.5 py-1.5 px-2 bg-blue-600/20 border border-blue-500/30 hover:bg-blue-600/30 text-blue-400 rounded-lg text-[11px] font-semibold transition-all"
                                        >
                                            <Sparkles size={12} className={rescanning ? "animate-spin" : ""} />
                                            <span>{rescanning ? 'Discovering...' : 'Auto-Discover from Repo'}</span>
                                        </button>
                                    </div>
                                ) : (
                                    features.map((f, i) => {
                                    const fImpl = implementations[f.id];
                                    const isSelected = selectedFeature?.id === f.id;
                                    return (
                                        <button
                                            key={f.id}
                                            onClick={() => selectFeature(f)}
                                            className={`w-full flex items-center justify-between p-2.5 rounded-xl text-left transition-all ${
                                                isSelected
                                                    ? 'bg-blue-600/15 border border-blue-500/30 text-white'
                                                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-[var(--surface-2)] border border-transparent'
                                            }`}
                                        >
                                            <div className="flex items-center gap-2 min-w-0">
                                                <span className="text-[10px] text-zinc-500 font-mono w-4 shrink-0">{i + 1}.</span>
                                                <span className="text-xs font-medium truncate">{f.name}</span>
                                            </div>
                                            {fImpl?.done && (
                                                <div className="shrink-0 ml-1.5">
                                                    {fImpl.files.every(fi => fi.committed)
                                                        ? <Check size={13} className="text-emerald-400" />
                                                        : <span className="w-2 h-2 rounded-full bg-amber-400 block" title="Uncommitted draft" />
                                                    }
                                                </div>
                                            )}
                                        </button>
                                    );
                                }))}
                            </div>
                        </div>

                        {/* Feature Detail Canvas */}
                        <div className="flex-1 flex overflow-hidden">
                            {!selectedFeature ? (
                                <div className="flex-1 flex items-center justify-center text-center p-8 bg-[var(--surface-0)]">
                                    <div className="max-w-sm">
                                        <div className="w-12 h-12 rounded-2xl bg-zinc-800/60 border border-zinc-700/60 flex items-center justify-center mx-auto mb-4 text-zinc-400">
                                            <Flag size={20} />
                                        </div>
                                        <h3 className="text-sm font-semibold text-zinc-200 mb-1">Select a feature to begin</h3>
                                        <p className="text-xs text-zinc-500 leading-relaxed">
                                            Pick a feature from the left list to view its architecture plan, synthesize source code, or review existing files.
                                        </p>
                                    </div>
                                </div>
                            ) : (
                                <div className="flex-1 flex flex-col overflow-hidden bg-[var(--surface-0)]">
                                    {/* Feature Header */}
                                    <div className="px-6 py-4 border-b border-[var(--border-subtle)] bg-[var(--surface-1)] shrink-0 flex items-center justify-between">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <h2 className="text-base font-bold text-white">{selectedFeature.name}</h2>
                                                {impl?.done && (
                                                    <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold ${
                                                        impl.files.every(f => f.committed)
                                                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                                            : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                                    }`}>
                                                        {impl.files.every(f => f.committed) ? 'Pushed' : 'Drafts Ready'}
                                                    </span>
                                                )}
                                            </div>
                                            <p className="text-xs text-zinc-400 mt-0.5">
                                                {filePlan.length} file{filePlan.length !== 1 ? 's' : ''} planned across database, backend API, and web UI.
                                            </p>
                                        </div>

                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => setShowBuildPrompt(true)}
                                                className="flex items-center gap-1.5 px-3 py-1.5 bg-[var(--surface-2)] hover:bg-zinc-800 text-zinc-300 hover:text-white text-xs font-semibold rounded-xl border border-[var(--border-subtle)] transition-all shadow-sm"
                                                title="Generate ready-to-paste build prompt for Cursor or Claude Code"
                                            >
                                                <Sparkles size={13} className="text-purple-400" />
                                                <span>Build Prompt</span>
                                            </button>

                                            {impl?.done && !impl.files.every(f => f.committed) && (
                                                <>
                                                    <button
                                                        onClick={() => {
                                                            setSelectedFeature(null);
                                                            showToast('Saved as draft');
                                                        }}
                                                        className="px-3 py-1.5 bg-[var(--surface-2)] hover:bg-zinc-800 text-zinc-300 text-xs font-semibold rounded-xl border border-[var(--border-subtle)] transition-all"
                                                    >
                                                        Keep as Draft
                                                    </button>
                                                    <button
                                                        onClick={() => pushFeature(selectedFeature)}
                                                        disabled={pushingAll}
                                                        className="flex items-center gap-1.5 px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl shadow-md shadow-blue-600/20 transition-all"
                                                    >
                                                        {pushingAll ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                                                        Commit & Push
                                                    </button>
                                                </>
                                            )}

                                            {!impl?.done && !impl?.implementing && (
                                                <button
                                                    onClick={() => implementFeature(selectedFeature)}
                                                    className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-500 to-amber-500 hover:from-orange-400 hover:to-amber-400 text-white text-xs font-semibold rounded-xl shadow-lg shadow-orange-500/20 transition-all hover:scale-[1.01]"
                                                >
                                                    <Zap size={13} />
                                                    Implement Feature
                                                </button>
                                            )}

                                            {impl?.implementing && (
                                                <div className="flex items-center gap-2 text-xs font-medium text-orange-400 bg-orange-500/10 border border-orange-500/20 px-3 py-1.5 rounded-xl">
                                                    <Loader2 size={13} className="animate-spin" />
                                                    Generating source files...
                                                </div>
                                            )}

                                            {impl?.done && (
                                                <button
                                                    onClick={() => setDiscardModalOpen(true)}
                                                    className="p-2 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-xl transition-all"
                                                    title="Discard implementation"
                                                >
                                                    <Trash2 size={14} />
                                                </button>
                                            )}
                                        </div>
                                    </div>

                                    {/* Plan / Code Area */}
                                    <div className="flex-1 overflow-hidden flex">
                                        <div className="w-80 border-r border-[var(--border-subtle)] overflow-y-auto shrink-0 bg-[var(--surface-0)]">
                                            {/* Pre-implementation plan view */}
                                            {!impl?.done && !impl?.implementing && (
                                                <div className="p-4 space-y-3">
                                                    <div className="flex items-center justify-between">
                                                        <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Planned Artifacts</span>
                                                        <span className="text-[11px] text-zinc-500">{filePlan.length} files</span>
                                                    </div>

                                                    {filePlan.map((p, i) => (
                                                        <div key={i} className="p-3 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl space-y-1">
                                                            <div className="flex items-center justify-between">
                                                                <span className="text-xs font-medium text-zinc-200 truncate">{p.fileName}</span>
                                                                <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase font-mono ${
                                                                    p.type === 'schemas' ? 'bg-blue-500/10 text-blue-400' :
                                                                    p.type === 'endpoints' ? 'bg-purple-500/10 text-purple-400' :
                                                                    'bg-pink-500/10 text-pink-400'
                                                                }`}>
                                                                    {p.type === 'schemas' ? 'DB' : p.type === 'endpoints' ? 'API' : 'UI'}
                                                                </span>
                                                            </div>
                                                            <p className="text-[10px] text-zinc-500 font-mono truncate">{p.filePath}</p>
                                                        </div>
                                                    ))}

                                                    {filePlan.length === 0 && (
                                                        <p className="text-xs text-zinc-500 py-6 text-center">No matching spec items found. Add tables or routes first.</p>
                                                    )}

                                                    {filePlan.length > 0 && (
                                                        <button
                                                            onClick={() => implementFeature(selectedFeature)}
                                                            className="w-full mt-3 flex items-center justify-center gap-2 py-2.5 bg-orange-500 hover:bg-orange-400 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-orange-500/20"
                                                        >
                                                            <Play size={12} />
                                                            Synthesize Code
                                                        </button>
                                                    )}
                                                </div>
                                            )}

                                            {/* Live Generation Console */}
                                            {impl?.implementing && (
                                                <div className="p-4 flex flex-col h-full bg-[var(--surface-0)] font-mono">
                                                    <div className="flex items-center gap-2 mb-3 text-orange-400 text-xs font-semibold">
                                                        <Loader2 size={13} className="animate-spin" />
                                                        <span>Synthesis in progress</span>
                                                    </div>
                                                    <div className="flex-1 text-[11px] space-y-1.5 overflow-y-auto text-zinc-400 bg-[var(--surface-1)] p-3 rounded-xl border border-[var(--border-subtle)]">
                                                        {genLogs.map((log, i) => (
                                                            <div key={i} className="animate-fade">
                                                                {log}
                                                            </div>
                                                        ))}
                                                        <div className="animate-pulse text-zinc-600">_</div>
                                                    </div>
                                                </div>
                                            )}

                                            {/* Generated Files list (post implementation) */}
                                            {impl?.done && (
                                                <div className="p-4 space-y-2">
                                                    <div className="flex items-center justify-between mb-1">
                                                        <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Generated Files</span>
                                                        <span className="text-[11px] text-zinc-500">{impl.files.length}</span>
                                                    </div>

                                                    {impl.files.map((f, i) => (
                                                        <button
                                                            key={i}
                                                            onClick={() => setOpenFile(f)}
                                                            className={`w-full flex items-center gap-2.5 p-3 rounded-xl border transition-all text-left ${
                                                                openFile?.filePath === f.filePath
                                                                    ? 'bg-blue-600/15 border-blue-500/30 text-white'
                                                                    : 'bg-[var(--surface-1)] border-[var(--border-subtle)] text-zinc-300 hover:border-zinc-700'
                                                            }`}
                                                        >
                                                            <File size={13} className={f.committed ? 'text-emerald-400 shrink-0' : 'text-amber-400 shrink-0'} />
                                                            <div className="flex-1 min-w-0">
                                                                <p className="text-xs font-medium truncate">{f.fileName}</p>
                                                                <p className="text-[10px] text-zinc-500 font-mono truncate">{f.filePath}</p>
                                                            </div>
                                                            {f.committed ? (
                                                                <Check size={12} className="text-emerald-400 shrink-0" />
                                                            ) : (
                                                                <span className="text-[9px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-400 font-bold shrink-0">
                                                                    DRAFT
                                                                </span>
                                                            )}
                                                        </button>
                                                    ))}

                                                    {!impl.files.every(f => f.committed) && (
                                                        <button
                                                            onClick={() => pushFeature(selectedFeature)}
                                                            disabled={pushingAll}
                                                            className="w-full mt-3 flex items-center justify-center gap-2 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-blue-600/20"
                                                        >
                                                            {pushingAll ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                                                            Commit & Push
                                                        </button>
                                                    )}
                                                </div>
                                            )}
                                        </div>

                                        {/* Code Viewer */}
                                        {openFile ? (
                                            <div className="flex-1 overflow-hidden">
                                                <CodeViewer
                                                    title={openFile.fileName}
                                                    code={openFile.code}
                                                    onChange={(code) => {
                                                        setOpenFile(f => f ? { ...f, code } : f);
                                                        setImplementations(prev => {
                                                            const featureImpl = prev[selectedFeature.id];
                                                            if (!featureImpl) return prev;
                                                            return {
                                                                ...prev,
                                                                [selectedFeature.id]: {
                                                                    ...featureImpl,
                                                                    files: featureImpl.files.map(fi =>
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
                                            <div className="flex-1 flex items-center justify-center text-center p-8 bg-[var(--surface-0)]">
                                                <div className="max-w-xs">
                                                    <Code2 size={24} className="text-zinc-700 mx-auto mb-2" />
                                                    <p className="text-xs text-zinc-500">
                                                        {impl?.done ? 'Click any file on the left to inspect and edit code' : 'Synthesize code to preview generated implementation'}
                                                    </p>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* File Tree Panel (Right Side) */}
                        {treeVisible ? (
                            <div className="w-56 bg-[var(--surface-1)] border-l border-[var(--border-subtle)] flex flex-col shrink-0">
                                <div className="h-10 border-b border-[var(--border-subtle)] flex items-center justify-between px-3 shrink-0">
                                    <span className="text-[10px] font-bold uppercase tracking-wider text-zinc-500">Project Tree</span>
                                    <button onClick={() => setTreeVisible(false)} className="text-zinc-500 hover:text-zinc-300 p-1">
                                        <X size={12} />
                                    </button>
                                </div>
                                <div className="flex-1 overflow-y-auto py-2">
                                    {buildTree().map(n => (
                                        <TreeItem key={n.path} node={n} onSelect={handleTreeSelect} selectedPath={selectedTreePath} />
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <button
                                onClick={() => setTreeVisible(true)}
                                className="w-8 bg-[var(--surface-1)] border-l border-[var(--border-subtle)] flex items-center justify-center text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
                                title="Show file tree"
                            >
                                <ChevronRight size={14} className="rotate-180" />
                            </button>
                        )}
                    </div>
                )}

                {/* ── DATABASE TAB ── */}
                {activeTab === 'database' && (
                    <div className="flex-1 overflow-auto p-8 max-w-4xl mx-auto w-full space-y-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-white">Database Schemas</h2>
                                <p className="text-xs text-zinc-400 mt-1">PostgreSQL tables and data models managed by Prisma.</p>
                            </div>
                            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                {schemas.length} models
                            </span>
                        </div>

                        {/* Add schema */}
                        <div className="flex items-center gap-2 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl px-3 py-2 focus-within:border-blue-500/50 transition-all">
                            <Plus size={14} className="text-zinc-400 shrink-0" />
                            <input
                                value={newTable}
                                onChange={e => setNewTable(e.target.value)}
                                onKeyDown={e => {
                                    if (e.key === 'Enter' && newTable.trim()) {
                                        addItem('schemas', { table_name: newTable.trim(), fields: [] });
                                        setNewTable('');
                                    }
                                }}
                                placeholder="Add database table (e.g. users, subscriptions, invoices)..."
                                className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 outline-none font-mono"
                            />
                        </div>

                        {/* Schemas List */}
                        <div className="space-y-2">
                            {schemas.map(s => (
                                <div key={s.id} className="group flex items-center justify-between p-3.5 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl hover:border-zinc-700 transition-all">
                                    <div className="flex items-center gap-3">
                                        <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-blue-500/10 text-blue-400 border border-blue-500/20">
                                            MODEL
                                        </span>
                                        <span className="text-sm font-semibold text-zinc-200 font-mono">{s.table_name}</span>
                                    </div>
                                    <div className="flex items-center gap-3">
                                        <span className="text-xs text-zinc-500">{s.fields?.length || 0} fields configured</span>
                                        <button
                                            onClick={() => deleteItem('schemas', s.id)}
                                            className="text-zinc-600 hover:text-red-400 p-1 opacity-40 group-hover:opacity-100 transition-all"
                                            title="Delete model"
                                        >
                                            <Trash2 size={13} />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* ── API ROUTES TAB ── */}
                {activeTab === 'api' && (
                    <div className="flex-1 overflow-auto p-8 max-w-4xl mx-auto w-full space-y-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-white">API Endpoints</h2>
                                <p className="text-xs text-zinc-400 mt-1">FastAPI routes and contract endpoints.</p>
                            </div>
                            <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                {endpoints.length} routes
                            </span>
                        </div>

                        {/* Add endpoint */}
                        <div className="flex items-center gap-3 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl px-3 py-2">
                            <select
                                value={newRouteMethod}
                                onChange={e => setNewRouteMethod(e.target.value)}
                                className={`px-2 py-0.5 rounded text-[11px] font-mono font-bold uppercase outline-none cursor-pointer border ${METHOD_COLORS[newRouteMethod]?.bg} ${METHOD_COLORS[newRouteMethod]?.text} ${METHOD_COLORS[newRouteMethod]?.border}`}
                            >
                                {['GET', 'POST', 'PUT', 'PATCH', 'DELETE'].map(m => <option key={m} value={m} className="bg-zinc-900 text-white">{m}</option>)}
                            </select>
                            <input
                                value={newRoute}
                                onChange={e => setNewRoute(e.target.value)}
                                onKeyDown={e => {
                                    if (e.key === 'Enter' && newRoute.trim()) {
                                        const route = newRoute.trim().startsWith('/') ? newRoute.trim() : `/${newRoute.trim()}`;
                                        addItem('endpoints', { method: newRouteMethod, route, request_schema: {}, response_schema: {} });
                                        setNewRoute('');
                                    }
                                }}
                                placeholder="/api/v1/resource (press Enter)..."
                                className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 outline-none font-mono"
                            />
                        </div>

                        {/* Routes List */}
                        <div className="space-y-2">
                            {endpoints.map(ep => {
                                const badge = METHOD_COLORS[ep.method] || { bg: 'bg-zinc-800', text: 'text-zinc-300', border: 'border-zinc-700' };
                                return (
                                    <div key={ep.id} className="group flex items-center justify-between p-3.5 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl hover:border-zinc-700 transition-all">
                                        <div className="flex items-center gap-3">
                                            <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${badge.bg} ${badge.text} ${badge.border}`}>
                                                {ep.method}
                                            </span>
                                            <span className="text-xs font-mono font-medium text-zinc-200">{ep.route}</span>
                                        </div>
                                        <button
                                            onClick={() => deleteItem('endpoints', ep.id)}
                                            className="text-zinc-600 hover:text-red-400 p-1 opacity-40 group-hover:opacity-100 transition-all"
                                            title="Delete endpoint"
                                        >
                                            <Trash2 size={13} />
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}

                {/* ── UI COMPONENTS & VIEWS TAB ── */}
                {activeTab === 'ui' && (
                    <div className="flex-1 overflow-auto p-8 max-w-4xl mx-auto w-full space-y-6">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                            <div>
                                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                    <LayoutPanelTop size={20} className="text-pink-400" />
                                    <span>UI Views, Templates & Components</span>
                                </h2>
                                <p className="text-xs text-zinc-400 mt-1">
                                    Discovered views and templates across HTML/Jinja, Next.js, React, Vue, Svelte, and Angular.
                                </p>
                            </div>
                            <div className="flex items-center gap-2 flex-wrap">
                                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                    {uiComponents.filter(c => c.type === 'template').length} templates
                                </span>
                                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
                                    {uiComponents.filter(c => c.type === 'page').length} pages
                                </span>
                                <span className="px-2.5 py-1 rounded-full text-xs font-semibold bg-pink-500/10 text-pink-400 border border-pink-500/20">
                                    {uiComponents.filter(c => c.type === 'component').length} components
                                </span>
                            </div>
                        </div>

                        {/* Add UI Component / View Card */}
                        <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-4 space-y-3">
                            <span className="text-xs font-semibold text-zinc-300">Add New View or Component</span>
                            <div className="grid grid-cols-1 sm:grid-cols-12 gap-2.5">
                                <div className="sm:col-span-5 flex items-center gap-2 bg-[var(--surface-2)] border border-[var(--border-subtle)] rounded-xl px-3 py-2">
                                    <Plus size={14} className="text-zinc-400 shrink-0" />
                                    <input
                                        value={newUI}
                                        onChange={e => setNewUI(e.target.value)}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter' && newUI.trim()) {
                                                addItem('ui-components', {
                                                    name: newUI.trim(),
                                                    type: newUIType,
                                                    route: newUIRoute.trim() || (newUIType === 'template' || newUIType === 'page' ? '/' : undefined)
                                                });
                                                setNewUI('');
                                                setNewUIRoute('');
                                            }
                                        }}
                                        placeholder="View or template name (e.g. Index Template, Dashboard View)..."
                                        className="flex-1 bg-transparent text-xs text-zinc-200 placeholder:text-zinc-500 outline-none"
                                    />
                                </div>
                                <div className="sm:col-span-3">
                                    <select
                                        value={newUIType}
                                        onChange={e => setNewUIType(e.target.value as any)}
                                        className="w-full h-full bg-[var(--surface-2)] border border-[var(--border-subtle)] text-xs text-zinc-300 rounded-xl px-3 py-2 outline-none focus:border-pink-500/50"
                                    >
                                        <option value="template">Template (HTML / Jinja)</option>
                                        <option value="page">Page / View</option>
                                        <option value="component">Component</option>
                                        <option value="layout">Layout</option>
                                    </select>
                                </div>
                                <div className="sm:col-span-3">
                                    <input
                                        value={newUIRoute}
                                        onChange={e => setNewUIRoute(e.target.value)}
                                        placeholder="Route (e.g. /, /predict)"
                                        className="w-full bg-[var(--surface-2)] border border-[var(--border-subtle)] text-xs text-zinc-300 rounded-xl px-3 py-2 outline-none placeholder:text-zinc-600 focus:border-pink-500/50"
                                    />
                                </div>
                                <div className="sm:col-span-1">
                                    <button
                                        onClick={() => {
                                            if (!newUI.trim()) return;
                                            addItem('ui-components', {
                                                name: newUI.trim(),
                                                type: newUIType,
                                                route: newUIRoute.trim() || (newUIType === 'template' || newUIType === 'page' ? '/' : undefined)
                                            });
                                            setNewUI('');
                                            setNewUIRoute('');
                                        }}
                                        disabled={!newUI.trim()}
                                        className="w-full h-full flex items-center justify-center bg-pink-600 hover:bg-pink-500 disabled:opacity-40 text-white rounded-xl text-xs font-semibold py-2 transition-all"
                                        title="Add View"
                                    >
                                        Add
                                    </button>
                                </div>
                            </div>
                        </div>

                        {/* Views & Components List */}
                        <div className="space-y-2.5">
                            {uiComponents.length === 0 ? (
                                <div className="p-8 text-center rounded-2xl bg-[var(--surface-1)] border border-[var(--border-subtle)]">
                                    <LayoutPanelTop size={32} className="mx-auto text-zinc-600 mb-3" />
                                    <p className="text-sm font-semibold text-zinc-300">No UI views or templates detected</p>
                                    <p className="text-xs text-zinc-500 mt-1 max-w-md mx-auto">
                                        Click &quot;Rescan Repo&quot; to automatically discover all HTML templates, React/Next.js pages, Vue SFCs, or add custom views above.
                                    </p>
                                </div>
                            ) : (
                                uiComponents.map(c => {
                                    const typePill =
                                        c.type === 'template'
                                            ? { bg: 'bg-emerald-500/10', text: 'text-emerald-400', border: 'border-emerald-500/20', label: 'TEMPLATE' }
                                            : c.type === 'page'
                                            ? { bg: 'bg-purple-500/10', text: 'text-purple-400', border: 'border-purple-500/20', label: 'PAGE' }
                                            : c.type === 'layout'
                                            ? { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/20', label: 'LAYOUT' }
                                            : { bg: 'bg-pink-500/10', text: 'text-pink-400', border: 'border-pink-500/20', label: 'COMPONENT' };

                                    return (
                                        <div
                                            key={c.id}
                                            className="group flex items-center justify-between p-3.5 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl hover:border-zinc-700 transition-all"
                                        >
                                            <div className="flex items-center gap-3 min-w-0">
                                                <span className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase ${typePill.bg} ${typePill.text} border ${typePill.border} shrink-0`}>
                                                    {typePill.label}
                                                </span>
                                                <span className="text-xs font-semibold text-zinc-200 truncate">{c.name}</span>
                                                {c.route && (
                                                    <span className="text-[11px] font-mono text-zinc-400 bg-zinc-800/80 px-2 py-0.5 rounded border border-zinc-700/60 shrink-0">
                                                        {c.route}
                                                    </span>
                                                )}
                                            </div>

                                            <div className="flex items-center gap-2 shrink-0">
                                                {c.code && (
                                                    <button
                                                        onClick={() => setSelectedViewCode(c)}
                                                        className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-zinc-800/90 hover:bg-zinc-700 text-zinc-200 border border-zinc-700/60 transition-all"
                                                        title="View source code or template HTML"
                                                    >
                                                        <Code2 size={13} className="text-amber-400" />
                                                        <span>View Code</span>
                                                    </button>
                                                )}
                                                <button
                                                    onClick={() => deleteItem('ui-components', c.id)}
                                                    className="text-zinc-600 hover:text-red-400 p-1.5 opacity-40 group-hover:opacity-100 transition-all"
                                                    title="Delete view"
                                                >
                                                    <Trash2 size={13} />
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>

                        {/* Code Preview Drawer / Modal */}
                        {selectedViewCode && (
                            <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
                                <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
                                    <div className="h-12 px-4 border-b border-[var(--border-subtle)] flex items-center justify-between shrink-0 bg-[var(--surface-2)]/60">
                                        <div className="flex items-center gap-2.5">
                                            <Code2 size={16} className="text-amber-400" />
                                            <span className="text-sm font-bold text-white">{selectedViewCode.name}</span>
                                            <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase bg-pink-500/10 text-pink-400 border border-pink-500/20">
                                                {selectedViewCode.type}
                                            </span>
                                            {selectedViewCode.route && (
                                                <span className="text-[11px] font-mono text-zinc-400 bg-zinc-800 px-2 py-0.5 rounded border border-zinc-700/60">
                                                    {selectedViewCode.route}
                                                </span>
                                            )}
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <button
                                                onClick={() => {
                                                    navigator.clipboard.writeText(selectedViewCode.code || '');
                                                    showToast('Source copied to clipboard!');
                                                }}
                                                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold text-zinc-300 hover:text-white bg-zinc-800 hover:bg-zinc-700 transition-all border border-zinc-700/60"
                                            >
                                                <Copy size={13} />
                                                <span>Copy</span>
                                            </button>
                                            <button
                                                onClick={() => setSelectedViewCode(null)}
                                                className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-800 transition-all"
                                            >
                                                <X size={16} />
                                            </button>
                                        </div>
                                    </div>
                                    <div className="flex-1 overflow-auto p-4 bg-[var(--surface-0)] font-mono text-xs leading-relaxed text-zinc-200 select-text">
                                        <pre className="whitespace-pre-wrap break-all">
                                            {selectedViewCode.code || '<!-- No source code available for this view -->'}
                                        </pre>
                                    </div>
                                </div>
                            </div>
                        )}
                    </div>
                )}

                {/* ── AI INSIGHTS TAB ── */}
                {activeTab === 'insights' && (
                    <div className="flex-1 overflow-auto p-8 max-w-4xl mx-auto w-full space-y-6">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-xl font-bold text-white flex items-center gap-2">
                                    <Brain size={20} className="text-amber-400" />
                                    <span>AI Architecture Insights</span>
                                </h2>
                                <p className="text-xs text-zinc-400 mt-1">Automatic consistency checks and architecture gap detection.</p>
                            </div>
                            <button
                                onClick={loadRecommendations}
                                disabled={recsLoading}
                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-zinc-300 hover:text-white bg-[var(--surface-1)] border border-[var(--border-subtle)] hover:border-zinc-700 transition-all disabled:opacity-50"
                            >
                                {recsLoading ? <Loader2 size={12} className="animate-spin" /> : <TrendingUp size={12} />}
                                Refresh Analysis
                            </button>
                        </div>

                        {/* Project Completeness Overview */}
                        {recommendations && (
                            <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-5 space-y-4">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-semibold text-zinc-400">Identified Archetype:</span>
                                    <span className="text-xs font-bold text-amber-400 uppercase tracking-wider px-2 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                                        {recommendations.project_type}
                                    </span>
                                </div>
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2">
                                    {Object.entries(recommendations.completeness_scores || {}).map(([key, value]: [string, any]) => (
                                        <div key={key} className="p-3 bg-[var(--surface-2)] rounded-xl border border-[var(--border-subtle)]">
                                            <div className="flex justify-between items-center mb-2">
                                                <span className="text-[11px] text-zinc-400 capitalize">{key}</span>
                                                <span className="text-xs font-bold text-zinc-200">{Math.round(value * 100)}%</span>
                                            </div>
                                            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full rounded-full transition-all duration-500 ${
                                                        value >= 0.7 ? 'bg-emerald-500' : value >= 0.4 ? 'bg-amber-500' : 'bg-red-500'
                                                    }`}
                                                    style={{ width: `${Math.round(value * 100)}%` }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {recsLoading && !recommendations && (
                            <div className="flex items-center justify-center py-16">
                                <Loader2 size={20} className="animate-spin text-amber-400" />
                                <span className="ml-2.5 text-xs text-zinc-400">Analyzing schema & routes consistency...</span>
                            </div>
                        )}

                        {/* Recommendations */}
                        {recommendations && (['critical', 'recommended', 'nice_to_have'] as const).map(severity => {
                            const recs = recommendations.recommendations?.[severity] || [];
                            if (recs.length === 0) return null;
                            const config = {
                                critical: { label: 'Critical Issues', icon: ShieldAlert, color: 'text-red-400', border: 'border-red-500/25', bg: 'bg-red-500/5' },
                                recommended: { label: 'Recommended Improvements', icon: Lightbulb, color: 'text-amber-400', border: 'border-amber-500/25', bg: 'bg-amber-500/5' },
                                nice_to_have: { label: 'Nice-to-Have Enhancements', icon: Info, color: 'text-blue-400', border: 'border-blue-500/25', bg: 'bg-blue-500/5' },
                            }[severity];
                            const Icon = config.icon;
                            return (
                                <div key={severity} className="space-y-3">
                                    <div className="flex items-center gap-2">
                                        <Icon size={14} className={config.color} />
                                        <h3 className={`text-xs font-bold uppercase tracking-wider ${config.color}`}>
                                            {config.label} ({recs.length})
                                        </h3>
                                    </div>
                                    <div className="space-y-2">
                                        {recs.map((rec: any) => (
                                            <div key={rec.id} className={`group ${config.bg} border ${config.border} rounded-xl p-4 transition-all hover:border-zinc-600`}>
                                                <div className="flex items-start justify-between gap-3">
                                                    <div className="space-y-1">
                                                        <h4 className="text-xs font-bold text-zinc-100">{rec.title}</h4>
                                                        <p className="text-xs text-zinc-400 leading-relaxed">{rec.description}</p>
                                                        <div className="flex items-center gap-2 pt-1">
                                                            <span className="text-[10px] px-2 py-0.5 rounded font-mono font-bold uppercase bg-zinc-800 text-zinc-300">
                                                                {rec.layer}
                                                            </span>
                                                            <span className="text-[10px] text-zinc-500">{rec.type?.replace('_', ' ')}</span>
                                                        </div>
                                                    </div>
                                                    <div className="flex items-center gap-2 shrink-0">
                                                        {rec.action?.type !== 'info' && rec.action?.type !== 'navigate' && (
                                                            <button
                                                                onClick={() => handleApplyRec(rec.id)}
                                                                disabled={applyingRecId === rec.id}
                                                                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25 border border-emerald-500/30 transition-all disabled:opacity-50"
                                                            >
                                                                {applyingRecId === rec.id ? <Loader2 size={11} className="animate-spin" /> : <Check size={11} />}
                                                                Apply
                                                            </button>
                                                        )}
                                                        <button
                                                            onClick={() => handleDismissRec(rec.id)}
                                                            className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-[var(--surface-2)] transition-all"
                                                            title="Dismiss"
                                                        >
                                                            <EyeOff size={13} />
                                                        </button>
                                                    </div>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            );
                        })}

                        {recommendations && recommendations.total_count === 0 && (
                            <div className="text-center py-16 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl">
                                <Check size={28} className="mx-auto text-emerald-400 mb-2" />
                                <h3 className="text-sm font-semibold text-zinc-200">Architecture is fully consistent</h3>
                                <p className="text-xs text-zinc-500 mt-1">No missing schemas, unhandled routes, or orphaned components detected.</p>
                            </div>
                        )}
                    </div>
                )}

                {/* ── OVERVIEW TAB ── */}
                {activeTab === 'overview' && (
                    <div className="flex-1 overflow-auto p-8 max-w-4xl mx-auto w-full space-y-6">
                        <div>
                            <h2 className="text-xl font-bold text-white">Project Overview</h2>
                            <p className="text-xs text-zinc-400 mt-1">Summary of layers and current code implementation status.</p>
                        </div>

                        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                            {[
                                { label: 'Features', value: features.length, color: 'text-amber-400' },
                                { label: 'Data Models', value: schemas.length, color: 'text-blue-400' },
                                { label: 'Endpoints', value: endpoints.length, color: 'text-purple-400' },
                                { label: 'UI Views', value: uiComponents.length, color: 'text-pink-400' },
                                { label: 'Implemented', value: Object.values(implementations).filter(i => i.done).length, color: 'text-emerald-400' },
                            ].map(({ label, value, color }) => (
                                <div key={label} className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl p-4">
                                    <p className="text-[10px] text-zinc-500 uppercase tracking-wider font-semibold mb-1">{label}</p>
                                    <p className={`text-2xl font-bold ${color}`}>{value}</p>
                                </div>
                            ))}
                        </div>

                        <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-xl p-5 space-y-3 font-mono text-xs">
                            <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
                                <span className="text-zinc-400">Repository Name</span>
                                <span className="text-zinc-200 font-bold">{project?.name}</span>
                            </div>
                            <div className="flex items-center justify-between pb-3 border-b border-[var(--border-subtle)]">
                                <span className="text-zinc-400">GitHub Remote</span>
                                <a href={project?.repo_url} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">
                                    {project?.repo_url}
                                </a>
                            </div>
                            <div className="pt-1">
                                <span className="text-zinc-500 block mb-1">Configured Features:</span>
                                <div className="flex flex-wrap gap-1.5">
                                    {features.map((f: any) => (
                                        <span key={f.id} className="px-2 py-0.5 rounded bg-[var(--surface-2)] text-zinc-300 border border-[var(--border-subtle)] text-[11px]">
                                            {f.name}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* ── ERD TAB: Auto-laid-out Diagrams & Exports ── */}
                {activeTab === 'erd' && (
                    <div className="flex-1 overflow-hidden h-full">
                        <ERDView projectId={Number(id)} onShowToast={showToast} />
                    </div>
                )}

                {/* ── DRIFT TAB: Drift Detection, 3-Way Sync & PR Governance ── */}
                {activeTab === 'drift' && (
                    <div className="flex-1 overflow-hidden h-full flex flex-col">
                        <DriftPanel projectId={Number(id)} onSpecUpdated={fetchProjectData} onShowToast={showToast} />
                    </div>
                )}

                {/* ── CHAT & IMPACT ANALYSIS TAB ── */}
                {activeTab === 'chat' && (
                    <div className="flex-1 overflow-hidden h-full">
                        <ArchitectureChat projectId={Number(id)} />
                    </div>
                )}

                {/* ── DESIGN CRITIQUE TAB ── */}
                {activeTab === 'critique' && (
                    <div className="flex-1 overflow-hidden h-full">
                        <DesignCritique projectId={Number(id)} />
                    </div>
                )}

                {/* ── ARCHITECTURAL DECISION RECORDS TAB ── */}
                {activeTab === 'adrs' && (
                    <div className="flex-1 overflow-hidden h-full">
                        <ADRView projectId={Number(id)} onShowToast={showToast} />
                    </div>
                )}
            </div>

            {/* Discard Confirmation Modal */}
            {discardModalOpen && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4 animate-fade">
                    <div className="bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl p-6 max-w-sm w-full space-y-4 shadow-2xl">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 shrink-0">
                                <Trash2 size={18} />
                            </div>
                            <div>
                                <h3 className="text-sm font-bold text-white">Discard generated files?</h3>
                                <p className="text-xs text-zinc-400 mt-0.5">This will clear the drafts for this feature.</p>
                            </div>
                        </div>
                        <div className="flex items-center justify-end gap-2 pt-2">
                            <button
                                onClick={() => setDiscardModalOpen(false)}
                                className="px-3.5 py-1.5 rounded-xl text-xs font-semibold text-zinc-400 hover:text-white hover:bg-[var(--surface-2)] transition-all"
                            >
                                Cancel
                            </button>
                            <button
                                onClick={confirmDiscard}
                                className="px-4 py-1.5 rounded-xl text-xs font-semibold bg-red-600 hover:bg-red-500 text-white transition-all shadow-md shadow-red-600/20"
                            >
                                Discard
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Drafts Tray Slideout */}
            {showDraftsTray && (
                <div className="fixed bottom-14 right-6 w-84 bg-[var(--surface-1)] border border-[var(--border-subtle)] rounded-2xl shadow-2xl z-40 overflow-hidden animate-slideUp">
                    <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-subtle)]">
                        <div className="flex items-center gap-2">
                            <Inbox size={14} className="text-amber-400" />
                            <span className="text-xs font-bold text-zinc-200">{allDraftFiles.length} pending draft{allDraftFiles.length !== 1 ? 's' : ''}</span>
                        </div>
                        <button onClick={() => setShowDraftsTray(false)} className="text-zinc-500 hover:text-white">
                            <X size={14} />
                        </button>
                    </div>
                    <div className="max-h-64 overflow-y-auto divide-y divide-[var(--border-subtle)]">
                        {allDraftFiles.length === 0 ? (
                            <p className="text-xs text-zinc-500 p-6 text-center">No uncommitted drafts found.</p>
                        ) : allDraftFiles.map((f, i) => (
                            <div key={i} className="flex items-center gap-3 px-4 py-2.5">
                                <File size={12} className="text-amber-400 shrink-0" />
                                <div className="flex-1 min-w-0">
                                    <p className="text-xs font-medium text-zinc-200 truncate">{f.fileName}</p>
                                    <p className="text-[10px] text-zinc-500 font-mono truncate">{f.filePath}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                    {allDraftFiles.length > 0 && (
                        <div className="p-3 border-t border-[var(--border-subtle)] bg-[var(--surface-2)]">
                            <button
                                onClick={() => { if (selectedFeature) pushFeature(selectedFeature); }}
                                disabled={pushingAll || !selectedFeature}
                                className="w-full flex items-center justify-center gap-2 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-xs font-semibold rounded-xl transition-all shadow-md shadow-blue-600/20"
                            >
                                {pushingAll ? <Loader2 size={13} className="animate-spin" /> : <Send size={13} />}
                                Commit & Push All
                            </button>
                        </div>
                    )}
                </div>
            )}

            {/* Custom Toast Notification */}
            {toast && (
                <div className={`fixed bottom-6 left-1/2 -translate-x-1/2 px-4 py-2 rounded-xl text-xs font-semibold shadow-xl z-50 flex items-center gap-2 animate-slideUp ${
                    toast.ok ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'
                }`}>
                    {toast.ok ? <Check size={14} /> : <AlertCircle size={14} />}
                    <span>{toast.msg}</span>
                </div>
            )}
            {/* Build Prompt Modal */}
            {selectedFeature && (
                <BuildPromptModal
                    projectId={Number(id)}
                    featureId={selectedFeature.id}
                    featureName={selectedFeature.name}
                    isOpen={showBuildPrompt}
                    onClose={() => setShowBuildPrompt(false)}
                    onShowToast={showToast}
                />
            )}

            {/* PRD & Wireframe to Spec Modal */}
            <DocToSpecModal
                projectId={Number(id)}
                isOpen={showDocToSpec}
                onClose={() => setShowDocToSpec(false)}
                onSpecApplied={fetchProjectData}
                onShowToast={showToast}
            />
        </div>
    );
}
