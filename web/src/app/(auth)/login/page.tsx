'use client';

import { useState } from 'react';
import Link from 'next/link';
import { signIn } from 'next-auth/react';
import { useRouter } from 'next/navigation';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail]       = useState('');
  const [password, setPassword] = useState('');
  const [error, setError]       = useState('');
  const [loading, setLoading]   = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    const result = await signIn('credentials', { email, password, redirect: false });
    setLoading(false);
    if (result?.error) setError('Invalid email or password');
    else router.replace('/dashboard');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 to-blue-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-blue-800 rounded-xl flex items-center justify-center text-white font-bold text-lg">N</div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">NeuroGuard AI</h1>
            <p className="text-sm text-gray-500">Clinician Dashboard</p>
          </div>
        </div>

        <h2 className="text-2xl font-semibold text-gray-800 mb-2">Sign in</h2>
        <p className="text-gray-500 mb-6 text-sm">Access your patient monitoring portal</p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email" value={email} onChange={(e) => setEmail(e.target.value)} required
              className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              placeholder="clinician@hospital.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password" value={password} onChange={(e) => setPassword(e.target.value)} required
              className="w-full px-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit" disabled={loading}
            className="w-full bg-blue-800 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {/* Demo credentials hint */}
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-xl">
          <p className="text-xs font-semibold text-blue-800 mb-2">Demo credentials</p>
          <div className="space-y-1 text-xs text-blue-700 font-mono">
            <div
              className="cursor-pointer hover:bg-blue-100 rounded px-1 py-0.5 transition-colors"
              onClick={() => { setEmail('demo@neuroguard.ai'); setPassword('demo123'); }}
            >
              demo@neuroguard.ai / demo123 &nbsp;<span className="text-blue-500">(clinician)</span>
            </div>
            <div
              className="cursor-pointer hover:bg-blue-100 rounded px-1 py-0.5 transition-colors"
              onClick={() => { setEmail('admin@neuroguard.ai'); setPassword('admin123'); }}
            >
              admin@neuroguard.ai / admin123 &nbsp;<span className="text-blue-500">(admin)</span>
            </div>
          </div>
          <p className="text-xs text-blue-500 mt-2">Click a row to auto-fill</p>
        </div>

        <p className="mt-4 text-center text-xs text-gray-500">
          Don&apos;t have an account?{' '}
          <Link href="/register" className="text-blue-600 hover:underline font-medium">
            Sign up
          </Link>{' '}
          to create a real backend account.
        </p>
        <p className="mt-2 text-center text-xs text-gray-400">
          HIPAA-compliant · All data encrypted · Audit-logged
        </p>
      </div>
    </div>
  );
}
