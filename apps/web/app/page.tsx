'use client';

import { Github, Cpu, ShieldCheck, Zap, Globe } from 'lucide-react';

export default function Home() {
  const handleLogin = () => {
    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID;
    const redirectUri = encodeURIComponent(`${window.location.origin}/auth/callback`);
    window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=repo,user,admin:repo_hook`;
  };

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex flex-col items-center selection:bg-blue-500/30 selection:text-blue-200">
      {/* Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 text-center max-w-5xl">
        <div className="animate-fade flex flex-col items-center">
          <div className="bg-blue-600/10 p-4 rounded-3xl mb-10 border border-blue-500/20 shadow-2xl shadow-blue-500/10">
            <Cpu className="text-blue-500 w-12 h-12" />
          </div>

          <h1 className="text-6xl md:text-8xl font-black tracking-tighter mb-6">
            Architect <br />
            <span className="gradient-text">Before You Code.</span>
          </h1>

          <p className="text-zinc-500 text-lg md:text-xl max-w-2xl mb-12 leading-relaxed font-medium">
            SpecOS is the technical control plane for modern builders. Define your schemas,
            API endpoints, and prompts in one place. Sync directly to GitHub.
          </p>

          <button
            onClick={handleLogin}
            className="group relative flex items-center gap-4 bg-white text-black px-10 py-5 rounded-2xl font-black text-lg transition-all hover:scale-105 active:scale-95 shadow-2xl shadow-white/5"
          >
            <Github size={24} />
            Connect GitHub Account
            <div className="absolute inset-0 rounded-2xl border-2 border-white/20 group-hover:border-white/40 transition-all opacity-0 group-hover:opacity-100 blur-xl" />
          </button>
        </div>

        {/* Features Minimal Grid */}
        <div className="mt-32 grid grid-cols-1 md:grid-cols-3 gap-8 w-full animate-fade" style={{ animationDelay: '0.2s' }}>
          <div className="p-8 bg-zinc-900/50 border border-zinc-900 rounded-[2.5rem] text-left group hover:border-zinc-700 transition-all">
            <div className="p-3 bg-zinc-800 w-fit rounded-2xl text-zinc-400 group-hover:text-blue-500 transition-colors mb-4">
              <ShieldCheck size={24} />
            </div>
            <h3 className="text-lg font-bold mb-2">Versioned Specs</h3>
            <p className="text-zinc-500 text-sm leading-relaxed">Persist your architecture directly in your repository as source of truth.</p>
          </div>

          <div className="p-8 bg-zinc-900/50 border border-zinc-900 rounded-[2.5rem] text-left group hover:border-zinc-700 transition-all">
            <div className="p-3 bg-zinc-800 w-fit rounded-2xl text-zinc-400 group-hover:text-purple-500 transition-colors mb-4">
              <Zap size={24} />
            </div>
            <h3 className="text-lg font-bold mb-2">Instant Sync</h3>
            <p className="text-zinc-500 text-sm leading-relaxed">One click to generate and push spec.json using native GitHub integrations.</p>
          </div>

          <div className="p-8 bg-zinc-900/50 border border-zinc-900 rounded-[2.5rem] text-left group hover:border-zinc-700 transition-all">
            <div className="p-3 bg-zinc-800 w-fit rounded-2xl text-zinc-400 group-hover:text-green-500 transition-colors mb-4">
              <Globe size={24} />
            </div>
            <h3 className="text-lg font-bold mb-2">Omni-Channel</h3>
            <p className="text-zinc-500 text-sm leading-relaxed">The unified interface for Database, API, and Prompt engineering.</p>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-12 border-t border-zinc-900 w-full mt-20">
        <div className="max-w-7xl mx-auto px-6 flex justify-between items-center">
          <div className="flex items-center gap-2 opacity-30 grayscale hover:grayscale-0 transition-all">
            <Cpu size={16} />
            <span className="text-xs font-black uppercase tracking-[0.3em]">SpecOS MVP</span>
          </div>
          <p className="text-zinc-600 text-[10px] uppercase font-bold tracking-widest">
            Built for the elite 1% of builders.
          </p>
        </div>
      </footer>
    </div>
  );
}
