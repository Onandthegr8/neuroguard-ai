import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';
import { KeystrokeCapture } from '@/components/assessment/KeystrokeCapture';

export default function TypingAssessmentPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <Link href="/assessment" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-blue-700">
        <ArrowLeft className="w-4 h-4" /> Back to assessments
      </Link>
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Keystroke Assessment</h1>
        <p className="text-gray-500 text-sm mt-1">
          Passive typing analysis for early motor biomarker detection
        </p>
      </div>
      <KeystrokeCapture />
    </div>
  );
}
