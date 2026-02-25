'use client';

import React, { useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import api from '@/lib/api';

function CallbackContent() {
    const router = useRouter();
    const searchParams = useSearchParams();

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
                    console.error(err);
                    router.push('/');
                });
        }
    }, [searchParams, router]);

    return (
        <div className="flex items-center justify-center min-h-screen">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-gray-900"></div>
        </div>
    );
}

export default function AuthCallback() {
    return (
        <Suspense fallback={<div>Loading...</div>}>
            <CallbackContent />
        </Suspense>
    );
}
