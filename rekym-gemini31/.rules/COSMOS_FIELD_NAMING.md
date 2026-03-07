# Cosmos DB Field Naming Conventions

## Rule: All field names must be camelCase

This project uses **camelCase** for all document fields stored in Cosmos DB. Pydantic models serialize with camelCase aliases (e.g. Python `merchant_id` → Cosmos DB `merchantId`).

This means indexing policies, excluded paths, and composite indexes **must** use the exact camelCase field names that appear in documents.

## Complete Field Reference

All multi-word fields across every model, organized by container. Single-word fields (`id`, `status`, `remarks`, etc.) are omitted — they don't transform.

### ReKymCase fields (`cases` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/case_id` | `/caseId` | Queries, unique key |
| `/merchant_id` | `/merchantId` | Partition key, queries |
| `/trigger_type` | `/triggerType` | Queries |
| `/current_state` | `/currentState` | Queries, composite indexes |
| `/owner_user_id` | `/ownerUserId` | Queries |
| `/due_at` | `/dueAt` | Queries, composite indexes |
| `/created_at` | `/createdAt` | Queries, composite indexes |
| `/completed_at` | `/completedAt` | Queries |
| `/latest_review` | `/latestReview` | Excluded paths (nested) |
| `/latest_decision` | `/latestDecision` | Excluded paths (nested) |
| `/communication_status` | `/communicationStatus` | Queries |

### MerchantProfile fields (`merchantProfiles` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/merchant_id` | `/merchantId` | Partition key |
| `/legal_name` | `/legalName` | Queries |
| `/contact_email` | `/contactEmail` | Queries |
| `/risk_tier` | `/riskTier` | Queries |
| `/last_rekym_completed_at` | `/lastReKymCompletedAt` | Queries |

### DocumentSubmission fields (`documents` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/submission_id` | `/submissionId` | Unique key |
| `/case_id` | `/caseId` | Partition key |
| `/merchant_id` | `/merchantId` | Queries |
| `/submitted_by_merchant_id` | `/submittedByMerchantId` | Queries |
| `/version_number` | `/versionNumber` | Queries |
| `/completeness_status` | `/completenessStatus` | Queries |
| `/storage_object_ref` | `/storageObjectRef` | Excluded paths |
| `/google_drive_revision_id` | `/googleDriveRevisionId` | Excluded paths |
| `/file_name` | `/fileName` | Queries |
| `/mime_type` | `/mimeType` | Queries |
| `/file_size_bytes` | `/fileSizeBytes` | Queries |
| `/submitted_at` | `/submittedAt` | Queries, composite indexes |
| `/validation_findings` | `/validationFindings` | Excluded paths |

### ReviewRecord fields (`reviews` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/review_id` | `/reviewId` | Unique key |
| `/case_id` | `/caseId` | Partition key |
| `/maker_user_id` | `/makerUserId` | Queries |
| `/risk_tags` | `/riskTags` | Queries |
| `/submitted_for_check_at` | `/submittedForCheckAt` | Queries |

### ApprovalDecision fields (`decisions` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/decision_id` | `/decisionId` | Unique key |
| `/case_id` | `/caseId` | Partition key |
| `/checker_user_id` | `/checkerUserId` | Queries |
| `/decided_at` | `/decidedAt` | Queries, composite indexes |

### AuditEvent fields (`auditEvents` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/audit_event_id` | `/auditEventId` | Unique key |
| `/case_id` | `/caseId` | Partition key |
| `/actor_type` | `/actorType` | Queries |
| `/actor_id` | `/actorId` | Queries |
| `/from_state` | `/fromState` | Queries |
| `/to_state` | `/toState` | Queries |
| `/occurred_at` | `/occurredAt` | Queries, composite indexes |

### ArchivePackage fields (`archives` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/archive_id` | `/archiveId` | Unique key |
| `/case_id` | `/caseId` | Partition key |
| `/locked_at` | `/lockedAt` | Queries |
| `/retention_until` | `/retentionUntil` | Queries |
| `/artifact_manifest_ref` | `/artifactManifestRef` | Excluded paths |
| `/audit_event_count` | `/auditEventCount` | Queries |
| `/document_version_count` | `/documentVersionCount` | Queries |

### CommunicationEvent fields (`communications` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/event_id` | `/eventId` | Unique key |
| `/case_id` | `/caseId` | Partition key |
| `/template_id` | `/templateId` | Queries |
| `/delivery_status` | `/deliveryStatus` | Queries |
| `/retry_count` | `/retryCount` | Queries |
| `/last_retry_at` | `/lastRetryAt` | Queries |
| `/failure_reason` | `/failureReason` | Queries |
| `/occurred_at` | `/occurredAt` | Queries |

### ExceptionResolution fields (`exceptionResolutions` container)

| Wrong (snake_case) | Correct (camelCase) | Affected Area |
|-------------------|---------------------|---------------|
| `/resolution_id` | `/resolutionId` | Unique key |
| `/case_id` | `/caseId` | Partition key |
| `/proposed_by_checker_user_id` | `/proposedByCheckerUserId` | Queries |
| `/approved_by_supervisor_user_id` | `/approvedBySupervisorUserId` | Queries |
| `/proposal_reason` | `/proposalReason` | Queries |
| `/approved_at` | `/approvedAt` | Queries |
| `/target_state` | `/targetState` | Queries |

## Reserved Word Escaping in Queries

Some field names (e.g. `key`, `value`, `type`, `status`) are **reserved words** in Cosmos DB SQL.
When referencing them in queries, use **double-quote bracket** syntax — never dot-bracket.

| Syntax | Example | Result |
|--------|---------|--------|
| `c["key"]` | `WHERE c["key"] = @key` | **Correct** |
| `c.[key]` | `WHERE c.[key] = @key` | **BadRequest — invalid** |
| `c.key` | `WHERE c.key = @key` | May work but unreliable with reserved words |

Common reserved words encountered in this project: `key`, `value`, `type`, `status`, `action`, `source`.

See [Cosmos DB reserved keywords](https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/query/keywords) for the full list.

## Indexing Policy Guard: System `id` Property

Do not add `/id/?` to `includedPaths` in Cosmos DB indexing policies.

- Cosmos DB treats `id` as a system property.
- Explicitly indexing `/id/?` is rejected with `BadRequest`.
- Error pattern: `The specified path '/id/?' could not be accepted because it overrides system property 'id'.`

Use normal included/excluded paths for application fields only (e.g., `/type/?`, `/key/?`, `/payload/*`), and keep `id` out of custom indexing paths.

## Singleton Document ID Convention

Never use a generic value like `"default"` for the `id` field on singleton configuration documents. In Cosmos DB, `id` must be unique **within a logical partition** (i.e. the same partition key value). If multiple singleton document types share the same container and partition key, a generic `id` like `"default"` will cause **silent data overwrites** on upsert.

**Rule:** Use the pattern `"{type}:{key}"` for singleton document IDs. This makes the `id` self-documenting and collision-proof.

| Pattern | Example `id` | Container | Partition Key |
|---------|-------------|-----------|---------------|
| `{type}:{key}` | `workflowConfig:partnerWorkflow` | `configuration` | `/yearCreated` |
| `{type}:{key}` | `accessControlConfig:roleAccessMatrix` | `configuration` | `/yearCreated` |

For collection-style documents (e.g. account managers, audit events), use **UUID v4** for `id` — these are unique by construction.

## Why This Matters

- **Misnamed excluded paths are silently ignored.** Cosmos DB won't error — it just indexes the field anyway, wasting RU on writes.
- **Misnamed composite indexes are non-functional.** Queries that should use a composite index will fall back to expensive cross-partition scans.
- **Misnamed unique key paths fail silently.** The constraint applies to a non-existent field, so duplicates won't be caught.

## How to Verify

1. Check the Pydantic model **aliases** (camelCase) in `backend/src/models/` — these are the source of truth for Cosmos DB field names.
2. Cross-reference every path in cosmos container setup against the model aliases.
3. SQL queries in `backend/src/repositories/` use `c.fieldName` — these must match the camelCase aliases.

## Reference

- Models: `backend/src/models/case.py`, `document.py`, `review.py`, `audit.py`, `communication.py`, `exception_resolution.py`
- Repositories: `backend/src/repositories/case.py`, `document.py`, `review.py`, `audit.py`, `communication.py`, `archive.py`, `merchant_profile.py`, `exception_resolution.py`
- Cosmos client: `backend/src/cosmos/client.py`
