'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, Users, BarChart3, Settings, LogOut, Keyboard } from 'lucide-react';
import { signOut } from 'next-auth/react';
import { clsx } from 'clsx';

const NAV = [
  { href: '/dashboard',  icon: LayoutDashboard, label: 'Dashboard'  },
  { href: '/patients',   icon: Users,           label: 'Patients'   },
  { href: '/assessment', icon: Keyboard,        label: 'Assessment' },
  { href: '/analytics',  icon: BarChart3,        label: 'Analytics'  },
  { href: '/settings',   icon: Settings,         label: 'Settings'   },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="w-56 min-h-screen bg-white border-r border-gray-100 flex flex-col">
      {/* Logo */}
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-800 rounded-lg flex items-center justify-center text-white font-bold text-sm">N</div>
          <div>
            <p className="text-sm font-bold text-gray-900 leading-none">NeuroGuard</p>
            <p className="text-[10px] text-gray-400">Clinician Portal</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-3 space-y-0.5">
        {NAV.map(item => {
          const active = path.startsWith(item.href);
          return (
            <Link key={item.href} href={item.href}
              className={clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors',
                active ? 'bg-blue-50 text-blue-800' : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
              )}>
              <item.icon className="w-4 h-4 flex-shrink-0" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Sign out */}
      <div className="p-3 border-t border-gray-100">
        <button
          onClick={() => signOut({ callbackUrl: '/login' })}
          className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-gray-500 hover:bg-red-50 hover:text-red-600 transition-colors w-full"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </aside>
  );
}
