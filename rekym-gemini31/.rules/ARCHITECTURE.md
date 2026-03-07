# Architecture

## Overview

Re-KYM is a GCash centralized compliance platform that automates merchant KYM re-verification through a Maker-Checker workflow. FastAPI backend with Docker Compose, React frontend, and Azure Cosmos DB.

**Tech Stack**: Python 3.12+ · FastAPI · Pydantic v2 · Azure Cosmos DB (async SDK) · React + TypeScript · TanStack Query · Vite · Tailwind CSS

## Layered Architecture

```
Request → Route → Service → Repository → Cosmos DB
```

Each business domain follows a fixed set of layers with strictly validated dependency directions:

| Layer | Responsibility | Location |
|-------|---------------|----------|
| **Routes** | HTTP handling, request/response mapping | `backend/src/routes/` |
| **Schemas** | Request/Response DTOs (Pydantic) | `backend/src/schemas/` |
| **Services** | Business logic, orchestration | `backend/src/services/` |
| **Repositories** | Data access, Cosmos DB operations | `backend/src/repositories/` |
| **Models** | Domain entities (Pydantic) | `backend/src/models/` |
| **Cosmos** | DB client singleton, container setup | `backend/src/cosmos/` |
| **Middleware** | Auth policy, rate limiting, tenant scoping | `backend/src/middleware/` |
| **Integrations** | External services (email, Google Drive, Partner DB) | `backend/src/integrations/` |
| **Lib** | Shared utilities | `backend/src/lib/` |

**Dependency rule**: Routes → Services → Repositories → Cosmos. Never skip layers.

## Cosmos DB Containers & Partition Keys

| Container | Partition Key | Purpose |
|-----------|--------------|---------|
| `cases` | `/merchantId` | Re-KYM workflow cases, collocated by merchant |
| `merchantProfiles` | `/merchantId` | Merchant profile data |
| `documents` | `/caseId` | Document submissions per case |
| `reviews` | `/caseId` | Maker review records per case |
| `decisions` | `/caseId` | Checker approval decisions per case |
| `auditEvents` | `/caseId` | Append-only audit trail with hash chain |
| `archives` | `/caseId` | Immutable 7-year retention packages |
| `communications` | `/caseId` | Notification/email delivery tracking |
| `exceptionResolutions` | `/caseId` | Exception recovery proposals |

See `.github/skills/cosmosdb-best-practices/` for Cosmos DB SDK and query optimization rules.

## Core Workflow (Maker-Checker)

1. **Case creation** — triggered by schedule or data change → state: `DUE`
2. **Merchant submission** — merchant uploads documents via secure portal → state: `DOCS_SUBMITTED`
3. **Document validation** — completeness and validity checks → state: `DOCS_VALIDATED` or loops back
4. **Maker review** — assigned Maker reviews documents, adds risk tags/remarks → state: `UNDER_REVIEW`
5. **Checker decision** — Checker approves/rejects (self-approval blocked) → state: `APPROVED` or `REJECTED`
6. **Partner DB sync** — approved status pushed to Partner Database → state: `COMPLETED`
7. **Archival** — case + evidence locked in immutable archive for 7-year retention

**Exception handling**: Checker proposes recovery → Supervisor approves → state restored.

## Key Business Rules

- **Separation of duties**: Maker cannot approve their own case
- **Tenant isolation**: Merchants can only access their own cases/documents
- **Audit trail**: Every state transition produces a hash-chained audit event
- **Rate limiting**: Per-tenant and per-user burst/sustained limits
- **MFA lockout**: 5 failed attempts → 30-minute lockout for merchant portal

## Frontend Feature Areas

| Feature | Location | Purpose |
|---------|----------|---------|
| Maker Dashboard | `frontend/src/features/maker-dashboard/` | Case queue, review workflow |
| Checker Dashboard | `frontend/src/features/checker-dashboard/` | Approval queue, decisioning |
| Partner Workflow | `frontend/src/features/partners/` | Internal partner review and confirmation workflow |
| Admin Dashboard | `frontend/src/features/admin-dashboard/` | System overview, exception management |

## Configuration

Key environment variables (see `.env.example` for full annotated list; see [CONFIG_MANAGEMENT.md](CONFIG_MANAGEMENT.md) for conventions):

| Variable | Description |
|----------|-------------|
| `COSMOS_ENDPOINT` | Cosmos DB endpoint URL |
| `COSMOS_DATABASE` | Database name (default: `rekym`) |
| `COSMOS_AUTH_MODE` | `entra` (default) or `key` (account key) |
| `COSMOS_KEY` | Account key (only when `COSMOS_AUTH_MODE=key`) |
| `GOOGLE_DRIVE_CREDENTIALS_JSON` | Google Drive service account credentials |
| `GOOGLE_DRIVE_SHARED_DRIVE_ID` | Shared Drive ID for document storage |
| `SSO_ISSUER` | Enterprise SSO token issuer |
| `SSO_AUDIENCE` | SSO audience identifier |
| `APP_ENV` | Environment (development/staging/production) |
| `CORS_ORIGINS` | Allowed CORS origins |
