from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from model.agent import OrganizationAgent
from model.leave import LeaveStatus, OrganizationLeaveRequest
from model.organization import Organization, OrganizationMember, RoleEnum
from model.user import User
from schema.organization import (
    AgentConfigResponse,
    AgentConfigUpsert,
    AdminLeaveRequestResponse,
    EmployeeCreate,
    EmployeeResponse,
    JoinOrganizationRequest,
    OrganizationMemberDetailsResponse,
    OrganizationCreate,
    OrganizationMemberResponse,
    OrganizationPinUpdate,
    LeaveDecision,
    OrganizationAgentSummary,
)
from security import get_current_user
from services.secrets import encrypt_api_key, hash_organization_pin, verify_organization_pin

router = APIRouter(prefix="/organization", tags=["Organization"])


def _require_org_admin(
    db: Session, organization_id: int, current_user: User
) -> Organization:
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
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.role == RoleEnum.admin,
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization admin access required",
        )
    return organization


def _require_org_admin_or_member(
    db: Session, organization_id: int, current_user: User
) -> OrganizationMember:
    organization_exists = (
        db.query(Organization.id)
        .filter(Organization.id == organization_id)
        .first()
    )
    if not organization_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
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


def _employee_response(member: OrganizationMember) -> EmployeeResponse:
    return EmployeeResponse(
        id=member.id,
        user_id=member.user_id,
        organization_id=member.organization_id,
        employee_id=member.employee_id,
        full_name=member.user.full_name,
        email=member.user.email,
        employee_salary=member.employee_salary,
        employee_leaves=member.employee_leaves,
        designation=member.designation,
        role=member.role,
        joined_at=member.joined_at,
    )


def _agent_response(agent: OrganizationAgent) -> AgentConfigResponse:
    return AgentConfigResponse(
        id=agent.id,
        organization_id=agent.organization_id,
        agent_name=agent.agent_name or "Organization Assistant",
        base_url=agent.base_url,
        llm_provider=agent.llm_provider,
        llm_model=agent.llm_model,
        embedding_model=agent.embedding_model,
        api_key="********" if agent.encrypted_api_key else None,
        instructions=agent.instructions,
        updated_at=agent.updated_at,
    )


def _save_agent(
    db: Session,
    organization_id: int,
    payload: AgentConfigUpsert,
    current_user: User,
    agent: OrganizationAgent | None = None,
) -> OrganizationAgent:
    if not agent and not payload.api_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required when creating an agent configuration",
        )
    if payload.api_key:
        try:
            encrypted_api_key = encrypt_api_key(payload.api_key)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc
    elif agent:
        encrypted_api_key = agent.encrypted_api_key
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="api_key is required when creating an agent configuration",
        )

    if not agent:
        agent = OrganizationAgent(organization_id=organization_id)
        db.add(agent)
    agent.agent_name = payload.agent_name
    agent.base_url = str(payload.base_url).rstrip("/")
    agent.llm_provider = payload.llm_provider
    agent.llm_model = payload.llm_model
    agent.embedding_model = payload.embedding_model
    agent.encrypted_api_key = encrypted_api_key
    agent.instructions = payload.instructions
    agent.updated_by = current_user.id
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent configuration could not be saved",
        ) from exc
    db.refresh(agent)
    return agent


@router.post(
    "/register",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    payload: OrganizationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.query(Organization).filter(Organization.name == payload.name).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization name already exists",
        )

    org = Organization(name=payload.name, description=payload.description)
    db.add(org)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization name already exists",
        ) from exc
    org.join_pin_hash = hash_organization_pin(org.id, payload.join_pin)
    member = OrganizationMember(
        user_id=current_user.id,
        organization_id=org.id,
        role=RoleEnum.admin,
    )
    db.add(member)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Organization name already exists",
        ) from exc
    db.refresh(member)
    return member


@router.post(
    "/join",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
def join_organization(
    payload: JoinOrganizationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = (
        db.query(Organization)
        .filter(Organization.id == payload.organization_id)
        .first()
    )
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )
    if not verify_organization_pin(org.id, payload.pin, org.join_pin_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid organization PIN",
        )
    already_member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.user_id == current_user.id,
            OrganizationMember.organization_id == payload.organization_id,
        )
        .first()
    )
    if already_member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a member of this organization",
        )

    member = OrganizationMember(
        user_id=current_user.id,
        organization_id=org.id,
        role=RoleEnum.member,
    )
    db.add(member)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already a member of this organization",
        ) from exc
    db.refresh(member)
    return member


@router.put("/{organization_id}/pin", status_code=status.HTTP_204_NO_CONTENT)
def update_organization_pin(
    organization_id: int,
    payload: OrganizationPinUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    organization = _require_org_admin(db, organization_id, current_user)
    organization.join_pin_hash = hash_organization_pin(
        organization.id, payload.pin
    )
    db.commit()


@router.post(
    "/{organization_id}/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_employee(
    organization_id: int,
    payload: EmployeeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org = _require_org_admin(db, organization_id, current_user)
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found; employees must have an existing user account",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive users cannot be added as employees",
        )
    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not member:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user must join this organization before employee details can be added",
        )
    if member.employee_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee details already exist for this organization member",
        )

    db.query(Organization).filter(Organization.id == org.id).with_for_update().first()
    existing_ids = (
        db.query(OrganizationMember.employee_id)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.employee_id.isnot(None),
        )
        .all()
    )
    sequence = max(
        (
            int(match.group(1))
            for (employee_id,) in existing_ids
            if (match := re.fullmatch(r"EMP(\d+)", employee_id))
        ),
        default=1000,
    )
    member.employee_id = f"EMP{sequence + 1}"
    member.employee_salary = payload.employee_salary
    member.employee_leaves = payload.employee_leaves
    member.designation = payload.designation
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee membership conflicts with an existing organization member",
        ) from exc
    db.refresh(member)
    return _employee_response(member)


@router.get(
    "/{organization_id}/employees",
    response_model=list[EmployeeResponse],
)
def list_employees(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    members = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.employee_id.isnot(None),
        )
        .order_by(OrganizationMember.id)
        .all()
    )
    return [_employee_response(member) for member in members]


@router.get(
    "/{organization_id}/members/pending-employee-details",
    response_model=list[OrganizationMemberDetailsResponse],
)
def list_members_pending_employee_details(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    members = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.employee_id.is_(None),
            OrganizationMember.role == RoleEnum.member,
        )
        .order_by(OrganizationMember.joined_at, OrganizationMember.id)
        .all()
    )
    return [
        OrganizationMemberDetailsResponse(
            user_id=member.user.id,
            organization_id=member.organization_id,
            full_name=member.user.full_name,
            email=member.user.email,
            role=member.role,
            joined_at=member.joined_at,
        )
        for member in members
    ]


@router.get(
    "/{organization_id}/leave-requests",
    response_model=list[AdminLeaveRequestResponse],
)
def list_leave_requests(
    organization_id: int,
    leave_status: LeaveStatus = LeaveStatus.pending,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    requests = (
        db.query(OrganizationLeaveRequest, User)
        .join(User, OrganizationLeaveRequest.user_id == User.id)
        .filter(
            OrganizationLeaveRequest.organization_id == organization_id,
            OrganizationLeaveRequest.status == leave_status,
        )
        .order_by(OrganizationLeaveRequest.created_at)
        .all()
    )
    return [
        AdminLeaveRequestResponse(
            id=leave_request.id,
            organization_id=leave_request.organization_id,
            user_id=leave_request.user_id,
            start_date=leave_request.start_date,
            end_date=leave_request.end_date,
            reason=leave_request.reason,
            status=leave_request.status.value,
            reviewed_by=leave_request.reviewed_by,
            reviewed_at=leave_request.reviewed_at,
            created_at=leave_request.created_at,
            full_name=user.full_name,
            email=user.email,
        )
        for leave_request, user in requests
    ]


@router.put(
    "/{organization_id}/leave-requests/{leave_request_id}/decision",
    response_model=AdminLeaveRequestResponse,
)
def review_leave_request(
    organization_id: int,
    leave_request_id: int,
    payload: LeaveDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    leave_request = (
        db.query(OrganizationLeaveRequest)
        .filter(
            OrganizationLeaveRequest.id == leave_request_id,
            OrganizationLeaveRequest.organization_id == organization_id,
        )
        .with_for_update()
        .first()
    )
    if not leave_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Leave request not found",
        )
    if leave_request.status != LeaveStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending leave requests can be reviewed",
        )

    member = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == leave_request.user_id,
        )
        .with_for_update()
        .first()
    )
    if payload.status == "approved":
        if not member or member.employee_leaves is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee leave balance has not been configured",
            )
        requested_days = (leave_request.end_date - leave_request.start_date).days + 1
        if member.employee_leaves < requested_days:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Employee does not have enough leave days remaining",
            )
        member.employee_leaves -= requested_days
        leave_request.status = LeaveStatus.approved
    else:
        leave_request.status = LeaveStatus.rejected

    leave_request.reviewed_by = current_user.id
    leave_request.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(leave_request)
    return AdminLeaveRequestResponse(
        id=leave_request.id,
        organization_id=leave_request.organization_id,
        user_id=leave_request.user_id,
        start_date=leave_request.start_date,
        end_date=leave_request.end_date,
        reason=leave_request.reason,
        status=leave_request.status.value,
        reviewed_by=leave_request.reviewed_by,
        reviewed_at=leave_request.reviewed_at,
        created_at=leave_request.created_at,
        full_name=leave_request.user.full_name,
        email=leave_request.user.email,
    )


@router.put(
    "/{organization_id}/agent",
    response_model=AgentConfigResponse,
)
def upsert_agent(
    organization_id: int,
    payload: AgentConfigUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    agent = (
        db.query(OrganizationAgent)
        .filter(OrganizationAgent.organization_id == organization_id)
        .order_by(OrganizationAgent.id)
        .first()
    )
    agent = _save_agent(db, organization_id, payload, current_user, agent)
    return _agent_response(agent)


@router.post(
    "/{organization_id}/agents",
    response_model=AgentConfigResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_agent(
    organization_id: int,
    payload: AgentConfigUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    agent = _save_agent(db, organization_id, payload, current_user)
    return _agent_response(agent)


@router.get(
    "/{organization_id}/agents",
    response_model=list[OrganizationAgentSummary],
)
def list_organization_agents(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin_or_member(db, organization_id, current_user)
    agents = (
        db.query(OrganizationAgent)
        .filter(OrganizationAgent.organization_id == organization_id)
        .order_by(OrganizationAgent.id)
        .all()
    )
    return [
        OrganizationAgentSummary(
            id=agent.id,
            agent_name=agent.agent_name or "Organization Assistant",
            llm_provider=agent.llm_provider,
            llm_model=agent.llm_model,
        )
        for agent in agents
    ]


@router.get(
    "/{organization_id}/agents/{agent_id}",
    response_model=AgentConfigResponse,
)
def get_agent_by_id(
    organization_id: int,
    agent_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    agent = (
        db.query(OrganizationAgent)
        .filter(
            OrganizationAgent.id == agent_id,
            OrganizationAgent.organization_id == organization_id,
        )
        .first()
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return _agent_response(agent)


@router.put(
    "/{organization_id}/agents/{agent_id}",
    response_model=AgentConfigResponse,
)
def update_agent(
    organization_id: int,
    agent_id: int,
    payload: AgentConfigUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    agent = (
        db.query(OrganizationAgent)
        .filter(
            OrganizationAgent.id == agent_id,
            OrganizationAgent.organization_id == organization_id,
        )
        .first()
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    agent = _save_agent(db, organization_id, payload, current_user, agent)
    return _agent_response(agent)


@router.get(
    "/{organization_id}/agent",
    response_model=AgentConfigResponse,
)
def get_agent(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_org_admin(db, organization_id, current_user)
    agent = (
        db.query(OrganizationAgent)
        .filter(OrganizationAgent.organization_id == organization_id)
        .order_by(OrganizationAgent.id)
        .first()
    )
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent configuration not found",
        )
    return _agent_response(agent)
