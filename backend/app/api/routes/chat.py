"""Chat and grounded generation endpoints enforcing prompt delimitation and RBAC."""

from typing import Annotated
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.generation import ChatQueryRequest, ChatQueryResponse
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.generation import generate_answer
from app.services.llm import LLMProvider, get_llm_provider
from app.services.vector_store import VectorStore, get_vector_store

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "/query",
    response_model=ChatQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask enterprise document assistant",
    description="Submits a natural language query grounded in authorized documents with prompt injection defenses and verified citations.",
)
async def chat_query(
    payload: ChatQueryRequest,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    llm_provider: LLMProvider = Depends(get_llm_provider),
) -> ChatQueryResponse:
    """Generate grounded answer with strict prompt delimitation and exact citations."""
    ip_address = request.client.host if request.client else None

    return await generate_answer(
        request=payload,
        current_user=current_user,
        db=db,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        llm_provider=llm_provider,
        ip_address=ip_address,
    )
