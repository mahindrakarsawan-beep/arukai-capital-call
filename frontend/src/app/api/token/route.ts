import { NextResponse } from "next/server";
import { getToken } from "@/lib/auth";

/**
 * GET /api/token
 * Returns the JWT token from the httpOnly cookie so client components
 * can use it to make authenticated API calls (e.g., file upload).
 * Only accessible from the same origin.
 */
export async function GET() {
  const token = await getToken();
  return NextResponse.json({ token: token ?? null });
}
