from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from ..models.meeting import MeetingCreate, MeetingResponse, MeetingStatus, MeetingStatusResponse
from ..services.transcriber import TranscriberService
import uuid
from typing import List, Dict
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton service instance
transcriber_service = TranscriberService()

# Store active WebSocket connections
active_connections: Dict[str, List[WebSocket]] = {}

# Callback function for transcription updates
async def transcription_update_callback(meeting_id: str, full_transcript: str, new_text: str):
    """Callback function that sends transcription updates to connected WebSocket clients"""
    if meeting_id in active_connections and active_connections[meeting_id]:
        # Create timestamp for the update
        timestamp = datetime.now().isoformat()

        # Prepare the message
        message = {
            "event": "transcript_update",
            "meeting_id": meeting_id,
            "full_transcript": full_transcript,
            "new_text": new_text,
            "timestamp": timestamp
        }

        # Send to all connected clients
        disconnected_clients = []
        for i, connection in enumerate(active_connections[meeting_id]):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error sending to WebSocket client: {e}")
                disconnected_clients.append(i)

        # Remove disconnected clients (in reverse order to avoid index issues)
        for idx in sorted(disconnected_clients, reverse=True):
            try:
                del active_connections[meeting_id][idx]
            except:
                pass

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

        # Check if meeting_status is None before trying to access it
        if meeting_status is None:
            logger.error(f"Meeting status is None for meeting_id: {meeting_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get meeting status after creation"
            )

        return MeetingResponse(
            id=meeting_id,
            title=meeting_status["title"],
            status=MeetingStatus(meeting_status["status"]),  # Convert string to enum
            start_time=meeting_status["start_time"],
            participants=meeting_status["participants"],
            transcript_path=None,
            summary_path=None,
            summary_content=None,
            current_transcript=""
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

        # Check if meeting_status is None before accessing it
        if meeting_status is None:
            logger.error(f"Failed to get meeting status for meeting_id: {meeting_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get meeting status after stopping"
            )

        # Notify any WebSocket connections that the meeting has stopped
        if meeting_id in active_connections:
            for connection in active_connections[meeting_id]:
                try:
                    await connection.send_json({
                        "event": "meeting_stopped",
                        "meeting_id": meeting_id,
                        "status": meeting_status["status"]
                    })
                except Exception as e:
                    logger.error(f"Error sending WebSocket notification: {e}")

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
            summary_path=meeting_status.get("summary_path"),
            summary_content=meeting_status.get("summary_content"),
            current_transcript=meeting_status.get("current_transcript", "")
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
                    summary_path=m.get("summary_path"),
                    summary_content=m.get("summary_content")
                ))

        return result
    except Exception as e:
        logger.error(f"Error retrieving meetings: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve meetings: {str(e)}"
        )


@router.websocket("/ws/meetings/{meeting_id}/transcript")
async def websocket_transcript(websocket: WebSocket, meeting_id: str):
    """WebSocket endpoint for real-time transcript updates"""
    await websocket.accept()

    try:
        # Check if meeting exists
        meeting_status = transcriber_service.get_meeting_status(meeting_id)
        if not meeting_status:
            await websocket.send_json({"error": f"Meeting {meeting_id} not found"})
            await websocket.close()
            return

        # Add this connection to active connections
        if meeting_id not in active_connections:
            active_connections[meeting_id] = []
        active_connections[meeting_id].append(websocket)

        # Register callback for transcription updates
        transcriber_service.register_transcript_callback(meeting_id, transcription_update_callback)

        # Send initial transcript if available
        if meeting_status.get("current_transcript"):
            await websocket.send_json({
                "event": "initial_transcript",
                "meeting_id": meeting_id,
                "transcript": meeting_status["current_transcript"],
                "timestamp": datetime.now().isoformat()
            })

        # Keep the connection alive until client disconnects
        try:
            while True:
                # Wait for messages from client (ping, etc.)
                data = await websocket.receive_text()
                # Process client messages if needed
                if data == "ping":
                    await websocket.send_json({"event": "pong"})
        except WebSocketDisconnect:
            logger.info(f"WebSocket client disconnected from meeting {meeting_id}")
        finally:
            # Remove connection from active connections
            if meeting_id in active_connections and websocket in active_connections[meeting_id]:
                active_connections[meeting_id].remove(websocket)
            # Unregister callback when all clients disconnect
            if not active_connections.get(meeting_id):
                transcriber_service.unregister_transcript_callback(meeting_id, transcription_update_callback)

    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        try:
            await websocket.close()
        except:
            pass
