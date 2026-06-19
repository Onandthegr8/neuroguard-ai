'use client';

import { useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Upload, CheckCircle2, AlertTriangle, FileText, Loader2 } from 'lucide-react';
import { apiClient } from '@/lib/api/client';
import { getSession } from 'next-auth/react';

// ── Our target schema ─────────────────────────────────────────────────────────
// Each field the backend /wearable/import endpoint accepts, with a hint about
// what a Mi Fitness / Zepp export usually calls it.
const TARGET_FIELDS = [
  { key: 'sleep_date',              label: 'Sleep date',            required: true,  hint: 'date / day / start' },
  { key: 'total_sleep_min',         label: 'Total sleep (min)',     required: false, hint: 'sleep / duration / totalSleep' },
  { key: 'deep_sleep_min',          label: 'Deep sleep (min)',      required: false, hint: 'deep / deepSleepTime' },
  { key: 'rem_duration_min',        label: 'REM sleep (min)',       required: false, hint: 'rem / REMTime' },
  { key: 'sleep_efficiency',        label: 'Sleep efficiency (0-1 or %)', required: false, hint: 'efficiency / score' },
  { key: 'rem_fragmentation_idx',   label: 'REM fragmentation (0-1)', required: false, hint: 'rare in budget exports' },
  { key: 'awakenings',              label: 'Awakenings (count)',    required: false, hint: 'wakeCount / awake' },
  { key: 'sleep_onset_min',         label: 'Time to fall asleep (min)', required: false, hint: 'onset / latency' },
  { key: 'hrv_rmssd',               label: 'HRV RMSSD (ms)',        required: false, hint: 'hrv / rmssd' },
  { key: 'resting_hr',              label: 'Resting heart rate',    required: false, hint: 'restingHR / minHR' },
] as const;

type TargetKey = typeof TARGET_FIELDS[number]['key'];

// Heuristic auto-mapping: match an incoming column name to a target field
function autoGuess(col: string): TargetKey | '' {
  const c = col.toLowerCase().replace(/[^a-z0-9]/g, '');
  if (/(date|day)/.test(c) && !/update/.test(c))       return 'sleep_date';
  if (/(deepsleep|deep)/.test(c))                       return 'deep_sleep_min';
  if (/rem/.test(c) && /time|min|duration/.test(c))     return 'rem_duration_min';
  if (/(totalsleep|sleepduration|sleeptime|asleep)/.test(c)) return 'total_sleep_min';
  if (/(efficiency|sleepscore|score)/.test(c))          return 'sleep_efficiency';
  if (/(wakecount|awaken|awake)/.test(c))               return 'awakenings';
  if (/(onset|latency|fallasleep)/.test(c))             return 'sleep_onset_min';
  if (/(hrv|rmssd)/.test(c))                            return 'hrv_rmssd';
  if (/(restinghr|minhr|heartrate|hr)/.test(c))         return 'resting_hr';
  return '';
}

// Minimal CSV parser (handles quoted fields + commas; Mi Fitness exports are simple)
function parseCSV(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n').filter(l => l.trim().length);
  if (!lines.length) return { headers: [], rows: [] };
  const parseLine = (line: string): string[] => {
    const out: string[] = [];
    let cur = '', inQ = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (inQ) {
        if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
        else if (ch === '"') inQ = false;
        else cur += ch;
      } else {
        if (ch === '"') inQ = true;
        else if (ch === ',') { out.push(cur); cur = ''; }
        else cur += ch;
      }
    }
    out.push(cur);
    return out.map(s => s.trim());
  };
  const headers = parseLine(lines[0]);
  const rows = lines.slice(1).map(parseLine);
  return { headers, rows };
}

// ── Mi Fitness aggregated-export parser ───────────────────────────────────────
// The Mi Fitness "hlth_center_aggregated_fitness_data.csv" stores everything as
// {Uid,Sid,Tag,Key,Time,Value,UpdateTime} where Value is a JSON blob. We detect
// that header, filter Key=='sleep', parse the JSON, and extract the fields our
// model uses. min_hr during sleep ≈ resting HR; sleep_score/100 ≈ efficiency.
function isMiFitnessAggregated(headers: string[]): boolean {
  const h = headers.map(x => x.toLowerCase());
  return h.includes('key') && h.includes('value') && h.includes('time') && h.includes('uid');
}

interface NormRecord {
  sleep_date:        string;
  total_sleep_min?:  number;
  deep_sleep_min?:   number;
  rem_duration_min?: number;
  sleep_efficiency?: number;
  awakenings?:       number;
  resting_hr?:       number;
}

function parseMiFitness(headers: string[], rows: string[][]): NormRecord[] {
  const ki = headers.findIndex(h => h.toLowerCase() === 'key');
  const vi = headers.findIndex(h => h.toLowerCase() === 'value');
  const ti = headers.findIndex(h => h.toLowerCase() === 'time');
  if (ki < 0 || vi < 0 || ti < 0) return [];

  const out: NormRecord[] = [];
  for (const r of rows) {
    if (r[ki] !== 'sleep') continue;
    let v: any;
    try { v = JSON.parse(r[vi]); } catch { continue; }

    const total = Number(v.total_duration);
    // Skip "watch not worn" placeholder nights (no real sleep architecture)
    if (!total || total <= 0) continue;

    const epoch = parseInt(r[ti], 10);
    if (!epoch) continue;
    const sleep_date = new Date(epoch * 1000).toISOString().slice(0, 10);

    const seg = Array.isArray(v.segment_details) && v.segment_details.length
      ? v.segment_details[0] : {};

    const rec: NormRecord = { sleep_date };
    rec.total_sleep_min  = total;
    if (v.sleep_deep_duration != null) rec.deep_sleep_min   = Number(v.sleep_deep_duration);
    if (v.sleep_rem_duration  != null && Number(v.sleep_rem_duration) > 0)
      rec.rem_duration_min = Number(v.sleep_rem_duration);
    // Mi's own 0-100 sleep score is the most realistic efficiency proxy
    if (v.sleep_score != null) rec.sleep_efficiency = Math.min(1, Number(v.sleep_score) / 100);
    const awake = seg.awake_count ?? v.awake_count;
    if (awake != null) rec.awakenings = Number(awake);
    // min HR during sleep ≈ resting HR
    const minHr = v.min_hr ?? seg.min_hr;
    if (minHr != null && Number(minHr) > 0) rec.resting_hr = Number(minHr);

    out.push(rec);
  }
  // newest first, dedupe by date (keep first / newest)
  const seen = new Set<string>();
  return out
    .sort((a, b) => b.sleep_date.localeCompare(a.sleep_date))
    .filter(r => (seen.has(r.sleep_date) ? false : (seen.add(r.sleep_date), true)));
}

type Phase = 'upload' | 'mapping' | 'mi_preview' | 'importing' | 'done' | 'error';

export default function ImportSleepPage() {
  const [phase,   setPhase]   = useState<Phase>('upload');
  const [fileName, setFileName] = useState('');
  const [headers, setHeaders] = useState<string[]>([]);
  const [rows,    setRows]    = useState<string[][]>([]);
  const [mapping, setMapping] = useState<Record<TargetKey, string>>({} as any);
  const [miRecords, setMiRecords] = useState<NormRecord[]>([]);
  const [result,  setResult]  = useState<any>(null);
  const [error,   setError]   = useState('');

  function handleFile(file: File) {
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = () => {
      const { headers, rows } = parseCSV(String(reader.result));
      if (!headers.length) { setError('Could not read any columns from this file.'); setPhase('error'); return; }

      // Auto-detect the Mi Fitness aggregated JSON format
      if (isMiFitnessAggregated(headers)) {
        const recs = parseMiFitness(headers, rows);
        if (!recs.length) {
          setError('Detected a Mi Fitness export, but found no usable sleep nights ' +
                   '(all rows were empty/“watch not worn” placeholders).');
          setPhase('error');
          return;
        }
        setMiRecords(recs);
        setPhase('mi_preview');
        return;
      }

      // Fall back to generic flat-CSV column mapping
      setHeaders(headers);
      setRows(rows);
      const guess: Record<string, string> = {};
      for (const tf of TARGET_FIELDS) {
        const match = headers.find(h => autoGuess(h) === tf.key);
        if (match) guess[tf.key] = match;
      }
      setMapping(guess as any);
      setPhase('mapping');
    };
    reader.readAsText(file);
  }

  function colIndex(colName: string) { return headers.indexOf(colName); }

  function buildRecords() {
    const di = colIndex(mapping['sleep_date']);
    return rows
      .filter(r => di >= 0 && r[di])
      .map(r => {
        const rec: any = {};
        for (const tf of TARGET_FIELDS) {
          const src = mapping[tf.key];
          if (!src) continue;
          const idx = colIndex(src);
          if (idx < 0) continue;
          let raw: any = r[idx];
          if (raw === undefined || raw === '') continue;

          if (tf.key === 'sleep_date') {
            // normalise common date formats to yyyy-mm-dd
            const d = new Date(raw);
            rec.sleep_date = isNaN(d.getTime()) ? String(raw).slice(0, 10) : d.toISOString().slice(0, 10);
          } else {
            let num = parseFloat(String(raw).replace(/[^0-9.\-]/g, ''));
            if (isNaN(num)) continue;
            // sleep_efficiency: accept "85" (%) or "0.85"
            if (tf.key === 'sleep_efficiency' && num > 1) num = num / 100;
            rec[tf.key] = num;
          }
        }
        return rec;
      })
      .filter(rec => rec.sleep_date);
  }

  async function doImport(miMode = false) {
    setPhase('importing');
    try {
      const session = await getSession();
      const token   = (session as any)?.accessToken;
      const records = miMode ? miRecords : buildRecords();
      if (!records.length) { setError('No valid rows to import.'); setPhase('error'); return; }

      if (!token || token === 'demo-access-token') {
        // demo mode — simulate
        setResult({ synced_count: records.length, skipped_count: 0, derived_count: records.length,
          warnings: ['Demo mode — not actually saved. Sign in with a real account to persist.'] });
        setPhase('done');
        return;
      }

      const resp = await apiClient.post('/wearable/import', {
        vendor: 'xiaomi', model: 'Mi Fitness import', records,
      });
      setResult(resp.data);

      // Kick a fresh risk computation so the dashboard reflects the new data
      try { await apiClient.post('/risk/compute'); } catch { /* non-fatal */ }

      setPhase('done');
    } catch (e: any) {
      setError(e?.response?.data?.detail ? JSON.stringify(e.response.data.detail) : (e?.message ?? 'Import failed'));
      setPhase('error');
    }
  }

  const dateMapped = !!mapping['sleep_date'];
  const mappedCount = Object.values(mapping).filter(Boolean).length;

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      <Link href="/assessment" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-blue-700">
        <ArrowLeft className="w-4 h-4" /> Back to assessment
      </Link>

      <div>
        <h1 className="text-2xl font-bold text-gray-900">Import Sleep Data</h1>
        <p className="text-gray-500 text-sm mt-1">
          Upload a sleep export from Mi Fitness, Zepp, Samsung Health, or any CSV. Map the columns once —
          the importer remembers nothing sensitive, only sleep metrics.
        </p>
      </div>

      {/* How to export */}
      <details className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-900">
        <summary className="font-semibold cursor-pointer">How do I get the CSV from Mi Fitness?</summary>
        <ol className="list-decimal list-inside mt-3 space-y-1.5 text-blue-800">
          <li>On a browser go to <strong>privacy.mi.com</strong> → sign in with the same Xiaomi account as Mi Fitness</li>
          <li>Choose <strong>&ldquo;Export or delete your data&rdquo;</strong> → <strong>Export</strong></li>
          <li>Select <strong>Mi Fitness / Wear / Health</strong> data, request the export</li>
          <li>Xiaomi emails you a ZIP within ~a few minutes to a day</li>
          <li>Unzip it — find the sleep CSV (often <code>sleep.csv</code> or under a <code>HEALTH/</code> folder)</li>
          <li>Upload that file below</li>
        </ol>
        <p className="mt-2 text-xs text-blue-600">
          Budget watches (incl. Redmi Watch 3 Active) often export total/deep/light sleep but
          <strong> not REM fragmentation or HRV</strong> — the importer estimates those and flags them.
        </p>
      </details>

      {/* Step 1: upload */}
      {phase === 'upload' && (
        <label className="block border-2 border-dashed border-gray-300 rounded-2xl p-10 text-center cursor-pointer hover:border-blue-400 hover:bg-blue-50/40 transition-colors">
          <input type="file" accept=".csv,text/csv" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f); }} />
          <Upload className="w-10 h-10 text-gray-400 mx-auto mb-3" />
          <p className="text-sm font-medium text-gray-700">Click to choose your sleep CSV</p>
          <p className="text-xs text-gray-400 mt-1">or drag &amp; drop — .csv only, parsed in your browser</p>
        </label>
      )}

      {/* Step 2: column mapping */}
      {phase === 'mapping' && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <FileText className="w-4 h-4" /> {fileName} · {rows.length} rows · {headers.length} columns detected
          </div>

          <div className="card p-5 space-y-3">
            <p className="text-sm font-semibold text-gray-800">Map your columns</p>
            <p className="text-xs text-gray-500">
              We pre-filled best guesses. Only <strong>Sleep date</strong> is required — map as many of the
              rest as your export has. Leave unknown ones blank.
            </p>
            <div className="divide-y divide-gray-100">
              {TARGET_FIELDS.map(tf => (
                <div key={tf.key} className="py-2.5 flex items-center gap-3">
                  <div className="flex-1 min-w-0">
                    <span className="text-sm text-gray-800">{tf.label}</span>
                    {tf.required && <span className="text-red-500 ml-1">*</span>}
                    <span className="block text-[11px] text-gray-400">usually: {tf.hint}</span>
                  </div>
                  <select
                    value={mapping[tf.key] ?? ''}
                    onChange={e => setMapping(m => ({ ...m, [tf.key]: e.target.value }))}
                    className={`text-sm border rounded-lg px-3 py-2 bg-white w-56
                      ${tf.required && !mapping[tf.key] ? 'border-red-300' : 'border-gray-200'}`}
                  >
                    <option value="">— not in my file —</option>
                    {headers.map(h => <option key={h} value={h}>{h}</option>)}
                  </select>
                </div>
              ))}
            </div>
          </div>

          {/* Preview first 3 rows of what will be sent */}
          <div className="card p-5">
            <p className="text-sm font-semibold text-gray-800 mb-2">Preview (first 3 nights)</p>
            <pre className="text-xs bg-gray-50 rounded-lg p-3 overflow-x-auto text-gray-700">
              {JSON.stringify(buildRecords().slice(0, 3), null, 2)}
            </pre>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500">{mappedCount} field(s) mapped</span>
            <div className="flex gap-2">
              <button onClick={() => setPhase('upload')}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-xl">
                Choose another file
              </button>
              <button onClick={doImport} disabled={!dateMapped}
                className="px-5 py-2 bg-blue-800 hover:bg-blue-700 disabled:opacity-50 text-white text-sm font-medium rounded-xl">
                Import {buildRecords().length} nights
              </button>
            </div>
          </div>
        </div>
      )}

      {phase === 'mi_preview' && (
        <div className="space-y-4">
          <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-sm text-green-900">
            <strong className="flex items-center gap-1.5">
              <CheckCircle2 className="w-4 h-4" /> Mi Fitness export detected
            </strong>
            <p className="mt-1 text-green-800">
              Parsed automatically — no column mapping needed. Found <strong>{miRecords.length}</strong> usable
              sleep nights (empty &ldquo;watch not worn&rdquo; nights were skipped).
            </p>
          </div>

          {(() => {
            const withRem = miRecords.filter(r => r.rem_duration_min != null).length;
            const withHr  = miRecords.filter(r => r.resting_hr != null).length;
            const span    = miRecords.length
              ? `${miRecords[miRecords.length-1].sleep_date} → ${miRecords[0].sleep_date}` : '—';
            return (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                <Stat label="Usable nights" value={miRecords.length} tone="green" />
                <Stat label="With real REM" value={withRem} tone="green" />
                <Stat label="With resting HR" value={withHr} tone="green" />
                <div className="rounded-xl p-3 bg-gray-50 text-gray-600 col-span-2 sm:col-span-1">
                  <div className="text-[11px] font-semibold">Date range</div>
                  <div className="text-xs">{span}</div>
                </div>
              </div>
            );
          })()}

          <div className="card p-5">
            <p className="text-sm font-semibold text-gray-800 mb-2">Preview (3 most recent nights)</p>
            <pre className="text-xs bg-gray-50 rounded-lg p-3 overflow-x-auto text-gray-700">
              {JSON.stringify(miRecords.slice(0, 3), null, 2)}
            </pre>
            <p className="text-xs text-amber-700 mt-2">
              REM fragmentation, HRV, sleep-onset and stage-transitions aren&apos;t in the Redmi export —
              the backend estimates those from the fields above and flags them.
            </p>
          </div>

          <div className="flex items-center justify-between">
            <button onClick={() => { setPhase('upload'); setMiRecords([]); }}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-xl">
              Choose another file
            </button>
            <button onClick={() => doImport(true)}
              className="px-5 py-2 bg-blue-800 hover:bg-blue-700 text-white text-sm font-medium rounded-xl">
              Import {miRecords.length} nights
            </button>
          </div>
        </div>
      )}

      {phase === 'importing' && (
        <div className="card p-10 text-center">
          <Loader2 className="w-10 h-10 text-blue-700 mx-auto animate-spin mb-3" />
          <p className="text-sm text-gray-600">
            Importing {miRecords.length || ''} nights & recomputing your risk score…
          </p>
        </div>
      )}

      {phase === 'done' && result && (
        <div className="card p-6 space-y-4">
          <div className="flex items-center gap-2 text-green-700">
            <CheckCircle2 className="w-6 h-6" />
            <span className="font-semibold">Import complete</span>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <Stat label="Imported"  value={result.synced_count}  tone="green" />
            <Stat label="Skipped (dupes)" value={result.skipped_count} tone="gray" />
            <Stat label="Estimated fields" value={result.derived_count} tone="amber" />
          </div>
          {result.warnings?.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-3 space-y-1">
              {result.warnings.map((w: string, i: number) => (
                <p key={i} className="text-xs text-amber-800 flex items-start gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" /> {w}
                </p>
              ))}
            </div>
          )}
          <div className="flex gap-2">
            <Link href="/dashboard" className="px-5 py-2 bg-blue-800 hover:bg-blue-700 text-white text-sm font-medium rounded-xl">
              View updated risk score
            </Link>
            <button onClick={() => { setPhase('upload'); setResult(null); }}
              className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-xl">
              Import another file
            </button>
          </div>
        </div>
      )}

      {phase === 'error' && (
        <div className="card p-6">
          <div className="flex items-center gap-2 text-red-700 mb-2">
            <AlertTriangle className="w-5 h-5" /> <span className="font-semibold">Import failed</span>
          </div>
          <p className="text-sm text-gray-600 mb-4">{error}</p>
          <button onClick={() => { setPhase('upload'); setError(''); }}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 text-sm rounded-xl">
            Try again
          </button>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone: 'green' | 'gray' | 'amber' }) {
  const c = { green: 'text-green-700 bg-green-50', gray: 'text-gray-600 bg-gray-50', amber: 'text-amber-700 bg-amber-50' }[tone];
  return (
    <div className={`rounded-xl p-3 ${c}`}>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-xs">{label}</div>
    </div>
  );
}
