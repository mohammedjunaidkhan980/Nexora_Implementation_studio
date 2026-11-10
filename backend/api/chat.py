import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import PyMongoError
from sqlalchemy.orm import Session

from database import get_db
from model.agent import OrganizationAgent
from model.organization import OrganizationMember
from model.user import User
from schema.organization import ChatRequest, ChatResponse, RAGSource
from security import get_current_user
from services.chat import handle_chat
from services.chat_memory import get_recent_messages
from services.rag import RAGError

router = APIRouter(prefix="/organization", tags=["Organization Chat"])
logger = logging.getLogger(__name__)


def _require_member(
    db: Session, organization_id: int, current_user: User
) -> None:
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
            detail="The organization admin must configure an agent before chat is available",
        )
    return agent


def _chat_response(
    organization_id: int,
    payload: ChatRequest,
    db: Session,
    current_user: User,
    agent_id: int | None = None,
):
    _require_member(db, organization_id, current_user)
    selected_agent_id = agent_id if agent_id is not None else payload.agent_id
    agent = _get_agent(db, organization_id, selected_agent_id)
    leave_request = (
        payload.leave_request.model_dump(mode="json")
        if payload.leave_request is not None
        else None
    )
    try:
        intent, answer, sources, created_leave, memory = handle_chat(
            db=db,
            organization_id=organization_id,
            current_user=current_user,
            agent=agent,
            message=payload.message,
            leave_request=leave_request,
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
    except PyMongoError as exc:
        logger.exception("MongoDB chat memory operation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB chat memory is unavailable",
        ) from exc
    return ChatResponse(
        agent_name=agent.agent_name or "Organization Assistant",
        intent=intent,
        answer=answer,
        sources=[RAGSource(**source) for source in sources],
        leave_request=created_leave,
        memory=memory,
    )


@router.post("/{organization_id}/chat", response_model=ChatResponse)
def chat_with_agent(
    organization_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _chat_response(organization_id, payload, db, current_user)


@router.post(
    "/{organization_id}/agents/{agent_id}/chat",
    response_model=ChatResponse,
)
def chat_with_selected_agent(
    organization_id: int,
    agent_id: int,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.agent_id is not None and payload.agent_id != agent_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="agent_id in the URL and request body must match",
        )
    return _chat_response(
        organization_id, payload, db, current_user, agent_id=agent_id
    )


@router.get("/{organization_id}/chat/history", response_model=list[dict[str, str]])
def chat_history(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_member(db, organization_id, current_user)
    try:
        return get_recent_messages(organization_id, current_user.id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except PyMongoError as exc:
        logger.exception("MongoDB chat history operation failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MongoDB chat memory is unavailable",
        ) from exc
