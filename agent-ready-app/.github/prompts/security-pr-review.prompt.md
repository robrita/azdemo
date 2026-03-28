---
description: "Perform a rigorous security review of the codebase detecting leaked secrets, insecure patterns, and OWASP-aligned vulnerabilities"
agent: "agent"
---

# Security PR Review Prompt

## Purpose

Perform a rigorous security review of the codebase (or changed files) before PR submission. Detect leaked secrets, insecure patterns, and OWASP-aligned vulnerabilities. Produce a clear, evidence-based risk report with concrete fixes and confidence levels.

---

## Instructions

You are performing a pre-PR security and vulnerability review. Follow this process strictly.

### 1. Define Review Scope First

Identify what is being reviewed:

1. **PR-only scan** (preferred): files changed in this branch/session
2. **Full codebase scan**: entire repository

If scope is unclear, ask before proceeding.

### 2. Run Security Checks in Layers

Perform checks in this order. Do not skip layers.

#### Layer A — Secrets & Sensitive Data Exposure

Look for exposed or hard-coded sensitive data, including:

- API keys, tokens, passwords, connection strings, private keys
- Credentials in test fixtures, examples, docs, scripts, CI files, logs
- Sensitive values in `local.settings.json`, `.env*`, YAML, JSON, shell scripts
- Accidentally committed secrets that look “dummy” but are valid formats

For every finding, include:

- file path
- evidence snippet (minimal, redacted)
- why it is risky
- exact remediation

#### Layer B — OWASP-Oriented Code Review (ASVS/Top-10 style)

Review code for patterns related to:

1. **Broken Access Control** (authorization gaps, missing ownership checks)
2. **Cryptographic Failures** (weak hashing, plaintext secrets, insecure randomness)
3. **Injection** (SQL/NoSQL/command/template injection; unsafe string interpolation)
4. **Insecure Design** (missing threat checks, unsafe defaults)
5. **Security Misconfiguration** (debug mode, permissive CORS, missing secure headers)
6. **Vulnerable/Outdated Components** (risky dependencies, known CVEs)
7. **Identification & Authentication Failures** (weak session/token handling)
8. **Software/Data Integrity Failures** (unsafe deserialization, untrusted updates)
9. **Logging & Monitoring Failures** (missing audit trails, secrets in logs)
10. **SSRF and external request abuse** (unvalidated outbound URL fetches)

Map each finding to the closest OWASP category.

#### Layer C — Dependency & Supply Chain Hygiene

Review dependency manifests and lock/pin strategy.

- Confirm exact pinning policy is followed where required by this repo
- Flag unpinned or overly broad versions if policy prohibits them
- Flag vulnerable packages if known in provided tool output/context

Do not invent CVE IDs. Only report CVEs if provided by scanner/tool output.

#### Layer D — API/Data Handling Risks

Check for:

- Missing input validation or schema validation
- Unsafe error handling leaking internals
- Overly verbose responses exposing sensitive internals
- PII/secrets returned in API payloads or logs

### 3. Evidence Rules (No Hallucination)

You MUST NOT:

- invent files, endpoints, classes, CVEs, or vulnerabilities
- report “likely vulnerable” without evidence and rationale

You MUST:

- cite exact file paths for findings
- include a short evidence excerpt (redact secrets)
- label assumptions explicitly as `[INFERENCE: ...]`
- distinguish verified findings vs. hypotheses

### 4. Severity & Triage

Assign each verified finding:

- **Severity**: Critical / High / Medium / Low
- **Confidence**: High / Medium / Low
- **Exploitability**: Easy / Moderate / Hard
- **PR Blocker**: Yes/No

Use conservative judgment. If uncertain, lower confidence and ask for clarification.

### 5. Remediation Requirements

For each finding, provide:

1. immediate fix (minimal safe patch)
2. hardening follow-up (defense-in-depth)
3. validation step (how to verify fix)

Avoid generic advice; keep actions specific to the observed code.

### 6. Output Format

Use this exact structure:

#### A. Scope & Method

- Scan scope (PR-only or full)
- What was reviewed (files/areas)
- Which checks were performed

#### B. Security Findings

For each issue:

```
ID: SEC-###
Title:
Category (OWASP):
Severity:
Confidence:
Exploitability:
PR Blocker:
Location(s):
Evidence:
Risk Explanation:
Immediate Fix:
Hardening Follow-up:
Validation:
```

#### C. Secret Exposure Summary

- Any confirmed leaked secrets: Yes/No
- If Yes: list impacted files and required rotation/revocation actions

#### D. Dependency Risk Summary

- Pinning policy compliance: Pass/Fail
- Vulnerability evidence from tools: list only verified results

#### E. Final PR Security Verdict

Choose one:

- **PASS** — no blocker findings
- **PASS WITH RISKS** — non-blocker findings exist
- **BLOCK** — blocker findings must be fixed before PR

Include:

- blocker count
- non-blocker count
- top 3 remediation priorities

### 7. Mandatory Stop Conditions

Stop and ask clarifying questions if:

- scope (PR-only vs full scan) is not defined
- a suspected secret cannot be confidently classified
- a claim would require missing runtime/config context

---

## Anti-Patterns to Avoid

| Anti-Pattern | Correct Behavior |
|--------------|------------------|
| “This might be vulnerable” with no evidence | Provide file-based evidence and rationale, or mark as hypothesis. |
| Reporting fake CVEs from memory | Only cite CVEs from scanner/tool output. |
| Printing full secrets in output | Redact values and provide secure handling guidance. |
| Treating all findings equally | Triage by severity, confidence, and exploitability. |
| Blocking PR on uncertain hypotheses | Ask clarification or mark non-blocking with low confidence. |

---

## Activation Phrase

When invoked, begin your response with:

> "Running a pre-PR security review. I will scan for secret exposure, OWASP-aligned risks, and dependency vulnerabilities, then return a triaged security verdict with required fixes."

Then follow the output format exactly.
