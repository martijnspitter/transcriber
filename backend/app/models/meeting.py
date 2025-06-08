from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

class MeetingStatus(str, Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"

class MeetingCreate(BaseModel):
    title: str = Field(default="Untitled Meeting")
    participants: List[str] = Field(default_factory=list)

class MeetingResponse(BaseModel):
    id: str
    title: str
    status: MeetingStatus
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    participants: List[str] = Field(default_factory=list)
    transcript_path: Optional[str] = None
    summary_path: Optional[str] = None
    current_transcript: Optional[str] = None

class MeetingStatusResponse(BaseModel):
    status: MeetingStatus
    message: Optional[str] = None
