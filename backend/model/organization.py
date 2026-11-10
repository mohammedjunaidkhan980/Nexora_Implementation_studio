import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database import Base

class RoleEnum(str, enum.Enum):
    owner = "owner"
    admin = "admin"
    member = "member"

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    join_pin_hash = Column(String(64), nullable=True)

    members = relationship("OrganizationMember", back_populates="organization")


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.member, nullable=False)
    employee_id = Column(String(32), nullable=True)
    employee_salary = Column(Numeric(12, 2), nullable=True)
    employee_leaves = Column(Integer, nullable=True)
    designation = Column(String(128), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
    organization = relationship("Organization", back_populates="members")

    __table_args__ = (
        Index("uq_org_member_user", "organization_id", "user_id", unique=True),
        Index("uq_org_employee_id", "organization_id", "employee_id", unique=True),
    )
