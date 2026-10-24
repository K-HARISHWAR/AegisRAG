# AegisRAG - Threat Model & Security Checklist

## 1. System Assets & Sensitivity

- **Document Source Files**: High confidentiality (may contain HR records, internal passwords, financial summaries).
- **Extracted Text Chunks & Embeddings**: High confidentiality.
- **User Credentials & Auth Tokens**: Critical confidentiality and integrity.
- **Audit Logs**: High integrity (needed for compliance and forensics).
- **LLM Credentials / API Keys**: High confidentiality (cost and security impact if compromised).

---

## 2. Threat Actors & Scenarios

| Threat Actor | Motivation / Capability | Attack Scenario |
| :--- | :--- | :--- |
| **External Attacker** | Unauthenticated access | Attacking public endpoints, sniffing unencrypted traffic, brute-forcing auth |
| **Curious Employee** | Horizontal privilege escalation | Engineering employee querying HR salary data or restricted engineering docs |
| **Malicious Insider** | Tampering / Exfiltration | Modifying client-side requests (tampering with role/department headers) |
| **Prompt Injector** | Indirect prompt injection | Embedding malicious instructions in uploaded documents to hijack LLM behavior |

---

## 3. STRIDE Threat Analysis & Mitigations

### 3.1 Spoofing (Identity)
- **Threat**: Attacker sends requests pretending to be an admin or another employee.
- **Mitigation**:
  - JWT tokens signed with strong server-side secret (`HS256` or `RS256`), with expiration (`exp`), issuer (`iss`), and subject (`sub`).
  - User identity and current active status verified against PostgreSQL for each request.

### 3.2 Tampering (Data Integrity)
- **Threat**: User alters document content or injects modified role claims in HTTP body.
- **Mitigation**:
  - Role and department from request bodies are ignored for authorization.
  - Document uploads compute SHA-256 checksums to verify integrity.
  - Database schema enforces foreign keys and uniqueness constraints.

### 3.3 Repudiation (Accountability)
- **Threat**: User denies performing an unauthorized document access or administrative action.
- **Mitigation**:
  - Structured audit trail recorded in `AuditEvent` table for uploads, grant modifications, document deletions, and RAG queries.
  - Request IDs propagated through headers and structured logs.

### 3.4 Information Disclosure (Confidentiality)
- **Threat**: Candidate chunks from restricted documents leak into LLM prompts or citations.
- **Mitigation**:
  - Dual-layer authorization: Pre-retrieval filtering in ChromaDB + post-retrieval revalidation against PostgreSQL.
  - Generic error messages returned to clients; full stack traces stored only in server logs.
  - Upload storage directories are not served as static web assets.

### 3.5 Denial of Service (Availability)
- **Threat**: User uploads huge files (zip bombs, massive PDFs) or floods query endpoints to exhaust LLM budget.
- **Mitigation**:
  - Hard 20 MB file size limit enforced at request stream inspection.
  - Request timeouts on extraction, embedding, and LLM calls.
  - Bounded top-k retrieval and token limits on LLM context windows.

### 3.6 Elevation of Privilege (Authorization)
- **Threat**: Employee accesses manager endpoints or attempts direct document retrieval by guessing UUIDs.
- **Mitigation**:
  - Centralized, testable authorization policies (`can_read_document`, `can_upload_document`, `can_manage_grants`).
  - Default-deny architecture on every endpoint.

---

## 4. Security Verification Checklist (Pre-Deployment)

- [ ] All routes require authentication except `/health/live`, `/health/ready`, and `/api/v1/auth/login`.
- [ ] No client-supplied roles, departments, or permissions are trusted.
- [ ] Direct API requests using guessed UUIDs for unauthorized documents are denied (HTTP 404 or 403).
- [ ] Vector search uses pre-computed authorized document IDs.
- [ ] Retrieved chunks are re-verified against PostgreSQL permissions before entering LLM context.
- [ ] Document content is wrapped in strict untrusted XML delimiters for LLM prompt.
- [ ] Audit logs do not store plaintext passwords, auth tokens, or private document bodies.
- [ ] No secrets or real API keys are committed to Git.
