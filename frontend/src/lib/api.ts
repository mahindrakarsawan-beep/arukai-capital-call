/**
 * Arukai Capital Call — API client.
 * All authenticated requests pull JWT from cookie header (server-side) or
 * the Authorization header set via the auth cookie on the client.
 * Base URL from NEXT_PUBLIC_API_URL env var.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export type DocType =
  | "capital_call_notice"
  | "subscription_agreement"
  | "side_letter"
  | "k1"
  | "wire_instructions"
  | "other";

export type DocumentStatus =
  | "pending_classification"
  | "pending_review"
  | "approved"
  | "rejected";

export interface DocumentSummary {
  id: string;
  filename: string;
  doc_type: DocType | null;
  uploaded_at: string;
  status: DocumentStatus;
  confidence: number | null;
}

export interface Classification {
  doc_type: DocType;
  confidence: number;
  key_indicators: string[];
  model_version?: string;
}

export interface DocumentDetail extends DocumentSummary {
  uploaded_by: string;
  classification: Classification | null;
  package_id?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  role: "admin" | "reviewer";
}

// ─────────────────────────────────────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────────────────────────────────────

function buildHeaders(token?: string): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      message = body?.detail ?? body?.message ?? message;
    } catch {
      // ignore JSON parse errors
    }
    throw new Error(message);
  }
  return res.json() as Promise<T>;
}

// ─────────────────────────────────────────────────────────────────────────────
// Auth
// ─────────────────────────────────────────────────────────────────────────────

export async function login(
  email: string,
  password: string
): Promise<LoginResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handleResponse<LoginResponse>(res);
}

export async function getMe(token: string): Promise<User> {
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: buildHeaders(token),
  });
  return handleResponse<User>(res);
}

// ─────────────────────────────────────────────────────────────────────────────
// Documents
// ─────────────────────────────────────────────────────────────────────────────

export async function listDocuments(
  token: string
): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE}/documents`, {
    headers: buildHeaders(token),
    cache: "no-store",
  });
  return handleResponse<DocumentSummary[]>(res);
}

export async function getDocument(
  id: string,
  token: string
): Promise<DocumentDetail> {
  const res = await fetch(`${API_BASE}/documents/${id}`, {
    headers: buildHeaders(token),
    cache: "no-store",
  });
  return handleResponse<DocumentDetail>(res);
}

export async function uploadDocument(
  file: File,
  token: string
): Promise<DocumentDetail> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/documents/upload`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      // Do NOT set Content-Type — browser sets it with boundary for multipart
    },
    body: form,
  });
  return handleResponse<DocumentDetail>(res);
}

// ─────────────────────────────────────────────────────────────────────────────
// Approvals
// ─────────────────────────────────────────────────────────────────────────────

export async function approveDocument(
  id: string,
  token: string,
  reason?: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/approvals/${id}`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify({ decision: "approved", note: reason ?? "" }),
  });
  return handleResponse<void>(res);
}

export async function rejectDocument(
  id: string,
  token: string,
  reason: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/approvals/${id}`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify({ decision: "rejected", note: reason }),
  });
  return handleResponse<void>(res);
}

// ─────────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────────

export function getDocumentDownloadUrl(id: string): string {
  return `${API_BASE}/documents/${id}/pdf`;
}
