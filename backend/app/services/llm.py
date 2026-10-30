"""LLM Provider abstraction supporting Groq, OpenAI-compatible APIs, and deterministic offline mock."""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

ABSTENTION_MESSAGE = "The available documentation does not contain sufficient information to answer this question."


class LLMProvider(ABC):
    """Abstract interface for LLM chat generation."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        """Generate response text from chat messages."""
        pass


class GroqLLMProvider(LLMProvider):
    """Groq API client via fast async HTTP requests."""

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self.api_key = api_key
        self.model = model
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    async def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()


class OpenAILLMProvider(LLMProvider):
    """OpenAI-compatible chat completion provider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini", api_base: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.model = model
        self.url = f"{api_base.rstrip('/')}/chat/completions"

    async def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()


class MockLLMProvider(LLMProvider):
    """Fast, deterministic, citation-aware mock LLM for offline testing and isolation."""

    async def generate(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.0,
    ) -> str:
        user_message = ""
        for m in messages:
            if m.get("role") == "user":
                user_message = m.get("content", "")

        # Extract context block and user question
        context_match = re.search(r"<context>(.*?)</context>", user_message, re.DOTALL)
        question_match = re.search(r"<question>(.*?)</question>", user_message, re.DOTALL)

        context_text = context_match.group(1).strip() if context_match else ""
        question_text = question_match.group(1).strip() if question_match else user_message

        # If context is completely empty, strictly abstain
        if not context_text or "<document" not in context_text:
            return ABSTENTION_MESSAGE

        # Parse document blocks: <document title="..." location="...">...</document>
        doc_pattern = re.compile(
            r'<document[^>]*title=["\'](.*?)["\'][^>]*location=["\'](.*?)["\'][^>]*>(.*?)</document>',
            re.DOTALL,
        )
        doc_matches = doc_pattern.findall(context_text)

        if not doc_matches:
            return ABSTENTION_MESSAGE

        # Extract question keywords (ignore common stop words and generic query terms)
        stopwords = {
            "what", "is", "are", "the", "a", "an", "and", "or", "how", "to", "in", "of", "for", "with",
            "on", "at", "by", "can", "does", "do", "see", "print", "dump", "regarding", "about", "who",
            "all", "our", "their", "employee", "company", "corporate", "document", "file", "policy", "procedure"
        }

        def _stem(word: str) -> str:
            w = word.lower()
            for suffix in ("ment", "ing", "ed", "es", "s"):
                if w.endswith(suffix) and len(w) > len(suffix) + 2:
                    return w[:-len(suffix)]
            return w

        q_tokens = [w for w in re.findall(r"\b\w+\b", question_text.lower()) if w not in stopwords and len(w) > 2]
        q_stem_tokens = [_stem(w) for w in q_tokens]

        if not q_tokens:
            return ABSTENTION_MESSAGE

        matched_sentences: List[tuple[int, float, str, str, str]] = []  # (overlap_count, ratio, title, location, sentence)

        for title, location, text in doc_matches:
            clean_text = text.strip()
            sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", clean_text) if s.strip()]
            for s in sentences:
                s_lower = s.lower()
                # Filter out sentences that look like injected instructions
                if "ignore previous" in s_lower or "ignore all instructions" in s_lower or "system prompt" in s_lower or "system override" in s_lower:
                    continue

                s_raw_tokens = set(re.findall(r"\b\w+\b", s_lower))
                s_stem_tokens = {_stem(w) for w in s_raw_tokens}

                exact_overlap = set(q_tokens).intersection(s_raw_tokens)
                stem_overlap = set(q_stem_tokens).intersection(s_stem_tokens)
                overlap_count = max(len(exact_overlap), len(stem_overlap))
                overlap_ratio = overlap_count / len(q_tokens)

                # Require meaningful factual overlap (at least 2 key terms or >= 40% of question keywords)
                if overlap_count >= 2 or (overlap_count >= 1 and overlap_ratio >= 0.4):
                    matched_sentences.append((overlap_count, overlap_ratio, title, location, s))

        if not matched_sentences:
            return ABSTENTION_MESSAGE

        # Select sentence with highest keyword overlap
        matched_sentences.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, _, title, location, best_sentence = matched_sentences[0]

        answer = f"Based on internal documentation: {best_sentence}. [Doc: {title}, {location}]"
        return answer


def get_llm_provider() -> LLMProvider:
    """Dependency / factory returning active LLM provider based on settings."""
    settings = get_settings()

    if settings.ENVIRONMENT == "test" or settings.LLM_PROVIDER == "mock":
        return MockLLMProvider()

    if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
        return GroqLLMProvider(api_key=settings.GROQ_API_KEY, model=settings.LLM_MODEL)

    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        return OpenAILLMProvider(
            api_key=settings.OPENAI_API_KEY,
            model=settings.LLM_MODEL,
            api_base=settings.OPENAI_API_BASE,
        )

    # Fallback to MockLLMProvider if no valid API key is present in development
    logger.warning("No LLM API key configured for provider '%s'. Falling back to MockLLMProvider.", settings.LLM_PROVIDER)
    return MockLLMProvider()
