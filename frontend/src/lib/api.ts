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

/** v0.2 state machine values returned by GET /packages. */
export type PackageState =
  | "submitted"
  | "intake_complete"
  | "under_review"
  | "routed_for_approval"
  | "decision_recorded"
  | "exception_surfaced";

/**
 * DocumentSummary — legacy shape for backward compatibility with
 * the /documents endpoint. Prefer PackageListOut for new code.
 */
export interface DocumentSummary {
  id: string;
  filename: string;
  doc_type: DocType | null;
  uploaded_at: string;
  status: DocumentStatus;
  confidence: number | null;
  /** v0.2: present when the list endpoint returns PackageListOut shape. */
  state?: PackageState | string;
  title?: string | null;
}

/**
 * PackageListOut — v0.2 list response shape from GET /packages.
 * Drummer adds doc_type + confidence + lead_filename + decision as
 * eagerly-loaded classification summary fields (Ticket 1).
 */
export interface PackageListOut {
  id: string;
  title: string;
  state: PackageState | string;
  version: string;
  uploaded_at: string;
  /** Eagerly-loaded from the first document's current classification (Ticket 1). */
  doc_type: DocType | null;
  confidence: number | null;
  lead_filename: string | null;
  /** Final approval decision — "approved" | "rejected" | null */
  decision: string | null;
  /**
   * 1-line AI summary computed server-side (POR-151).
   * e.g. "Capital Call · $2.5M due May 15 · 8 fields extracted · 99% confidence · 0 flags"
   * If null, client builds a fallback from doc_type + confidence.
   */
  ai_summary: string | null;
}

/** Per-field extraction result from Claude Haiku classify pipeline. */
export interface ExtractedField {
  value: string | boolean | null;
  confidence: number;
  source_text: string | null;
}

export interface Classification {
  doc_type: DocType;
  confidence: number;
  key_indicators: string[];
  /** Serialized per-field extraction — present when POR-151 backend has shipped. */
  extracted_fields?: Record<string, ExtractedField>;
  model_version?: string;
  /** Processing duration in milliseconds (POR-151). */
  duration_ms?: number;
  classification_error?: string | null;
  /** Natural-language reasoning paragraph (POR-151). */
  classification_reasoning?: string | null;
}

export interface DocumentDetail extends DocumentSummary {
  uploaded_by: string;
  classification: Classification | null;
  package_id?: string;
}

/** Nested classification + documents shape from GET /packages/{id}. */
export interface DocumentWithClassification {
  id: string;
  filename: string;
  classification: Classification | null;
}

export interface ReviewNote {
  id: string;
  body: string;
  author_id: string;
  created_at: string;
}

export interface Approval {
  id: string;
  action: "approved" | "rejected";
  note?: string;
  actor_id: string;
  created_at: string;
}

/**
 * PackageDetail — v0.2 shape from GET /packages/{id}.
 * Replaces DocumentDetail for the package detail page.
 */
export interface PackageDetail {
  id: string;
  /** Display title (may equal lead filename when not set). */
  title: string;
  /** v0.2 state machine value — use this, NOT status. */
  state: string;
  legacy_status?: string;
  /** Matches DocumentDetail.filename for breadcrumb/header usage. */
  filename: string;
  uploaded_by: string;
  uploaded_at?: string;
  created_at: string;
  updated_at: string;
  version: number;
  claimed_by_user_id?: string | null;
  claimed_at?: string | null;
  exception_reason?: string | null;
  last_moved_at?: string | null;
  documents: DocumentWithClassification[];
  review_notes: ReviewNote[];
  audit_trail: AuditEvent[];
  approval?: Approval | null;
  // POR-151 top-level AI data
  extracted_fields?: Record<string, ExtractedField> | null;
  classification_reasoning?: string | null;
  model_used?: string | null;
  classification_duration_ms?: number | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface User {
  id: string;
  email: string;
  role: "admin" | "reviewer" | "approver" | "operator";
}

// ─────────────────────────────────────────────────────────────────────────────
// Audit
// ─────────────────────────────────────────────────────────────────────────────

export interface AuditEvent {
  id: string;
  action: string;
  /** User ID of the actor (may be absent for system events). */
  actor_id?: string;
  actor_email?: string;
  /** "USER" | "SYSTEM" — defaults to "USER" when actor_email present, else "SYSTEM". */
  actor_type?: "USER" | "SYSTEM";
  package_id?: string;
  package_title?: string;
  created_at: string;
  before_state?: Record<string, unknown> | null;
  after_state?: Record<string, unknown> | null;
}

export interface AuditFilters {
  actor_id?: string;
  action?: string;
  from_date?: string;
  to_date?: string;
  package_id?: string;
  limit?: number;
  cursor?: string;
}

export interface AuditListResponse {
  items: AuditEvent[];
  next_cursor?: string;
  total: number;
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
      const raw = body?.detail ?? body?.message;
      if (typeof raw === "string") {
        message = raw;
      } else if (Array.isArray(raw) && raw.length > 0) {
        // Pydantic validation error: detail is an array of {msg, loc, type} objects
        message = raw.map((e: { msg?: string }) => e?.msg ?? JSON.stringify(e)).join("; ");
      } else if (raw != null) {
        message = JSON.stringify(raw);
      }
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

/**
 * List packages via the v0.2 GET /packages endpoint.
 * Returns PackageListOut which includes doc_type, confidence, and state.
 * Use this instead of listDocuments() for the operations console.
 */
export async function listPackages(
  token: string
): Promise<PackageListOut[]> {
  const res = await fetch(`${API_BASE}/packages`, {
    headers: buildHeaders(token),
    cache: "no-store",
  });
  return handleResponse<PackageListOut[]>(res);
}

/**
 * @deprecated Use listPackages() which hits the v0.2 /packages endpoint.
 * Kept for backward compatibility with legacy /documents endpoint callers.
 */
export async function listDocuments(
  token: string
): Promise<DocumentSummary[]> {
  const res = await fetch(`${API_BASE}/documents`, {
    headers: buildHeaders(token),
    cache: "no-store",
  });
  return handleResponse<DocumentSummary[]>(res);
}

/**
 * @deprecated Use getPackage() which hits the v0.2 /packages/{id} endpoint.
 * Kept for backward compatibility with legacy /documents/{id} callers.
 */
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

/**
 * GET /packages/{id} — v0.2 package detail.
 * Returns PackageDetail with top-level state, documents[], and POR-151 AI data.
 */
export async function getPackage(
  id: string,
  token: string
): Promise<PackageDetail> {
  const res = await fetch(`${API_BASE}/packages/${id}`, {
    headers: buildHeaders(token),
    cache: "no-store",
  });
  return handleResponse<PackageDetail>(res);
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
// Attestation — POST /packages/{id}/attest (B1 endpoint)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /packages/{id}/attest
 * Role gate: approver only.
 * Body: { action: "approved" | "rejected", note: string }
 * Replaces old approveDocument / rejectDocument.
 */
export async function attestPackage(
  id: string,
  action: "approved" | "rejected",
  note: string,
  token: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/packages/${id}/attest`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify({ action, note }),
  });
  return handleResponse<void>(res);
}

// ─────────────────────────────────────────────────────────────────────────────
// Claim / Release — POST /packages/{id}/claim|release (B1 endpoints)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /packages/{id}/claim
 * Role gate: reviewer only. Transitions package to under_review (claimed).
 */
export async function claimPackage(
  id: string,
  token: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/packages/${id}/claim`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify({}),
  });
  return handleResponse<void>(res);
}

/**
 * POST /packages/{id}/release
 * Role gate: reviewer — only the current claimant.
 */
export async function releasePackage(
  id: string,
  token: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/packages/${id}/release`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify({}),
  });
  return handleResponse<void>(res);
}

// ─────────────────────────────────────────────────────────────────────────────
// State transitions — POST /packages/{id}/transition (B1 endpoint)
// ─────────────────────────────────────────────────────────────────────────────

/**
 * POST /packages/{id}/transition
 * Validates against §2.2 transition matrix on the backend.
 * Invalid transitions → 409 with detail "Transition {from}→{to} not permitted".
 */
export async function transitionPackage(
  id: string,
  nextState: string,
  token: string,
  reason?: string
): Promise<void> {
  const body: Record<string, string> = { next_state: nextState };
  if (reason) body.reason = reason;
  const res = await fetch(`${API_BASE}/packages/${id}/transition`, {
    method: "POST",
    headers: buildHeaders(token),
    body: JSON.stringify(body),
  });
  return handleResponse<void>(res);
}

// ─────────────────────────────────────────────────────────────────────────────
// Utilities
// ─────────────────────────────────────────────────────────────────────────────

export function getDocumentDownloadUrl(id: string): string {
  return `${API_BASE}/documents/${id}/pdf`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Audit
// ─────────────────────────────────────────────────────────────────────────────

/**
 * List global audit events with optional filters and cursor-based pagination.
 * Requires admin or approver role; backend enforces at the API layer.
 */
export async function listAuditEvents(
  token: string,
  filters?: AuditFilters
): Promise<AuditListResponse> {
  const params = new URLSearchParams();
  if (filters?.actor_id) params.set("actor_id", filters.actor_id);
  if (filters?.action) params.set("action", filters.action);
  if (filters?.from_date) params.set("from_date", filters.from_date);
  if (filters?.to_date) params.set("to_date", filters.to_date);
  if (filters?.package_id) params.set("package_id", filters.package_id);
  if (filters?.limit) params.set("limit", String(filters.limit));
  if (filters?.cursor) params.set("cursor", filters.cursor);

  const qs = params.toString();
  const res = await fetch(`${API_BASE}/audit${qs ? `?${qs}` : ""}`, {
    headers: buildHeaders(token),
    cache: "no-store",
  });
  return handleResponse<AuditListResponse>(res);
}

/**
 * Returns the streaming CSV export URL for the audit ledger.
 * Caller is responsible for appending the Authorization header or using
 * a server-side fetch; for direct <a href> download the token must be
 * passed as a query param if the backend supports it, or via a server
 * action that streams the response.
 */
export function getAuditExportUrl(filters?: Omit<AuditFilters, "limit" | "cursor">): string {
  const params = new URLSearchParams();
  if (filters?.actor_id) params.set("actor_id", filters.actor_id);
  if (filters?.action) params.set("action", filters.action);
  if (filters?.from_date) params.set("from_date", filters.from_date);
  if (filters?.to_date) params.set("to_date", filters.to_date);
  if (filters?.package_id) params.set("package_id", filters.package_id);

  const qs = params.toString();
  return `${API_BASE}/audit/export.csv${qs ? `?${qs}` : ""}`;
}
