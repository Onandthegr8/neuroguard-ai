'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { signIn } from 'next-auth/react';
import { api } from '@/lib/api/client';

export default function RegisterPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    email:          '',
    password:       '',
    age:            45,
    gender:         'f',
    family_history: false,
    risk_group:     'general',
  });
  const [error, setError]     = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      // 1. POST /user/register
      await api.auth.register({
        email:          form.email,
        password:       form.password,
        age:            Number(form.age),
        gender:         form.gender,
        family_history: form.family_history,
        risk_group:     form.risk_group,
      });

      // 2. Auto-login with the new credentials
      const result = await signIn('credentials', {
        email:    form.email,
        password: form.password,
        redirect: false,
      });
      if (result?.error) {
        setError('Account created, but login failed. Try signing in.');
      } else {
        router.replace('/dashboard');
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail
        ? JSON.stringify(e.response.data.detail)
        : 'Registration failed. Is the backend running?');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-900 to-blue-700 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl p-8 w-full max-w-md">
        <div className="flex items-center gap-3 mb-8">
          <div className="w-10 h-10 bg-blue-800 rounded-xl flex items-center justify-center text-white font-bold text-lg">N</div>
          <div>
            <h1 className="text-xl font-bold text-gray-900">NeuroGuard AI</h1>
            <p className="text-sm text-gray-500">Create your account</p>
          </div>
        </div>

        <h2 className="text-2xl font-semibold text-gray-800 mb-2">Sign up</h2>
        <p className="text-gray-500 mb-6 text-sm">
          Real account on the live backend — your typing patterns will be scored by the trained ML model.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Email</label>
            <input
              type="email" value={form.email}
              onChange={e => setForm(p => ({ ...p, email: e.target.value }))} required
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              placeholder="you@example.com"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Password</label>
            <input
              type="password" value={form.password}
              onChange={e => setForm(p => ({ ...p, password: e.target.value }))} required
              minLength={8}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              placeholder="At least 8 characters"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Age</label>
              <input
                type="number" min={18} max={120} value={form.age}
                onChange={e => setForm(p => ({ ...p, age: Number(e.target.value) }))}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Gender</label>
              <select
                value={form.gender}
                onChange={e => setForm(p => ({ ...p, gender: e.target.value }))}
                className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm bg-white"
              >
                <option value="f">Female</option>
                <option value="m">Male</option>
                <option value="o">Other</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Risk Group</label>
            <select
              value={form.risk_group}
              onChange={e => setForm(p => ({ ...p, risk_group: e.target.value }))}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm bg-white"
            >
              <option value="general">General population</option>
              <option value="high_risk">High-risk (age 60+ or family history)</option>
            </select>
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-700">
            <input
              type="checkbox" checked={form.family_history}
              onChange={e => setForm(p => ({ ...p, family_history: e.target.checked }))}
              className="rounded"
            />
            Family history of Parkinson&apos;s
          </label>

          <button
            type="submit" disabled={loading}
            className="w-full bg-blue-800 text-white py-3 rounded-xl font-semibold hover:bg-blue-700 disabled:opacity-60 transition-colors"
          >
            {loading ? 'Creating account…' : 'Create Account & Sign In'}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-gray-500">
          Already have an account? <Link href="/login" className="text-blue-600 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
