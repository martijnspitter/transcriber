/**
 * API service for communicating with the Meeting Transcriber backend
 */

// Use relative path for SvelteKit API routes
const API_BASE_URL = '/api';

// Types
export interface Meeting {
  id: string;
  title: string;
  status: 'idle' | 'recording' | 'processing' | 'completed' | 'error';
  start_time: string;
  end_time?: string;
  duration_seconds?: number;
  participants: string[];
  transcript_path?: string;
  summary_path?: string;
}

export interface CreateMeetingRequest {
  title: string;
  participants: string[];
}

export interface MeetingStatusResponse {
  status: 'idle' | 'recording' | 'processing' | 'completed' | 'error';
  message?: string;
}

/**
 * Start a new meeting recording
 */
export async function startMeeting(data: CreateMeetingRequest): Promise<Meeting> {
  try {
    const response = await fetch(`${API_BASE_URL}/meetings/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to start meeting');
    }

    return await response.json();
  } catch (error) {
    console.error('API error in startMeeting:', error);
    throw error;
  }
}

/**
 * Stop a meeting recording and start processing
 */
export async function stopMeeting(meetingId: string): Promise<MeetingStatusResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}/stop`, {
      method: 'POST',
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to stop meeting');
    }

    return await response.json();
  } catch (error) {
    console.error('API error in stopMeeting:', error);
    throw error;
  }
}

/**
 * Get details of a specific meeting
 */
export async function getMeeting(meetingId: string): Promise<Meeting> {
  try {
    const response = await fetch(`${API_BASE_URL}/meetings/${meetingId}`);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to get meeting details');
    }

    return await response.json();
  } catch (error) {
    console.error('API error in getMeeting:', error);
    throw error;
  }
}

/**
 * Get all meetings
 */
export async function getAllMeetings(): Promise<Meeting[]> {
  try {
    const response = await fetch(`${API_BASE_URL}/meetings/`);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || 'Failed to get meetings');
    }

    return await response.json();
  } catch (error) {
    console.error('API error in getAllMeetings:', error);
    throw error;
  }
}

/**
 * Poll a meeting's status until it's completed or reaches an error state
 * @param meetingId The ID of the meeting to poll
 * @param intervalMs The polling interval in milliseconds (default: 2000)
 * @param maxAttempts Maximum number of polling attempts (default: 30)
 * @returns The completed meeting data
 */
export async function pollMeetingUntilComplete(
  meetingId: string, 
  intervalMs = 2000, 
  maxAttempts = 30
): Promise<Meeting> {
  let attempts = 0;
  
  while (attempts < maxAttempts) {
    const meeting = await getMeeting(meetingId);
    
    if (meeting.status === 'completed' || meeting.status === 'error') {
      return meeting;
    }
    
    // Wait for the specified interval
    await new Promise(resolve => setTimeout(resolve, intervalMs));
    attempts++;
  }
  
  throw new Error('Polling timed out: meeting processing is taking too long');
}