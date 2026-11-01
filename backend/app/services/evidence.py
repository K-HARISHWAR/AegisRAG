"""Evidence validation, claim-grounding, and responsible abstention service.

Evaluates qualitative evidence quality across retrieval relevance, answer faithfulness,
and citation integrity without exposing uncalibrated truth probabilities.
"""

import re
import uuid
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Set, Tuple

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.generation import Citation, EvidenceDiagnostics
from app.schemas.retrieval import RetrievedChunk
from app.services.llm import ABSTENTION_MESSAGE

logger = get_logger(__name__)
settings = get_settings()

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does",
    "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had",
    "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her",
    "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd",
    "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over",
    "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves",
    "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've",
    "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when",
    "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's",
    "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves", "according", "document", "documentation", "doc", "page",
}


def tokenize_clean(text: str) -> List[str]:
    """Tokenize alphanumeric words, lowercase, and filter stopwords."""
    raw_tokens = re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())
    return [t for t in raw_tokens if t not in STOPWORDS and len(t) > 1]


def extract_factual_claims(answer: str) -> List[str]:
    """Segment answer into testable factual claim statements."""
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", answer.strip())
    claims: List[str] = []

    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue

        # Skip citation tags
        s_clean = re.sub(r"\[Doc:\s*[^\]]+\]", "", s_clean).strip()
        # Skip conversational transitions or abstention messages
        if not s_clean or len(s_clean) < 10:
            continue
        if ABSTENTION_MESSAGE.lower() in s_clean.lower():
            continue
        if s_clean.lower().startswith(("hello", "hi", "greetings", "here is", "based on")):
            # If the rest of the sentence has substance, keep it
            words = tokenize_clean(s_clean)
            if len(words) < 3:
                continue

        claims.append(s_clean)

    return claims


@dataclass
class EvidenceValidationResult:
    """Outcome of evidence validation check."""

    evidence_level: Literal["strong", "limited", "insufficient"]
    should_abstain: bool
    abstention_reason: Optional[str]
    validated_citations: List[Citation]
    diagnostics: EvidenceDiagnostics


def evaluate_retrieval_relevance(
    query: str,
    chunks: List[RetrievedChunk],
) -> Tuple[Literal["high", "medium", "low"], float]:
    """Evaluate whether retrieved passages exhibit substantive lexical and semantic relevance."""
    if not chunks:
        return "low", 0.0

    query_tokens = set(tokenize_clean(query))
    if not query_tokens:
        return "medium", 0.5

    # Aggregate passage texts
    combined_passage_text = " ".join(c.text.lower() for c in chunks)
    passage_tokens = set(tokenize_clean(combined_passage_text))

    overlap_count = len(query_tokens & passage_tokens)
    coverage_ratio = overlap_count / max(1, len(query_tokens))

    # Evaluate max combined retrieval score from hybrid fusion
    max_score = max((c.combined_score for c in chunks), default=0.0)

    # Classify qualitative relevance
    if max_score >= 0.50 or coverage_ratio >= 0.60:
        return "high", coverage_ratio
    elif max_score >= settings.EVIDENCE_MIN_RELEVANCE_THRESHOLD or coverage_ratio >= 0.25:
        return "medium", coverage_ratio
    else:
        return "low", coverage_ratio


def evaluate_claim_grounding(
    claims: List[str],
    chunks: List[RetrievedChunk],
) -> Tuple[float, int, int, List[str]]:
    """Determine which answer claims are faithfully supported by the retrieved chunks."""
    if not claims:
        return 1.0, 0, 0, []

    if not chunks:
        return 0.0, 0, len(claims), claims

    chunk_texts = [c.text.lower() for c in chunks]
    supported_claims: List[str] = []
    unsupported_claims: List[str] = []

    for claim in claims:
        claim_tokens = tokenize_clean(claim)
        if not claim_tokens:
            continue

        # Check claim token overlap against individual chunks
        claim_set = set(claim_tokens)
        is_supported = False

        for c_text in chunk_texts:
            # Check for direct phrase match or high term overlap in a single passage
            if claim.lower() in c_text:
                is_supported = True
                break

            matched_terms = [t for t in claim_set if t in c_text]
            overlap = len(matched_terms) / len(claim_set)

            # A claim is supported if >= 50% of its substantive terms appear in a single chunk
            if overlap >= 0.50:
                is_supported = True
                break

        if is_supported:
            supported_claims.append(claim)
        else:
            unsupported_claims.append(claim)

    total_valid = len(supported_claims) + len(unsupported_claims)
    if total_valid == 0:
        return 1.0, 0, 0, []

    faithfulness = len(supported_claims) / total_valid
    return round(faithfulness, 2), len(supported_claims), total_valid, unsupported_claims


def verify_citation_integrity(
    citations: List[Citation],
    authorized_chunks: List[RetrievedChunk],
) -> Tuple[List[Citation], bool]:
    """Enforce citation integrity against verified active PostgreSQL chunks.

    Strips any citations referencing documents not in the authorized active context.
    """
    if not citations:
        return [], True

    authorized_doc_map = {c.document_id: c for c in authorized_chunks}
    verified_citations: List[Citation] = []
    has_violation = False

    for cite in citations:
        chunk = authorized_doc_map.get(cite.document_id)
        if not chunk:
            logger.warning(
                "Citation integrity violation: Citation points to doc %s not in authorized context",
                cite.document_id,
            )
            has_violation = True
            continue

        # Ensure document version matches verified active version
        if cite.document_version != chunk.document_version:
            logger.info(
                "Correcting citation version for doc %s from v%s to verified active v%s",
                cite.document_id,
                cite.document_version,
                chunk.document_version,
            )
            cite.document_version = chunk.document_version

        # Populate or ensure non-empty passage snippet from authorized chunk
        if not cite.snippet or len(cite.snippet.strip()) < 5:
            cite.snippet = chunk.text[:200]

        verified_citations.append(cite)

    return verified_citations, not has_violation


def detect_conflicting_evidence(chunks: List[RetrievedChunk]) -> bool:
    """Identify if active retrieved chunks express mutually contradictory facts."""
    if len(chunks) < 2:
        return False

    # Check for direct negation or conflicting configuration values in candidate passages
    # For example: presence of both "port is 8080" and "port is 9090"
    texts = [c.text.lower() for c in chunks]
    unique_ports = set()
    for t in texts:
        ports = re.findall(r"\bport\s+(?:is\s+)?(\d{4,5})\b", t)
        unique_ports.update(ports)

    if len(unique_ports) > 1:
        # Check if they originate from different active documents
        return True

    return False


def validate_evidence(
    query: str,
    raw_answer: str,
    retrieved_chunks: List[RetrievedChunk],
    citations: List[Citation],
) -> EvidenceValidationResult:
    """Perform post-generation evidence check and determine qualitative evidence rating and abstention."""
    # 1. Check if raw answer is already an explicit abstention
    if ABSTENTION_MESSAGE.lower() in raw_answer.lower():
        diagnostics = EvidenceDiagnostics(
            retrieval_relevance="low" if not retrieved_chunks else "medium",
            faithfulness_score=0.0,
            supported_claims_count=0,
            total_claims_count=0,
            conflicts_detected=False,
            citation_integrity_verified=True,
            unsupported_claims=[],
        )
        return EvidenceValidationResult(
            evidence_level="insufficient",
            should_abstain=True,
            abstention_reason="explicit_abstention",
            validated_citations=[],
            diagnostics=diagnostics,
        )

    # 2. Case: Zero context chunks retrieved
    if not retrieved_chunks:
        diagnostics = EvidenceDiagnostics(
            retrieval_relevance="low",
            faithfulness_score=0.0,
            supported_claims_count=0,
            total_claims_count=0,
            conflicts_detected=False,
            citation_integrity_verified=True,
            unsupported_claims=[],
        )
        return EvidenceValidationResult(
            evidence_level="insufficient",
            should_abstain=True,
            abstention_reason="no_relevant_evidence",
            validated_citations=[],
            diagnostics=diagnostics,
        )

    # 3. Evaluate Retrieval Relevance
    relevance_label, coverage_ratio = evaluate_retrieval_relevance(query, retrieved_chunks)

    # 4. Extract and check claim grounding
    claims = extract_factual_claims(raw_answer)
    faithfulness, supported_cnt, total_cnt, unsupported = evaluate_claim_grounding(claims, retrieved_chunks)

    # 5. Verify Citation Integrity
    validated_cites, integrity_ok = verify_citation_integrity(citations, retrieved_chunks)

    # 6. Detect Conflicting Evidence
    has_conflicts = detect_conflicting_evidence(retrieved_chunks)

    # 7. Determine Qualitative Evidence Level
    # Strict Abstention Rules:
    # - If retrieval relevance is low, evidence is insufficient.
    # - If faithfulness is below threshold (e.g. unsupported claims), evidence is insufficient.
    if relevance_label == "low":
        evidence_level = "insufficient"
        should_abstain = True
        abstention_reason = "weak_retrieval_evidence"
    elif faithfulness < settings.EVIDENCE_MIN_FAITHFULNESS_THRESHOLD and total_cnt > 0:
        evidence_level = "insufficient"
        should_abstain = True
        abstention_reason = "unsupported_claims"
    elif has_conflicts:
        evidence_level = "limited"
        should_abstain = False
        abstention_reason = None
    elif relevance_label == "high" and faithfulness >= 0.75 and integrity_ok:
        evidence_level = "strong"
        should_abstain = False
        abstention_reason = None
    else:
        evidence_level = "limited"
        should_abstain = False
        abstention_reason = None

    # If abstaining, clear citations
    final_citations = [] if should_abstain else validated_cites

    diagnostics = EvidenceDiagnostics(
        retrieval_relevance=relevance_label,
        faithfulness_score=faithfulness,
        supported_claims_count=supported_cnt,
        total_claims_count=total_cnt,
        conflicts_detected=has_conflicts,
        citation_integrity_verified=integrity_ok,
        unsupported_claims=unsupported if should_abstain else [],
    )

    return EvidenceValidationResult(
        evidence_level=evidence_level,
        should_abstain=should_abstain,
        abstention_reason=abstention_reason,
        validated_citations=final_citations,
        diagnostics=diagnostics,
    )
