from pydantic import BaseModel
from typing import List
from .user import UserProfile

class HouseholdCreate(BaseModel):
    name: str

class HouseholdResponse(BaseModel):
    id: str
    name: str
    head_user_id: str
    shared_eating_mode: str
    member_count: int
    cuisine_prefs: List[str]
    members: List[UserProfile]

class InviteResponse(BaseModel):
    invite_token: str

class UpdatePreferencesRequest(BaseModel):
    cuisine_prefs: List[str]