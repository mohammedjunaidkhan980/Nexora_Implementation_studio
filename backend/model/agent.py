from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from database import Base


class OrganizationAgent(Base):
    __tablename__ = "organization_agents"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id"), nullable=False, index=True
    )
    agent_name = Column(
        String(128),
        nullable=False,
        default="Organization Assistant",
        server_default="Organization Assistant",
    )
    base_url = Column(String(2048), nullable=False)
    llm_provider = Column(String(128), nullable=False)
    llm_model = Column(String(255), nullable=False)
    embedding_model = Column(String(255), nullable=False)
    encrypted_api_key = Column(Text, nullable=False)
    instructions = Column(Text, nullable=False)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
