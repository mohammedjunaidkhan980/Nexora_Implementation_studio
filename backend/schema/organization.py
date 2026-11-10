from decimal import Decimal
from datetime import date, datetime
import re
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator

from model.organization import RoleEnum


class OrganizationCreate(BaseModel):
    name: str
    description: str | None = None
    join_pin: str

    @field_validator("name")
    @classmethod
    def name_must_not_be_empty(cls, v):
        if not v.strip():
            raise ValueError("Organization name must not be empty")
        if len(v.strip()) < 3:
            raise ValueError("Organization name must be at least 3 characters")
        return v.strip()

    @field_validator("join_pin")
    @classmethod
    def pin_must_be_four_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}", value):
            raise ValueError("join_pin must contain exactly 4 digits")
        return value


class OrganizationResponse(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = {"from_attributes": True}


class JoinOrganizationRequest(BaseModel):
    organization_id: int
    pin: str

    @field_validator("organization_id")
    @classmethod
    def org_id_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("organization_id must be a positive integer")
        return v

    @field_validator("pin")
    @classmethod
    def pin_must_be_four_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}", value):
            raise ValueError("pin must contain exactly 4 digits")
        return value


class OrganizationPinUpdate(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def pin_must_be_four_digits(cls, value: str) -> str:
        if not re.fullmatch(r"\d{4}", value):
            raise ValueError("pin must contain exactly 4 digits")
        return value


class OrganizationMemberResponse(BaseModel):
    id: int
    user_id: int
    organization_id: int
    role: RoleEnum
    joined_at: datetime

    model_config = {"from_attributes": True}


class EmployeeCreate(BaseModel):
    user_id: int = Field(gt=0)
    employee_salary: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    employee_leaves: int = Field(ge=0)
    designation: str = Field(min_length=1, max_length=128)

    @field_validator("designation")
    @classmethod
    def designation_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("designation must not be empty")
        return value


class EmployeeResponse(BaseModel):
    id: int
    user_id: int
    organization_id: int
    employee_id: str | None
    full_name: str
    email: str
    employee_salary: Decimal | None
    employee_leaves: int | None
    designation: str | None
    role: RoleEnum
    joined_at: datetime


class OrganizationMemberDetailsResponse(BaseModel):
    user_id: int
    organization_id: int
    full_name: str
    email: str
    role: RoleEnum
    joined_at: datetime


class AgentConfigUpsert(BaseModel):
    agent_name: str = Field(default="Organization Assistant", min_length=1, max_length=128)
    base_url: AnyHttpUrl = Field(max_length=2048)
    llm_provider: str = Field(min_length=1, max_length=128)
    llm_model: str = Field(min_length=1, max_length=255)
    embedding_model: str = Field(min_length=1, max_length=255)
    api_key: str | None = Field(default=None, min_length=1)
    instructions: str = Field(default="", max_length=12000)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.scheme != "https":
            raise ValueError("base_url must use HTTPS")
        return value

    @field_validator("api_key")
    @classmethod
    def api_key_must_not_be_empty(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("api_key must not be empty")
        return value

    @field_validator("llm_provider", "llm_model", "embedding_model")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This value must not be empty")
        return value

    @field_validator("agent_name")
    @classmethod
    def agent_name_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("agent_name must not be empty")
        return value


class AgentConfigResponse(BaseModel):
    id: int
    organization_id: int
    agent_name: str
    base_url: str
    llm_provider: str
    llm_model: str
    embedding_model: str
    api_key: str | None
    instructions: str
    updated_at: datetime | None


class OrganizationAgentSummary(BaseModel):
    id: int
    agent_name: str
    llm_provider: str
    llm_model: str


class RAGQuery(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    agent_id: int | None = Field(default=None, gt=0)

    @field_validator("query")
    @classmethod
    def query_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query must not be empty")
        return value


class RAGSource(BaseModel):
    document_id: int
    filename: str


class RAGResponse(BaseModel):
    answer: str
    sources: list[RAGSource]


class LeaveApplicationInput(BaseModel):
    start_date: date
    end_date: date
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("end_date")
    @classmethod
    def end_date_must_not_precede_start(cls, value: date, info) -> date:
        start_date = info.data.get("start_date")
        if start_date is not None and value < start_date:
            raise ValueError("end_date must be on or after start_date")
        return value

    @field_validator("reason")
    @classmethod
    def reason_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("reason must not be empty")
        return value


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    agent_id: int | None = Field(default=None, gt=0)
    leave_request: LeaveApplicationInput | None = None

    @field_validator("message")
    @classmethod
    def message_must_not_be_empty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


class LeaveRequestResponse(BaseModel):
    id: int
    organization_id: int
    user_id: int
    start_date: date
    end_date: date
    reason: str
    status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    created_at: datetime | None

    model_config = {"from_attributes": True}


class LeaveDecision(BaseModel):
    status: Literal["approved", "rejected"]


class AdminLeaveRequestResponse(LeaveRequestResponse):
    full_name: str
    email: str


class ChatResponse(BaseModel):
    agent_name: str
    intent: str
    answer: str
    sources: list[RAGSource] = Field(default_factory=list)
    leave_request: LeaveRequestResponse | None = None
    memory: list[dict[str, str]]
