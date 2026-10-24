# AegisRAG - Implementation Log

This log tracks architectural decisions, completed phases, verification commands, test outcomes, and git commits.

---

## Phase 0: Scope, Requirements, and Architecture
- **Date**: 2026-10-24
- **Completed Deliverables**:
  - `docs/requirements.md`: Defined problem statement, user personas (`employee`, `department_manager`, `admin`), permission matrix, supported document types (PDF, DOCX, XLSX with 20MB limit), and acceptance criteria.
  - `docs/architecture.md`: Documented modular monolith design, PostgreSQL as single source of truth, two-tier authorization filter (pre-search + post-search revalidation), data models, and trust boundaries.
  - `docs/threat-model.md`: Detailed STRIDE security analysis, privilege escalation scenarios, indirect prompt injection defense, and pre-deployment security checklist.
  - `evals/questions.jsonl` & `evals/README.md`: Created 20 synthetic evaluation questions covering allowed/denied departments, manager-only documents, abstention cases, and adversarial prompt injection attempts.
- **Outcomes**: MVP scope clearly specified; no out-of-scope microservices or complexity added.

---

## Phase 1: Tooling, Repo, and Development Workflow
- **Date**: 2026-10-24
- **Completed Deliverables**:
  - Verified local environment:
    - Git: `2.49.0.windows.1`
    - Python: `3.12.4` (using `py -3.12`)
    - Node.js: `v22.14.0`
    - npm: `10.9.2`
  - `.gitignore`: Configured to exclude `.env`, virtual environments (`.venv/`, `backend/venv/`), `node_modules/`, local upload storage, ChromaDB files, logs, and secrets.
  - `.env.example`: Added configuration template with placeholders only for backend, PostgreSQL, ChromaDB, HuggingFace embeddings, Groq/OpenAI LLM, and Vite frontend.
  - `AGENTS.md`: Established project guardrails, security rules (default-deny, untrusted document content, no hardcoded secrets), directory layout, and standard commands.
  - `README.md`: Comprehensive documentation with architecture diagram, prerequisites, local setup instructions, test commands, and implementation roadmap.
- **Verification Commands Run**:
  - `git --version` -> `git version 2.49.0.windows.1`
  - `py --version` -> `Python 3.12.4`
  - `node --version` -> `v22.14.0`
  - `npm --version` -> `10.9.2`
- **Next Step**: Initialize Git repository and create initial commit.
