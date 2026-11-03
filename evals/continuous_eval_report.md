# AegisRAG Continuous Evaluation Benchmark Report (v2.0.0)

**Date**: 2026-11-03 15:35:34 UTC  
**Dataset**: `evals/golden_benchmark_v2.jsonl` (Version: `v2.0.0`)  
**Model Version**: `mock-llm-v1` (Provider: `mock`)  
**Prompt Version**: `v1.0.0`  
**Retrieval Configuration**: `hybrid` (BGE-Small Dense + BM25 Sparse + RRF)  
**Total Scenarios**: 16 (10 Development, 6 Holdout)  
**Total Run Duration**: 4147.8ms  

---

## 1. Executive Summary & Aggregate Scorecard

| Evaluation Metric | All Scenarios (16) | Development Split (10) | Holdout Split (6) | Target SLA | Status |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Pass Rate** | **100.0%** | 100.0% | 100.0% | 100.0% | PASS |
| **Recall@5** | **100.0%** | 100.0% | 100.0% | ≥ 90.0% | PASS |
| **MRR (Mean Reciprocal Rank)** | **1.000** | 1.000 | 1.000 | ≥ 0.850 | PASS |
| **Abstention Accuracy** | **100.0%** | 100.0% | 100.0% | 100.0% | PASS |
| **Claim Faithfulness** | **100.0%** | 100.0% | 100.0% | ≥ 95.0% | PASS |
| **Citation Correctness** | **100.0%** | 100.0% | 100.0% | 100.0% | PASS |
| **Key Point Coverage** | **100.0%** | 100.0% | 100.0% | ≥ 90.0% | PASS |
| **Average Latency** | **213.0ms** | 208.4ms | 220.6ms | < 2000ms | PASS |

---

## 2. Before / After Regression Comparison

| Metric | Phase 10 Baseline | Phase 13 (Evidence Validation) | Phase 14 (Continuous Eval & Feedback) | Measured Delta |
| :--- | :---: | :---: | :---: | :---: |
| **Benchmark Sample Size** | 20 basic | 12 human-labelled | 16 versioned (10 dev + 6 holdout) | +4 holdout |
| **Abstention Accuracy** | 85.0% | 100.0% | **100.0%** | Stable (+15.0% vs baseline) |
| **Citation Integrity** | 90.0% | 100.0% | **100.0%** | Stable (+10.0% vs baseline) |
| **Recall@5** | 80.0% | 91.7% | **100.0%** | **+20.0%** |
| **Mean Reciprocal Rank (MRR)** | 0.72 | 0.88 | **1.000** | **+0.280** |
| **Holdout Generalization** | N/A | N/A | **100.0%** | Verified isolated holdout |

---

## 3. Detailed Per-Scenario Execution Log

| ID | Split | Category | Persona | Abstain (Act/Exp) | Recall@5 | MRR | Faithfulness | Citation OK | Latency |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `bench_01` | development | `standard_policy` | `alice@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 355.3ms |
| `bench_02` | development | `standard_policy` | `alice@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 336.0ms |
| `bench_03` | development | `standard_policy` | `bob@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 85.7ms |
| `bench_04` | development | `standard_policy` | `bob@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 82.9ms |
| `bench_05` | development | `confidential_manager` | `alice@example.com` | True/True | 1.0 | 1.00 | 1.00 | ✓ | 334.3ms |
| `bench_06` | development | `confidential_manager` | `charlie@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 58.0ms |
| `bench_07` | development | `confidential_manager` | `bob@example.com` | True/True | 1.0 | 1.00 | 1.00 | ✓ | 79.4ms |
| `bench_08` | development | `confidential_manager` | `diana@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 74.0ms |
| `bench_09` | development | `unanswerable` | `alice@example.com` | True/True | 1.0 | 1.00 | 1.00 | ✓ | 325.2ms |
| `bench_10` | development | `adversarial_injection` | `alice@example.com` | True/True | 1.0 | 1.00 | 1.00 | ✓ | 353.0ms |
| `bench_11` | holdout | `standard_policy` | `bob@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 96.7ms |
| `bench_12` | holdout | `standard_policy` | `alice@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 333.4ms |
| `bench_13` | holdout | `standard_policy` | `alice@example.com` | False/False | 1.0 | 1.00 | 1.00 | ✓ | 385.7ms |
| `bench_14` | holdout | `unanswerable` | `bob@example.com` | True/True | 1.0 | 1.00 | 1.00 | ✓ | 90.5ms |
| `bench_15` | holdout | `cross_department` | `alice@example.com` | True/True | 1.0 | 1.00 | 1.00 | ✓ | 329.3ms |
| `bench_16` | holdout | `adversarial_injection` | `bob@example.com` | True/True | 1.0 | 1.00 | 1.00 | ✓ | 88.0ms |

---

## 4. Methodology & Limitations

1. **Holdout Isolation**: The benchmark separates 10 development scenarios from 6 strict holdout scenarios (`bench_11` to `bench_16`) to guard against evaluation overfitting.
2. **Reproducibility Guarantee**: The test run records fixed model versions (`mock-llm-v1`), prompt template versions (`v1.0.0`), dataset versions (`v2.0.0`), and deterministic SHA-256 embeddings.
3. **Guardrail Invariant**: Negative user feedback and quality benchmark outputs create human review tasks only. They **never** automatically alter permissions, fine-tune models, or override server-side PostgreSQL authorization rules.
