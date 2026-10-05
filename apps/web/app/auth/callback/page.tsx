'use client';

import React, { useEffect, useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Github, AlertCircle, ArrowLeft } from 'lucide-react';
import api from '@/lib/api';

function CallbackContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const code = searchParams.get('code');
        if (code) {
            api.post('/auth/github', { code })
                .then((res) => {
                    localStorage.setItem('token', res.data.access_token);
                    localStorage.setItem('username', res.data.username);
                    router.push('/dashboard');
                })
                .catch((err) => {
                    console.error('Authentication error:', err);
                    setError('Failed to authenticate with GitHub. The authorization code may have expired or is invalid.');
                });
        } else {
            setError('No authorization code provided in callback.');
        }
    }, [searchParams, router]);

    if (error) {
        return (
            <div className="min-h-screen bg-[var(--surface-0)] flex items-center justify-center p-6 text-zinc-100">
                <div className="max-w-md w-full p-8 rounded-2xl bg-[var(--surface-1)] border border-red-500/30 text-center space-y-4 shadow-2xl">
                    <div className="w-12 h-12 rounded-2xl bg-red-500/10 border border-red-500/25 flex items-center justify-center mx-auto text-red-400">
                        <AlertCircle size={22} />
                    </div>
                    <h2 className="text-lg font-bold text-white">Authentication Failed</h2>
                    <p className="text-xs text-zinc-400 leading-relaxed">{error}</p>
                    <button
                        onClick={() => router.push('/')}
                        className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-white transition-all"
                    >
                        <ArrowLeft size={14} /> Return to Home
                    </button>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-[var(--surface-0)] flex flex-col items-center justify-center p-6 text-zinc-100">
            <div className="relative flex items-center justify-center mb-6">
                <div className="absolute w-20 h-20 rounded-full bg-blue-500/15 blur-xl animate-pulse" />
                <div className="w-14 h-14 rounded-2xl bg-[var(--surface-1)] border border-[var(--border-subtle)] flex items-center justify-center shadow-xl">
                    <Github size={26} className="text-white" />
                </div>
            </div>

            <div className="flex items-center gap-2.5 text-sm font-semibold text-zinc-200 mb-2">
                <Loader2 size={16} className="animate-spin text-blue-500" />
                <span>Authenticating with GitHub...</span>
            </div>
            <p className="text-xs text-zinc-500">Connecting your account and setting up your workspace.</p>
        </div>
    );
}

export default function AuthCallback() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-[var(--surface-0)] flex items-center justify-center text-zinc-400 text-xs">
                <Loader2 size={18} className="animate-spin text-blue-500 mr-2" /> Loading...
            </div>
        }>
            <CallbackContent />
        </Suspense>
    );
}
