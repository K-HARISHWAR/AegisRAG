"""Retrieval endpoints for hybrid semantic and keyword search with two-stage RBAC filtering."""

from typing import Annotated
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.retrieval import RetrievalQuery, RetrievalResponse
from app.services.embeddings import EmbeddingProvider, get_embedding_provider
from app.services.retrieval import retrieve_context
from app.services.vector_store import VectorStore, get_vector_store

router = APIRouter(prefix="/retrieval", tags=["Retrieval"])


@router.post(
    "/query",
    response_model=RetrievalResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute secure hybrid document retrieval",
    description="Performs dense vector + BM25 keyword search enforced by pre-retrieval filtering and post-retrieval PostgreSQL revalidation.",
)
async def query_documents(
    payload: RetrievalQuery,
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    vector_store: VectorStore = Depends(get_vector_store),
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
) -> RetrievalResponse:
    """Retrieve grounded passages for a query subject to server-enforced RBAC."""
    ip_address = request.client.host if request.client else None

    return await retrieve_context(
        query_params=payload,
        current_user=current_user,
        db=db,
        vector_store=vector_store,
        embedding_provider=embedding_provider,
        ip_address=ip_address,
    )
