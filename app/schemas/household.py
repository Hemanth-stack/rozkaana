from typing import Optional
from uuid import UUID

from pydantic import BaseModel

from app.schemas.user import UserProfile


class HouseholdCreate(BaseModel):
    name: str
    cuisine_prefs: Optional[list[str]] = []


class HouseholdResponse(BaseModel):
    id: UUID
    name: str
    head_user_id: Optional[UUID]
    shared_eating_mode: Optional[str]
    member_count: int
    cuisine_prefs: Optional[list[str]] = []
    members: list[UserProfile] = []

    model_config = {"from_attributes": True}


class InviteResponse(BaseModel):
    invite_url: str
    token: str


class UpdatePreferencesRequest(BaseModel):
    cuisine_prefs: list[str]
