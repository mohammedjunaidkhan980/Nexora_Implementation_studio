import os
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from model.agent import OrganizationAgent
from model.document import DocumentStatus, OrganizationDocument
from model.organization import Organization, OrganizationMember, RoleEnum
from model.user import User
from schema.document import DocumentResponse
from schema.organization import RAGQuery, RAGResponse, RAGSource
from security import get_current_user
from services.rag import RAGError, answer_query, ingest_document

router = APIRouter(prefix="/organization", tags=["Organization Documents and RAG"])

MAX_DOCUMENT_BYTES = 20 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def _require_member(
    db: Session, organization_id: int, current_user: User
) -> OrganizationMember:
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization membership required",
        )
    return membership


def _require_admin(
    db: Session, organization_id: int, current_user: User
) -> None:
    organization = (
        db.query(Organization)
        .filter(Organization.id == organization_id)
        .first()
    )
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    membership = _require_member(db, organization_id, current_user)
    if membership.role != RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin access required",
        )


def _get_agent(
    db: Session, organization_id: int, agent_id: int | None = None
) -> OrganizationAgent:
    query = db.query(OrganizationAgent).filter(
        OrganizationAgent.organization_id == organization_id
    )
    if agent_id is not None:
        query = query.filter(OrganizationAgent.id == agent_id)
    agent = query.order_by(OrganizationAgent.id).first()
    if not agent:
        if agent_id is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent not found in this organization",
            )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Configure an organization agent before processing documents",
        )
    return agent


@router.post(
    "/{organization_id}/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    organization_id: int,
    file: Annotated[UploadFile, File()],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(db, organization_id, current_user)
    filename = (file.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    extension = Path(filename).suffix.lower()
    if not filename or len(filename) > 255 or extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload a PDF, DOCX, TXT, or Markdown file with a valid filename",
        )

    content = await file.read(MAX_DOCUMENT_BYTES + 1)
    if len(content) > MAX_DOCUMENT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Document exceeds the 20 MB upload limit",
        )

    root = Path(os.getenv("UPLOAD_ROOT", "uploaded_document")).resolve()
    organization_folder = root / f"org_{organization_id}"
    stored_name = f"{uuid4().hex}{extension}"
    stored_path = organization_folder / stored_name
    try:
        organization_folder.mkdir(parents=True, exist_ok=True)
        stored_path.write_bytes(content)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document could not be stored",
        ) from exc

    document = OrganizationDocument(
        organization_id=organization_id,
        filename=filename,
        storage_path=f"org_{organization_id}/{stored_name}",
        uploaded_by=current_user.id,
        status=DocumentStatus.uploaded,
    )
    db.add(document)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        try:
            stored_path.unlink(missing_ok=True)
        except OSError as cleanup_error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Document metadata could not be saved and the uploaded file could not be removed",
            ) from cleanup_error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Document metadata could not be saved",
        ) from exc
    db.refresh(document)
    return document


@router.get(
    "/{organization_id}/documents",
    response_model=list[DocumentResponse],
)
def list_documents(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_member(db, organization_id, current_user)
    return (
        db.query(OrganizationDocument)
        .filter(OrganizationDocument.organization_id == organization_id)
        .order_by(OrganizationDocument.uploaded_at.desc())
        .all()
    )


@router.post(
    "/{organization_id}/documents/{document_id}/ingest",
    response_model=DocumentResponse,
)
def process_document(
    organization_id: int,
    document_id: int,
    agent_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(db, organization_id, current_user)
    document = (
        db.query(OrganizationDocument)
        .filter(
            OrganizationDocument.id == document_id,
            OrganizationDocument.organization_id == organization_id,
        )
        .first()
    )
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    agent = _get_agent(db, organization_id, agent_id)
    try:
        ingest_document(organization_id, document, agent)
    except RAGError as exc:
        document.status = DocumentStatus.failed
        document.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        document.status = DocumentStatus.failed
        document.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    document.status = DocumentStatus.processed
    document.error_message = None
    db.commit()
    db.refresh(document)
    return document


@router.post(
    "/{organization_id}/query",
    response_model=RAGResponse,
)
def query_documents(
    organization_id: int,
    payload: RAGQuery,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_member(db, organization_id, current_user)
    agent = _get_agent(db, organization_id, payload.agent_id)
    try:
        answer, sources = answer_query(
            organization_id,
            payload.query,
            payload.top_k,
            agent,
        )
    except RAGError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return RAGResponse(
        answer=answer,
        sources=[RAGSource(**source) for source in sources],
    )
