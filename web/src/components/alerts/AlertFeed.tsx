'use client';

import { useState } from 'react';
import { AlertTriangle, Info, XCircle, Send } from 'lucide-react';
import { api } from '@/lib/api/client';
import type { AlertItem } from '@/types';

interface Props { alerts: AlertItem[]; patientId: string; }

const SEVERITY_STYLES = {
  info:     { icon: Info,          bg: 'bg-blue-50',   text: 'text-blue-700',  border: 'border-blue-100' },
  warning:  { icon: AlertTriangle, bg: 'bg-amber-50',  text: 'text-amber-700', border: 'border-amber-100' },
  critical: { icon: XCircle,       bg: 'bg-red-50',    text: 'text-red-700',   border: 'border-red-100' },
};

export function AlertFeed({ alerts, patientId }: Props) {
  const [message, setMessage]   = useState('');
  const [severity, setSeverity] = useState<'info'|'warning'|'critical'>('info');
  const [sending, setSending]   = useState(false);

  const sendAlert = async () => {
    if (!message.trim()) return;
    setSending(true);
    try {
      await api.alerts.create({ patient_id: patientId, message, severity, send_to_patient: true });
      setMessage('');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Send alert form */}
      <div className="bg-gray-50 rounded-xl p-4 space-y-3">
        <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Send Patient Alert</p>
        <div className="flex gap-2">
          <select
            value={severity}
            onChange={e => setSeverity(e.target.value as any)}
            className="px-3 py-2 text-sm border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
          <input
            value={message}
            onChange={e => setMessage(e.target.value)}
            placeholder="Message to patient…"
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={sendAlert}
            disabled={sending || !message.trim()}
            className="px-4 py-2 bg-blue-800 text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center gap-2 hover:bg-blue-700 transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
            {sending ? 'Sending…' : 'Send'}
          </button>
        </div>
      </div>

      {/* Alert list */}
      {alerts.length === 0 ? (
        <p className="text-sm text-gray-400 text-center py-6">No recent alerts</p>
      ) : (
        <div className="space-y-2">
          {alerts.map(alert => {
            const style = SEVERITY_STYLES[alert.severity] ?? SEVERITY_STYLES.info;
            const Icon  = style.icon;
            return (
              <div key={alert.id} className={`flex items-start gap-3 p-3 rounded-xl border ${style.bg} ${style.border}`}>
                <Icon className={`w-4 h-4 mt-0.5 flex-shrink-0 ${style.text}`} />
                <div className="flex-1 min-w-0">
                  <p className={`text-sm font-medium ${style.text}`}>{alert.title}</p>
                  <p className="text-xs text-gray-500 mt-0.5">{alert.created_at.slice(0, 10)}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
