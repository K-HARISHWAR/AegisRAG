# AegisRAG - Product Requirements & Specification

## 1. Problem Statement
Enterprise organizations store critical internal knowledge across diverse formats (PDFs, Word documents, Excel spreadsheets). Employees need fast, accurate answers to natural language questions grounded directly in internal documents. However, documents often contain confidential information (salaries, strategic plans, legal filings) that must not leak across departments or unauthorized personnel.

AegisRAG provides an enterprise RAG assistant that enforces strict, server-side Role-Based Access Control (RBAC) and explicit document-level grants before any document chunk can be retrieved or passed to a Large Language Model.

---

## 2. User Personas & Permissions Matrix

The initial release defines three primary roles across two primary departments (`Engineering` and `Human Resources`):

| Persona / Role | Department Scope | Document Upload | Manage Grants | Query Scope | Admin Actions |
| :--- | :--- | :---: | :---: | :--- | :---: |
| **Employee** | Assigned Department | No | No | Only documents permitted to their department or explicitly granted to them | None |
| **Department Manager** | Assigned Department | Yes (Own Dept) | Yes (Own Dept Docs) | All documents in their department + explicitly granted documents | Department metrics |
| **Admin** | Global (All Depts) | Yes (All Depts) | Yes (All Docs) | All documents across all departments | User & role management, global audit log |

### Explicit Permission Rules
1. **Department Isolation**: An employee in `Engineering` cannot query or view any document classified as `HR`, unless an explicit `DocumentGrant` exists for that user.
2. **Restricted Documents**: Documents marked with `confidential=true` are inaccessible to regular employees even within the same department, accessible only to department managers or explicitly named grantees.
3. **Default-Deny**: In the absence of an explicit match in the PostgreSQL authorization tables, access is denied.

---

## 3. Supported Document Types & File Handling (v1)

- **Supported Formats**:
  - **PDF (`.pdf`)**: Text extraction preserving page numbers for citation attribution. Scanned/image-only PDFs are detected and flagged (OCR is a post-MVP roadmap item).
  - **DOCX (`.docx`)**: Text extraction preserving paragraphs and headings.
  - **XLSX (`.xlsx`)**: Text extraction preserving sheet names and cell coordinates (e.g., `Sheet1!A1:D10`).
- **File Size Limit**: Maximum 20 MB per file. Requests exceeding 20 MB are rejected with HTTP 413.
- **Content Validation**: File signature / magic byte inspection to reject renamed malicious binaries.
- **Server Storage**: Server-generated UUID storage keys; the original filename is stored only as sanitized display metadata.

---

## 4. Retrieval & LLM Generation Specifications

1. **Pre-Retrieval Filtering**: Compute user-authorized document IDs from PostgreSQL and apply a filter to the ChromaDB query.
2. **Post-Retrieval Revalidation**: Re-check candidate chunk document IDs against PostgreSQL permissions before passing context to LLM.
3. **Prompt Delimitation & Defense**: Pass retrieved text wrapped in XML delimiters (`<context>...</context>`) with strict system instructions treating context as untrusted data.
4. **Citations & Abstention**:
   - Each answer must cite the source document name and location (page/paragraph/sheet).
   - If evidence is insufficient, the system must abstain by stating: *"The available documentation does not contain sufficient information to answer this question."*

---

## 5. Non-Goals for MVP (v1)

- Autonomous agent loops that call arbitrary tools or bypass authorization filters.
- Complex microservice architectures or Kubernetes clusters.
- Optical Character Recognition (OCR) for scanned PDFs (scanned documents return a descriptive warning).
- Real-time collaborative document editing.
- Multiple vector database providers concurrently.

---

## 6. Acceptance Criteria

- [ ] Unauthenticated requests to protected endpoints return HTTP 401.
- [ ] Cross-department document queries return no unauthorized passages or citations.
- [ ] An employee attempting to access another department's restricted document by guessing its UUID is denied with HTTP 404 or 403.
- [ ] Answers to valid questions cite exact source documents and pages/sheets.
- [ ] The system abstains on questions with no relevant source material.
- [ ] All sensitive configurations are loaded via environment variables; no secrets in code or logs.
