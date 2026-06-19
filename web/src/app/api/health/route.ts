import { NextResponse } from "next/server";

/**
 * GET /api/health
 * Kubernetes readiness probe endpoint for the Next.js container.
 */
export async function GET() {
  return NextResponse.json(
    { status: "ok", service: "web-dashboard", timestamp: new Date().toISOString() },
    { status: 200 }
  );
}
