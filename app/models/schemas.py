from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class TranscriptRequest(BaseModel):
    transcript: str

class MeetingJoinRequest(BaseModel):
    link: str
    participant_name: Optional[str] = "AI Meeting Agent"

class MeetingStatusResponse(BaseModel):
    session_id: Optional[str] = None
    project_id: Optional[str] = None
    running: bool
    link: Optional[str] = None
    meeting_type: Optional[str] = None
    platform: Optional[str] = None
    join_status: str = "idle"
    message: str = ""
    in_meeting: bool = False
    requires_login: bool = False
    waiting_for_host: bool = False
    mode: Optional[str] = None
    cdp_attached: bool = False
    transcript: str = ""
    requirements: Dict[str, Any] = Field(default_factory=dict)

class ProjectGenerationResponse(BaseModel):
    success: bool
    message: str
    running_url: Optional[str] = None
    requirements: Dict[str, Any] = Field(default_factory=dict)
    details: Dict[str, Any] = Field(default_factory=dict)
