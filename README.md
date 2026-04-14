# Arukai Capital Call — Deployment 2

Cross-border capital call / subscription package review and approval workflow.

**Commissioning Core:** Arukai v1 (Deployment 2)
**Execution Boundary:** Arukai-owned (separate from Portfolio Analyzer)
**Status:** Phase 2B — in build

## What this is

A governed private system that ingests capital call notices, subscription documents, side letters, and supporting materials; classifies materials; routes review; tracks approvals; surfaces exceptions; and maintains an audit trail through decision and execution.

## Client context

Family-office-style operator. Current process is fragmented across assistants, spreadsheets, PDFs, and legal/accounting review.

## Architecture

- Backend: FastAPI + PostgreSQL
- Frontend: Next.js (web dashboard)
- AI: Anthropic (document classification, entity extraction, exception detection)
- Infra: GCP Cloud Run, Neon Postgres, GCP Cloud Storage (documents)
- Auth: JWT + RBAC (4 roles: admin/approver/reviewer/viewer)
- Retention: 7-year regulatory minimum on audit trail

## Links

- **Linear project:** Arukai Commissioning Core (Phase 2B tickets)
- **Commissioning Core artifacts:** `portfolio-analyzer/.squad/arukai-core/`
