import type { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import axios from 'axios';

const API_URL = process.env.NEXTAUTH_API_URL ?? 'http://localhost:8001/api/v1';

/** Demo users — no backend required. Remove in production. */
const DEMO_USERS: Record<string, { id: string; role: string; name: string }> = {
  'demo@neuroguard.ai:demo123': {
    id:   'demo-clinician-001',
    role: 'clinician',
    name: 'Dr. Sarah Chen',
  },
  'admin@neuroguard.ai:admin123': {
    id:   'demo-admin-001',
    role: 'hospital_admin',
    name: 'Admin User',
  },
};

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'NeuroGuard',
      credentials: {
        email:    { label: 'Email',    type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        const email    = credentials?.email?.toLowerCase().trim() ?? '';
        const password = credentials?.password ?? '';

        // ── Demo mode: accept hardcoded credentials instantly ──
        const demoKey  = `${email}:${password}`;
        const demoUser = DEMO_USERS[demoKey];
        if (demoUser) {
          return {
            id:          demoUser.id,
            email,
            name:        demoUser.name,
            role:        demoUser.role,
            accessToken: 'demo-access-token',
          };
        }

        // ── Production mode: call the backend auth service ──
        try {
          const { data } = await axios.post(`${API_URL}/auth/login`, { email, password });
          if (data.access_token) {
            return {
              id:           data.user.id,
              email:        data.user.email,
              role:         data.user.role,
              accessToken:  data.access_token,
              refreshToken: data.refresh_token,
            };
          }
        } catch {
          // Backend unavailable — only demo credentials are accepted
        }
        return null;
      },
    }),
  ],
  session: { strategy: 'jwt', maxAge: 30 * 24 * 60 * 60 },
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.accessToken  = (user as any).accessToken;
        token.refreshToken = (user as any).refreshToken;
        token.role         = (user as any).role;
      }
      return token;
    },
    async session({ session, token }) {
      (session as any).accessToken = token.accessToken;
      (session as any).role        = token.role;
      return session;
    },
  },
  pages: { signIn: '/login' },
  secret: process.env.NEXTAUTH_SECRET,
};
