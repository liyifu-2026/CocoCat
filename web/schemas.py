"""Pydantic request/response schemas for CocoCat API."""
from pydantic import BaseModel, Field
from typing import Optional


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = None
    scene: Optional[str] = None
    enabled: Optional[bool] = None


class UpdateSkillManifestRequest(BaseModel):
    public: list[str] = Field(default_factory=list)
    private: list[str] = Field(default_factory=list)


class UpdateEntriesRequest(BaseModel):
    entries: list = Field(default_factory=list)


class CreateSceneRequest(BaseModel):
    id: str = Field(min_length=1)
    context: Optional[str] = None


class UpdateContextRequest(BaseModel):
    context: str = ""


class UpdateMountedKbsRequest(BaseModel):
    mounted: list[str] = Field(default_factory=list)


class UpdateRosterRequest(BaseModel):
    agents: list[str] = Field(default_factory=list)


class UpdateEnvSkillsRequest(BaseModel):
    env_skills: list[str] = Field(default_factory=list)


class SendMailboxRequest(BaseModel):
    content: str = Field(min_length=1)
