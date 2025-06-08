from fastapi import APIRouter, HTTPException, BackgroundTasks, WebSocket, Depends, status
from ..models.meeting import MeetingCreate, MeetingResponse, MeetingStatus, MeetingStatusResponse
from ..services.transcriber import TranscriberService
import uuid
from typing import List
import logging

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton service instance
transcriber_service = TranscriberService()

@router.post("/meetings/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting(meeting_data: MeetingCreate):
    """Start a new meeting recording"""
    meeting_id = str(uuid.uuid4())

    try:
        success, message = transcriber_service.start_meeting(
            meeting_id=meeting_id,
            title=meeting_data.title,
            participants=meeting_data.participants
        )

        if not success:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)

        # Get updated meeting data
        meeting_status = transcriber_service.get_meeting_status(meeting_id)

        if meeting_status is None:
            logger.error(f"Meeting status returned None for meeting ID {meeting_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve meeting status after creation"
            )

        return MeetingResponse(
            id=meeting_id,
            title=meeting_status["title"],
            status=MeetingStatus(meeting_status["status"]),  # Convert string to enum
            start_time=meeting_status["start_time"],
            participants=meeting_status["participants"],
            transcript_path=None,
            summary_path=None
        )
    except Exception as e:
        logger.error(f"Error creating meeting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create meeting: {str(e)}"
        )

@router.post("/meetings/{meeting_id}/stop", response_model=MeetingStatusResponse)
async def stop_meeting(meeting_id: str):
    """Stop a meeting recording and start processing"""
    try:
        success, message = transcriber_service.stop_meeting(meeting_id)

        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)

        meeting_status = transcriber_service.get_meeting_status(meeting_id)

        if meeting_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meeting status for {meeting_id} not found"
            )

        return MeetingStatusResponse(
            status=MeetingStatus(meeting_status["status"]),  # Convert string to enum
            message=f"Meeting {meeting_id} stopped and processing started"
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error stopping meeting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop meeting: {str(e)}"
        )

@router.get("/meetings/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(meeting_id: str):
    """Get meeting status"""
    try:
        meeting_status = transcriber_service.get_meeting_status(meeting_id)

        if meeting_status is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Meeting {meeting_id} not found"
            )

        # Convert string status to enum and handle None values
        return MeetingResponse(
            id=meeting_status["id"],
            title=meeting_status["title"],
            status=MeetingStatus(meeting_status["status"]),
            start_time=meeting_status["start_time"],
            end_time=meeting_status.get("end_time"),
            duration_seconds=meeting_status.get("duration_seconds"),
            participants=meeting_status["participants"],
            transcript_path=meeting_status.get("transcript_path"),
            summary_path=meeting_status.get("summary_path")
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error retrieving meeting: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve meeting: {str(e)}"
        )

@router.get("/meetings/", response_model=List[MeetingResponse])
async def get_all_meetings():
    """Get all meetings"""
    try:
        meetings = transcriber_service.get_all_meetings()
        result = []

        for m in meetings:
            if m is not None:
                result.append(MeetingResponse(
                    id=m["id"],
                    title=m["title"],
                    status=MeetingStatus(m["status"]),
                    start_time=m["start_time"],
                    end_time=m.get("end_time"),
                    duration_seconds=m.get("duration_seconds"),
                    participants=m["participants"],
                    transcript_path=m.get("transcript_path"),
                    summary_path=m.get("summary_path")
                ))

        return result
    except Exception as e:
        logger.error(f"Error retrieving meetings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve meetings: {str(e)}"
        )
