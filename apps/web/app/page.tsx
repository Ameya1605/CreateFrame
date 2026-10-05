'use client';

import { Github, Cpu, ShieldCheck, Zap, Globe, ArrowRight } from 'lucide-react';

export default function Home() {
  const handleLogin = () => {
    const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID;
    const redirectUri = encodeURIComponent(`${window.location.origin}/auth/callback`);
    window.location.href = `https://github.com/login/oauth/authorize?client_id=${clientId}&redirect_uri=${redirectUri}&scope=repo,user,admin:repo_hook`;
  };

  return (
    <div className="min-h-screen bg-[var(--surface-0)] text-zinc-100 flex flex-col items-center selection:bg-blue-500/30 selection:text-blue-200 relative overflow-hidden">

      {/* Animated background orbs */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div
          className="absolute w-[600px] h-[600px] rounded-full opacity-20 blur-[120px]"
          style={{
            background: 'radial-gradient(circle, #3b82f6 0%, transparent 70%)',
            top: '-10%',
            left: '50%',
            transform: 'translateX(-50%)',
            animation: 'float 20s ease-in-out infinite',
          }}
        />
        <div
          className="absolute w-[400px] h-[400px] rounded-full opacity-10 blur-[100px]"
          style={{
            background: 'radial-gradient(circle, #a855f7 0%, transparent 70%)',
            bottom: '5%',
            right: '10%',
            animation: 'float 15s ease-in-out infinite reverse',
          }}
        />
        <div
          className="absolute w-[300px] h-[300px] rounded-full opacity-10 blur-[80px]"
          style={{
            background: 'radial-gradient(circle, #14b8a6 0%, transparent 70%)',
            bottom: '20%',
            left: '5%',
            animation: 'float 18s ease-in-out infinite 3s',
          }}
        />
      </div>

      {/* Nav */}
      <nav className="w-full max-w-7xl mx-auto px-6 py-5 flex items-center justify-between relative z-10 animate-fade">
        <div className="flex items-center gap-2.5">
          <div className="bg-blue-500/10 p-2 rounded-xl border border-blue-500/20">
            <Cpu size={18} className="text-blue-400" />
          </div>
          <span className="text-sm font-bold tracking-wider uppercase text-zinc-300">CreateFrame</span>
        </div>
        <button
          onClick={handleLogin}
          className="flex items-center gap-2 text-sm text-zinc-400 hover:text-white transition-colors px-4 py-2 rounded-lg hover:bg-zinc-800/50"
        >
          <Github size={16} />
          Sign in
        </button>
      </nav>

      {/* Hero Section */}
      <main className="flex-1 flex flex-col items-center justify-center px-6 text-center max-w-5xl relative z-10">
        <div className="animate-fade flex flex-col items-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs font-semibold mb-8 animate-slide-up" style={{ animationDelay: '0.1s' }}>
            <Zap size={12} />
            Architecture-first development
          </div>

          <h1 className="text-4xl sm:text-6xl md:text-8xl font-black tracking-tighter mb-6 leading-[0.95]">
            Architect <br />
            <span className="gradient-text">Before You Code.</span>
          </h1>

          <p className="text-zinc-400 text-base sm:text-lg md:text-xl max-w-2xl mb-12 leading-relaxed font-medium">
            CreateFrame is the technical control plane for modern builders. Define your schemas,
            API endpoints, and prompts in one place. Sync directly to GitHub.
          </p>

          <div className="flex flex-col sm:flex-row items-center gap-4">
            <button
              onClick={handleLogin}
              className="group relative flex items-center gap-3 bg-white text-black px-8 sm:px-10 py-4 sm:py-5 rounded-2xl font-black text-base sm:text-lg transition-all hover:scale-105 active:scale-95 shadow-2xl shadow-white/5 overflow-hidden"
            >
              {/* Shimmer effect */}
              <div className="absolute inset-0 -translate-x-full group-hover:translate-x-full transition-transform duration-700 bg-gradient-to-r from-transparent via-white/20 to-transparent" />
              <Github size={22} />
              <span className="relative">Connect GitHub</span>
              <ArrowRight size={18} className="relative group-hover:translate-x-1 transition-transform" />
            </button>

            <a
              href="#features"
              className="text-sm text-zinc-500 hover:text-zinc-300 transition-colors px-6 py-3 rounded-xl border border-zinc-800 hover:border-zinc-700 font-semibold"
            >
              Learn more
            </a>
          </div>
        </div>

        {/* Features Grid */}
        <div id="features" className="mt-28 sm:mt-32 grid grid-cols-1 md:grid-cols-3 gap-5 w-full stagger-children">
          {[
            {
              icon: ShieldCheck,
              title: 'Versioned Specs',
              desc: 'Persist your architecture directly in your repository as source of truth.',
              color: 'blue',
            },
            {
              icon: Zap,
              title: 'Instant Sync',
              desc: 'One click to generate and push spec.json using native GitHub integrations.',
              color: 'purple',
            },
            {
              icon: Globe,
              title: 'Omni-Channel',
              desc: 'The unified interface for Database, API, and Prompt engineering.',
              color: 'teal',
            },
          ].map(({ icon: Icon, title, desc, color }) => {
            const colorMap: Record<string, string> = {
              blue: 'group-hover:text-blue-400 group-hover:border-blue-500/30 group-hover:bg-blue-500/5',
              purple: 'group-hover:text-purple-400 group-hover:border-purple-500/30 group-hover:bg-purple-500/5',
              teal: 'group-hover:text-teal-400 group-hover:border-teal-500/30 group-hover:bg-teal-500/5',
            };
            const iconColor: Record<string, string> = {
              blue: 'group-hover:text-blue-400',
              purple: 'group-hover:text-purple-400',
              teal: 'group-hover:text-teal-400',
            };
            return (
              <div
                key={title}
                className={`group p-7 sm:p-8 glass rounded-2xl text-left transition-all duration-300 hover:scale-[1.02] cursor-default ${colorMap[color]}`}
              >
                <div className={`p-3 bg-zinc-800/80 w-fit rounded-xl text-zinc-400 ${iconColor[color]} transition-colors mb-5`}>
                  <Icon size={22} />
                </div>
                <h3 className="text-base font-bold mb-2 text-zinc-200">{title}</h3>
                <p className="text-zinc-500 text-sm leading-relaxed">{desc}</p>
              </div>
            );
          })}
        </div>
      </main>

      {/* Footer */}
      <footer className="py-10 sm:py-12 border-t border-zinc-800/50 w-full mt-20 relative z-10">
        <div className="max-w-7xl mx-auto px-6 flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2 opacity-40 hover:opacity-70 transition-opacity">
            <Cpu size={14} />
            <span className="text-xs font-bold uppercase tracking-[0.25em]">CreateFrame</span>
            <span className="text-[10px] text-zinc-600 ml-1">v1.0</span>
          </div>
          <p className="text-zinc-600 text-xs font-medium tracking-wide">
            Architecture-first development for modern builders.
          </p>
        </div>
      </footer>
    </div>
  );
}
