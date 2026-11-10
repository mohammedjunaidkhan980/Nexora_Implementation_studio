import re
from datetime import date

from sqlalchemy.orm import Session

from model.agent import OrganizationAgent
from model.leave import LeaveStatus, OrganizationLeaveRequest
from model.organization import OrganizationMember
from model.user import User
from services.chat_memory import append_message, get_recent_messages
from services.rag import answer_query


def classify_intent(message: str, has_leave_request: bool = False) -> str:
    if has_leave_request:
        return "leave_application"

    text = message.casefold()
    if re.search(r"\b(apply|request|submit|take|book)\b.*\bleave\b", text):
        return "leave_application"
    if re.search(
        r"\b(leave (request )?status|my leave status|status of (my )?leave|"
        r"pending leave|approved leave|rejected leave|leave requests?)\b",
        text,
    ):
        return "leave_status"
    if re.search(
        r"\b(salary|pay|paycheck|pay rate|earnings|employee id|designation)\b",
        text,
    ):
        return "employee_data"
    if re.search(
        r"\b(leave balance|remaining leaves?|available leaves?|"
        r"how many leaves?|leaves? left|how much leave|my (annual )?leaves?)\b",
        text,
    ):
        return "employee_data"
    return "documents"


def _employee_answer(member: OrganizationMember | None, message: str) -> str:
    if not member or not member.employee_id:
        return "Your employee details are not set up yet. Please ask your organization admin to add them."

    text = message.casefold()
    if re.search(r"\b(salary|pay|paycheck|pay rate|earnings)\b", text):
        if member.employee_salary is None:
            return "Your salary has not been added by your organization admin yet."
        return f"Your recorded salary is {member.employee_salary}."
    if re.search(r"\b(designation)\b", text):
        return f"Your recorded designation is {member.designation or 'not set'}."
    if member.employee_leaves is None:
        return "Your available leave balance has not been added by your organization admin yet."
    return f"You have {member.employee_leaves} available leave days recorded."


def _leave_status_answer(
    db: Session, organization_id: int, user_id: int
) -> str:
    requests = (
        db.query(OrganizationLeaveRequest)
        .filter(
            OrganizationLeaveRequest.organization_id == organization_id,
            OrganizationLeaveRequest.user_id == user_id,
        )
        .order_by(OrganizationLeaveRequest.created_at.desc())
        .limit(5)
        .all()
    )
    if not requests:
        return "You have not submitted any leave requests to this organization."
    return "\n".join(
        f"Leave request #{request.id}: {request.start_date} to {request.end_date} — "
        f"{request.status.value}."
        for request in requests
    )


def _create_leave_request(
    db: Session,
    organization_id: int,
    user_id: int,
    start_date: date,
    end_date: date,
    reason: str,
) -> OrganizationLeaveRequest:
    overlap = (
        db.query(OrganizationLeaveRequest)
        .filter(
            OrganizationLeaveRequest.organization_id == organization_id,
            OrganizationLeaveRequest.user_id == user_id,
            OrganizationLeaveRequest.status.in_(
                [LeaveStatus.pending, LeaveStatus.approved]
            ),
            OrganizationLeaveRequest.start_date <= end_date,
            OrganizationLeaveRequest.end_date >= start_date,
        )
        .first()
    )
    if overlap:
        raise ValueError(
            f"Your dates overlap with existing {overlap.status.value} leave request #{overlap.id}."
        )
    leave_request = OrganizationLeaveRequest(
        organization_id=organization_id,
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
        status=LeaveStatus.pending,
    )
    db.add(leave_request)
    db.commit()
    db.refresh(leave_request)
    return leave_request


def handle_chat(
    db: Session,
    organization_id: int,
    current_user: User,
    agent: OrganizationAgent,
    message: str,
    leave_request: dict[str, str] | None = None,
) -> tuple[str, str, list[dict[str, object]], OrganizationLeaveRequest | None, list[dict[str, str]]]:
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == organization_id,
            OrganizationMember.user_id == current_user.id,
        )
        .first()
    )
    if not membership:
        raise PermissionError("Organization membership required")

    intent = classify_intent(message, has_leave_request=leave_request is not None)
    memory_text = message
    if leave_request:
        memory_text += (
            f" [Leave dates: {leave_request['start_date']} to "
            f"{leave_request['end_date']}; reason: {leave_request['reason']}]"
        )
    append_message(organization_id, current_user.id, "user", memory_text)
    recent = get_recent_messages(organization_id, current_user.id)
    conversation_history = recent[:-1]

    created_leave: OrganizationLeaveRequest | None = None
    sources: list[dict[str, object]] = []
    if intent == "employee_data":
        answer = _employee_answer(membership, message)
    elif intent == "leave_status":
        answer = _leave_status_answer(db, organization_id, current_user.id)
    elif intent == "leave_application":
        if leave_request is None:
            answer = (
                "To submit a leave request, select the start and end dates and provide "
                "a reason in the leave_request fields."
            )
        else:
            try:
                created_leave = _create_leave_request(
                    db,
                    organization_id,
                    current_user.id,
                    date.fromisoformat(leave_request["start_date"]),
                    date.fromisoformat(leave_request["end_date"]),
                    leave_request["reason"],
                )
            except ValueError as exc:
                answer = str(exc)
            else:
                answer = (
                    f"Your leave request #{created_leave.id} for "
                    f"{created_leave.start_date} to {created_leave.end_date} "
                    "has been submitted and is pending admin approval."
                )
    else:
        answer, sources = answer_query(
            organization_id,
            message,
            5,
            agent,
            conversation_history=conversation_history,
        )

    append_message(organization_id, current_user.id, "assistant", answer)
    return intent, answer, sources, created_leave, get_recent_messages(
        organization_id, current_user.id
    )
