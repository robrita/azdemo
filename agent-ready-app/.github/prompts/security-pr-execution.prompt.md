---
description: "Execute a concrete, repeatable pre-PR security scan workflow detecting secret exposure and OWASP-relevant risks before merge"
agent: "agent"
---

# Security PR Execution Prompt

## Purpose

Execute a concrete, repeatable pre-PR security scan workflow for this repository. Use repository-native commands plus targeted pattern scans to detect secret exposure and OWASP-relevant risks before merge.

Companion to: [security-pr-review.prompt.md](./security-pr-review.prompt.md)

---

## Instructions

You are running a security execution checklist, not a conceptual review. Execute the steps below in order, collect evidence, and return a triaged verdict.

### 1. Confirm Scope

Choose one mode before running commands:

1. **PR-only mode** (default): scan only files changed in this branch/session
2. **Full-repo mode**: scan all tracked files

If scope is not specified, default to PR-only and state that explicitly.

### 2. Build File List

#### PR-only mode

```bash
git diff --name-only --diff-filter=ACMR origin/main...HEAD
```

If that fails (no remote/base), fallback:

```bash
git diff --name-only --diff-filter=ACMR
```

#### Full-repo mode

```bash
git ls-files
```

Exclude from manual grep scan where applicable:

- `frontend/playwright-report/`
- `frontend/test-results/`
- `htmlcov/`
- binary/media artifacts

### 3. Execute Automated Security Gates

Run these commands in this order and capture output.

1) Repository security gate:

```bash
make security
```

2) Dependency vulnerability audit (Python):

```bash
pip-audit
```

If `pip-audit` is unavailable, report as a tooling gap and continue.

3) Optional broad gate (if time allows):

```bash
make ci
```

If `make ci` fails due to non-security gates, separate those failures from security findings.

### 4. Execute Targeted Secret/Exposure Scans

Run pattern scans over the scoped file list for high-risk tokens. Use case-insensitive matching and report only real findings after verification.

Search families:

1. **Credentials/Secrets**
   - `password`, `passwd`, `pwd`, `secret`, `api[_-]?key`, `token`, `private[_-]?key`, `connection[_-]?string`
2. **Cloud/provider keys**
   - `AKIA[0-9A-Z]{16}` (AWS access key pattern)
   - `-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----`
3. **Auth headers and bearer tokens**
   - `Authorization:\s*Bearer\s+`
4. **Potentially unsafe config flags**
   - `debug\s*=\s*true`, `allow_origins\s*=\s*\["\*"\]`, `verify\s*=\s*False`
5. **Potential command execution sinks**
   - `subprocess\.(Popen|run|call)`, `os\.system\(`

Important:

- Treat regex hits as **candidates**, not confirmed issues.
- Verify context before reporting.
- Never print full secret values; redact all but minimal prefix/suffix.

### 5. OWASP-Oriented Manual Verification

For each confirmed candidate, classify against OWASP category and validate exploitability.

Minimum categories to check:

- A01 Broken Access Control
- A02 Cryptographic Failures
- A03 Injection
- A05 Security Misconfiguration
- A06 Vulnerable and Outdated Components
- A09 Security Logging and Monitoring Failures
- A10 SSRF

### 6. Dependency Policy Compliance

Validate dependency policy in this repo:

- If a dependency was changed, verify **exact pin parity** between `requirements.txt` and `pyproject.toml`.
- Flag any mismatch as a security/process risk.

### 7. Evidence and Redaction Rules

You MUST:

- provide file path and minimal evidence snippet
- redact secrets (`abc...xyz`)
- mark assumptions as `[INFERENCE: ...]`
- separate verified findings from hypotheses

You MUST NOT:

- invent CVEs, files, or vulnerabilities
- output raw secrets
- mark uncertain findings as blockers without evidence

### 8. Output Format (Required)

#### A. Execution Summary

- scope mode
- commands executed
- commands skipped + reason

#### B. Findings

Use one block per finding:

```
ID: SEC-###
Title:
Category (OWASP):
Severity: Critical|High|Medium|Low
Confidence: High|Medium|Low
Exploitability: Easy|Moderate|Hard
PR Blocker: Yes|No
Location(s):
Evidence (redacted):
Risk Explanation:
Immediate Fix:
Hardening Follow-up:
Validation Command/Step:
```

#### C. Secret Exposure Summary

- confirmed leaked secrets: Yes/No
- if Yes: impacted files + required rotation/revocation actions

#### D. Dependency Audit Summary

- `make security`: pass/fail + key results
- `pip-audit`: pass/fail/unavailable + key results
- pin parity (`requirements.txt` vs `pyproject.toml`): pass/fail

#### E. Final Verdict

- **PASS** / **PASS WITH RISKS** / **BLOCK**
- blocker count
- non-blocker count
- top 3 remediation priorities

### 9. Stop Conditions

Stop and ask clarifying questions if:

- base branch for PR-only diff is unknown and fallback is ambiguous
- a potential secret cannot be confirmed without runtime context
- tooling is missing and results would be materially incomplete

---

## Anti-Patterns to Avoid

| Anti-Pattern | Correct Behavior |
|--------------|------------------|
| Reporting raw grep matches as vulnerabilities | Validate context and classify confidence first. |
| Exposing secret values in report | Redact all sensitive values. |
| Treating missing tools as “no findings” | Report tooling gap explicitly and lower confidence. |
| Mixing quality-gate failures with security findings | Separate security vs non-security outcomes clearly. |
| Blocking PR on hypotheses | Block only on verified high-confidence risks. |

---

## Activation Phrase

When invoked, begin with:

> "Running the security execution workflow now. I will execute repository security checks, validate secret exposure candidates, and return a triaged pre-PR security verdict."
