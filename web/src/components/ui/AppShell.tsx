'use client';

import { usePathname } from 'next/navigation';
import { Sidebar } from './Sidebar';

/** Pages that should NOT show the sidebar */
const AUTH_PATHS = ['/login', '/register', '/forgot-password'];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const isAuthPage = AUTH_PATHS.some(p => path.startsWith(p));

  if (isAuthPage) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-gray-50">
        {children}
      </main>
    </div>
  );
}
