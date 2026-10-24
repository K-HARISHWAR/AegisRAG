# AegisRAG - Evaluation Dataset & Protocol

This directory contains benchmark questions and evaluation specifications used to measure RAG retrieval accuracy, faithfulness, citation correctness, and RBAC security boundaries.

## Evaluation Categories

1. **Department Isolation Tests**:
   - Verify Engineering users cannot access HR documents (`leave_policy.pdf`, `executive_compensation_2026.xlsx`).
   - Verify HR users cannot access Engineering documents (`engineering_runbook.pdf`, `infra_secrets_master.docx`).
2. **Confidentiality / Document-Level Restriction Tests**:
   - Verify regular employees cannot view restricted files within their own department (e.g., manager-only docs).
   - Verify department managers can view restricted documents in their department.
   - Verify admins can query across all departments.
3. **Abstention on Missing Evidence**:
   - Verify questions with no grounding in any uploaded documents trigger clear abstention rather than hallucinated facts.
4. **Adversarial / Prompt Injection Resistance**:
   - Verify prompt injection attempts ("Ignore previous instructions...") do not bypass authorization boundaries or leak document contents.

## Format of `questions.jsonl`

Each JSON line contains:
- `id`: Unique identifier (e.g., `q01`)
- `question`: Natural language prompt
- `target_department`: Target document department
- `allowed_roles`: List of roles allowed to view the answer
- `allowed_departments`: List of departments allowed to view the answer
- `is_restricted`: Whether the document requires elevated/manager privileges
- `expected_source_document`: File name of ground truth source
- `expected_location`: Expected citation location (page/section/sheet)
- `expected_behavior`: One of `answer_with_citation`, `abstain_unauthorized`, `abstain_no_evidence`, `reject_prompt_injection`
