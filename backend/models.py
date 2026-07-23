from typing import Optional

from pydantic import BaseModel, Field


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40)
    password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class InvestigationRequest(BaseModel):
    namespace: str = Field(min_length=1, max_length=63)
    deployment: Optional[str] = None
    cluster_context: Optional[str] = None


class InvestigationResponse(BaseModel):
    id: int
    namespace: str
    deployment: Optional[str]
    cluster_context: Optional[str] = None
    status: str
    failure_pattern: Optional[str] = None
    root_cause: Optional[str] = None
    confidence: Optional[int] = None
    fix_commands: Optional[list[str]] = None
    error: Optional[str] = None
    analysis_duration_seconds: Optional[float] = None
    created_at: str
