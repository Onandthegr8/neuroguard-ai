'use client';

import { useState } from 'react';
import { Shield, Bell, Building2, Database, Download, CheckCircle2, XCircle, ChevronRight } from 'lucide-react';

type ConsentKey =
  | 'keystroke_collection'
  | 'sleep_data'
  | 'federated_learning'
  | 'research_use'
  | 'biometric_data';

const CONSENT_LABELS: Record<ConsentKey, { label: string; desc: string; required?: boolean }> = {
  keystroke_collection: {
    label: 'Keystroke Metadata Collection',
    desc: 'Captures timing patterns (dwell & interval) during typing — never the content of what you type.',
    required: true,
  },
  sleep_data: {
    label: 'Sleep & Wearable Data',
    desc: 'Syncs sleep stages, HRV, and nocturnal movement from your connected wearable device.',
  },
  federated_learning: {
    label: 'Federated Learning Participation',
    desc: 'Helps improve the global Parkinson\'s model using on-device training — your raw data never leaves your device.',
  },
  research_use: {
    label: 'De-identified Research Use',
    desc: 'Allows anonymized, aggregated data to be used for academic research publications.',
  },
  biometric_data: {
    label: 'Biometric Assessments',
    desc: 'Stores results from finger tap, spiral drawing, and voice assessment tasks.',
  },
};

const ALERT_PREFS = [
  { key: 'email_high_risk',    label: 'Email alerts for high-risk patients' },
  { key: 'sms_very_high',      label: 'SMS alerts for very-high risk events' },
  { key: 'weekly_digest',      label: 'Weekly summary digest' },
  { key: 'rapid_progression',  label: 'Rapid progression notifications' },
  { key: 'data_gap',           label: 'Data gap warnings (3+ day inactivity)' },
];

export default function SettingsPage() {
  const [consents, setConsents] = useState<Record<ConsentKey, boolean>>({
    keystroke_collection: true,
    sleep_data: true,
    federated_learning: false,
    research_use: false,
    biometric_data: true,
  });

  const [alertPrefs, setAlertPrefs] = useState<Record<string, boolean>>({
    email_high_risk:   true,
    sms_very_high:     true,
    weekly_digest:     true,
    rapid_progression: true,
    data_gap:          false,
  });

  const [hospital, setHospital] = useState({
    name:       'City General Hospital',
    npi:        '1234567890',
    department: 'Neurology / Movement Disorders',
  });

  const [saved, setSaved] = useState(false);

  function handleConsentToggle(key: ConsentKey) {
    if (CONSENT_LABELS[key].required) return; // cannot revoke required consents
    setConsents(prev => ({ ...prev, [key]: !prev[key] }));
  }

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="text-sm text-gray-500 mt-1">Manage your account, consents, and notification preferences.</p>
      </div>

      {/* ── Hospital Information ─────────────────────────────────────── */}
      <section className="card p-6 space-y-5">
        <div className="flex items-center gap-2 mb-1">
          <Building2 className="w-5 h-5 text-blue-700" />
          <h2 className="font-semibold text-gray-900">Hospital Information</h2>
        </div>
        {([
          { key: 'name',       label: 'Hospital Name',          placeholder: 'City General Hospital'         },
          { key: 'npi',        label: 'NPI / License Number',   placeholder: '1234567890'                    },
          { key: 'department', label: 'Department',             placeholder: 'Neurology / Movement Disorders' },
        ] as const).map(f => (
          <div key={f.key}>
            <label className="block text-sm font-medium text-gray-700 mb-1">{f.label}</label>
            <input
              className="w-full px-4 py-2.5 text-sm border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
              placeholder={f.placeholder}
              value={hospital[f.key]}
              onChange={e => setHospital(prev => ({ ...prev, [f.key]: e.target.value }))}
            />
          </div>
        ))}
      </section>

      {/* ── Consent Management ──────────────────────────────────────── */}
      <section className="card p-6 space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <Shield className="w-5 h-5 text-blue-700" />
          <h2 className="font-semibold text-gray-900">Consent Management</h2>
        </div>
        <p className="text-sm text-gray-500">
          You can withdraw non-essential consents at any time. Required consents are necessary for the core
          Parkinson&#39;s monitoring service to function.
        </p>

        <div className="divide-y divide-gray-100">
          {(Object.entries(CONSENT_LABELS) as [ConsentKey, typeof CONSENT_LABELS[ConsentKey]][]).map(
            ([key, meta]) => {
              const granted = consents[key];
              return (
                <div key={key} className="py-4 flex items-start gap-4">
                  <button
                    onClick={() => handleConsentToggle(key)}
                    className={`relative mt-0.5 flex-shrink-0 w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-blue-500
                      ${granted ? 'bg-blue-600' : 'bg-gray-200'}
                      ${meta.required ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
                    disabled={meta.required}
                    aria-label={`Toggle ${meta.label}`}
                  >
                    <span
                      className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200
                        ${granted ? 'translate-x-5' : 'translate-x-0'}`}
                    />
                  </button>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-800">{meta.label}</span>
                      {meta.required && (
                        <span className="text-xs px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded font-medium">Required</span>
                      )}
                      {granted
                        ? <CheckCircle2 className="w-4 h-4 text-green-500 ml-auto flex-shrink-0" />
                        : <XCircle    className="w-4 h-4 text-gray-300 ml-auto flex-shrink-0" />
                      }
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5 leading-relaxed">{meta.desc}</p>
                  </div>
                </div>
              );
            }
          )}
        </div>

        <div className="pt-2 border-t border-gray-100">
          <button className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
            <Download className="w-4 h-4" />
            Download full consent history (GDPR Article 7)
          </button>
        </div>
      </section>

      {/* ── Alert Preferences ───────────────────────────────────────── */}
      <section className="card p-6 space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <Bell className="w-5 h-5 text-blue-700" />
          <h2 className="font-semibold text-gray-900">Alert Preferences</h2>
        </div>
        <div className="space-y-3">
          {ALERT_PREFS.map(pref => (
            <label key={pref.key} className="flex items-center justify-between cursor-pointer group">
              <span className="text-sm text-gray-700 group-hover:text-gray-900">{pref.label}</span>
              <div
                onClick={() => setAlertPrefs(prev => ({ ...prev, [pref.key]: !prev[pref.key] }))}
                className={`relative w-11 h-6 rounded-full cursor-pointer transition-colors duration-200
                  ${alertPrefs[pref.key] ? 'bg-blue-600' : 'bg-gray-200'}`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full shadow transition-transform duration-200
                    ${alertPrefs[pref.key] ? 'translate-x-5' : 'translate-x-0'}`}
                />
              </div>
            </label>
          ))}
        </div>
      </section>

      {/* ── Data Import ─────────────────────────────────────────────── */}
      <section className="card p-6 space-y-3">
        <h2 className="font-semibold text-gray-900">Sleep Data Import</h2>
        <p className="text-sm text-gray-500">
          Have a Mi Fitness / Zepp / Samsung Health export? Upload the CSV and the importer maps the
          columns, fills the gaps, and recomputes your risk score.
        </p>
        <a href="/settings/import-sleep"
           className="inline-flex items-center gap-2 px-4 py-2.5 bg-blue-800 hover:bg-blue-700 text-white text-sm font-medium rounded-xl w-fit">
          Import sleep CSV →
        </a>
      </section>

      {/* ── Compliance & HIPAA ──────────────────────────────────────── */}
      <section className="card p-6 space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <Database className="w-5 h-5 text-blue-700" />
          <h2 className="font-semibold text-gray-900">Compliance</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {[
            { label: 'HIPAA BAA',            value: 'Active',       color: 'text-green-600 bg-green-50' },
            { label: 'Data Residency',        value: 'US East (AWS)', color: 'text-blue-600 bg-blue-50'  },
            { label: 'Encryption at Rest',    value: 'AES-256-GCM',  color: 'text-green-600 bg-green-50' },
            { label: 'FL Node Status',        value: 'Not enrolled', color: 'text-amber-600 bg-amber-50' },
          ].map(item => (
            <div key={item.label} className="flex items-center justify-between p-3 bg-gray-50 rounded-xl">
              <span className="text-sm text-gray-600">{item.label}</span>
              <span className={`text-xs font-semibold px-2 py-1 rounded-lg ${item.color}`}>{item.value}</span>
            </div>
          ))}
        </div>

        <div className="flex flex-col sm:flex-row gap-3 pt-1">
          <button className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
            <Download className="w-4 h-4" />Download BAA Template
          </button>
          <button className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
            <Download className="w-4 h-4" />Export My Data (GDPR Art. 20)
          </button>
          <button className="flex items-center gap-1.5 text-sm text-red-500 hover:underline">
            <ChevronRight className="w-4 h-4" />Request Account Deletion
          </button>
        </div>
      </section>

      {/* ── Save ────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-end gap-4 pb-6">
        {saved && (
          <div className="flex items-center gap-1.5 text-sm text-green-600 animate-fade-in">
            <CheckCircle2 className="w-4 h-4" />Settings saved
          </div>
        )}
        <button
          onClick={handleSave}
          className="px-6 py-2.5 bg-blue-800 text-white rounded-xl text-sm font-medium hover:bg-blue-700 transition-colors"
        >
          Save Changes
        </button>
      </div>
    </div>
  );
}
