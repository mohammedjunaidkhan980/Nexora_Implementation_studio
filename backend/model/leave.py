import enum

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from database import Base


class LeaveStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class OrganizationLeaveRequest(Base):
    __tablename__ = "organization_leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    reason = Column(String(1000), nullable=False)
    status = Column(
        Enum(LeaveStatus), nullable=False, default=LeaveStatus.pending
    )
    reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_leave_org_user", "organization_id", "user_id"),
        Index("ix_leave_org_status_created", "organization_id", "status", "created_at"),
    )
