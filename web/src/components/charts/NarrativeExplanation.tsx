'use client';

import { TrendingUp, Shield, AlertCircle, Sparkles } from 'lucide-react';

export interface Narrative {
  headline:   string;
  drivers:    string[];
  protective: string[];
  callouts:   string[];
  paragraph:  string;
}

interface Props {
  data:    Narrative | null | undefined;
  loading: boolean;
}

/**
 * Plain-English explanation of the latest risk score.
 *
 * Composes (a) the structured prose paragraph from the backend with
 * (b) labelled chips for the drivers / protective factors / callouts.
 */
export function NarrativeExplanation({ data, loading }: Props) {
  if (loading) {
    return (
      <div className="space-y-3">
        <div className="h-4 bg-gray-100 animate-pulse rounded w-3/4" />
        <div className="h-4 bg-gray-100 animate-pulse rounded w-full" />
        <div className="h-4 bg-gray-100 animate-pulse rounded w-5/6" />
      </div>
    );
  }
  if (!data) {
    return <p className="text-sm text-gray-400">No explanation available yet.</p>;
  }

  return (
    <div className="space-y-4">
      {/* Headline */}
      <div className="flex items-center gap-2 text-sm font-semibold text-blue-700">
        <Sparkles className="w-4 h-4" />
        AI explanation
      </div>

      {/* Paragraph — verbatim from the backend */}
      <p className="text-sm text-gray-700 leading-relaxed">{data.paragraph}</p>

      {/* Drivers / Protective factors as chip lists */}
      {(data.drivers.length > 0 || data.protective.length > 0) && (
        <div className="grid sm:grid-cols-2 gap-3 pt-1">
          {data.drivers.length > 0 && (
            <div>
              <div className="flex items-center gap-1 text-xs font-semibold text-red-700 mb-2">
                <TrendingUp className="w-3.5 h-3.5" /> RAISING RISK
              </div>
              <ul className="space-y-1.5">
                {data.drivers.map((d, i) => (
                  <li key={i} className="text-xs text-gray-700 bg-red-50 border border-red-100 rounded-md px-2.5 py-1.5">
                    {d}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {data.protective.length > 0 && (
            <div>
              <div className="flex items-center gap-1 text-xs font-semibold text-green-700 mb-2">
                <Shield className="w-3.5 h-3.5" /> PROTECTIVE
              </div>
              <ul className="space-y-1.5">
                {data.protective.map((p, i) => (
                  <li key={i} className="text-xs text-gray-700 bg-green-50 border border-green-100 rounded-md px-2.5 py-1.5">
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Callouts */}
      {data.callouts.length > 0 && (
        <div className="space-y-1.5 pt-1">
          {data.callouts.map((c, i) => (
            <div key={i} className="flex items-start gap-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-2.5 py-2">
              <AlertCircle className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
              <span>{c}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
