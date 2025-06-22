/**
 * API service for communicating with the Meeting Transcriber backend
 */

// Backend API URL
const API_BASE_URL = '';

// Types
export interface Meeting {
  id: string;
  title: string;
  status: 'recording' | 'processing' | 'recording_created' | 'transcript_created' | 'summary_created' | 'completed' | 'failed';
  created_at: string;
  start_time: string;
  duration: number;
  participants: string[];
  transcript_path: string;
  audio_devices: AudioDevice[];
  transcript?: string;
  summary?: string;
  error?: string;
}

export interface AudioDevice {
  id: number;
  name: string;
  channels: number;
  is_input: boolean;
  is_output: boolean;
  is_system: boolean;
  is_default: boolean;
}

export interface CreateMeetingRequest {
  title: string;
  participants: string[];
}

export interface StartMeetingResponse {
  meeting_id: string;
}

export interface MeetingStatusResponse {
  status: 'recording' | 'processing' | 'recording_created' | 'transcript_created' | 'summary_created' | 'completed' | 'failed';
  message?: string;
}

export interface StopMeetingRequest {
  meeting_id: string;
}

export interface StopMeetingResponse {
  message: string;
}

export interface MeetingsResponse {
  status: string;
  meetings: Meeting[];
}

/**
 * Start a new meeting recording
 */
export async function startMeeting(data: CreateMeetingRequest): Promise<StartMeetingResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/meetings`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to start meeting');
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
export async function stopMeeting(meetingId: string): Promise<StopMeetingResponse> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/meetings/${meetingId}/stop`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ meeting_id: meetingId }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to stop meeting');
    }

    const responseData = await response.json();
    return responseData;
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
    const response = await fetch(`${API_BASE_URL}/api/meetings/${meetingId}`);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to get meeting details');
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
    const response = await fetch(`${API_BASE_URL}/api/meetings`);

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Failed to get meetings');
    }

    const data: MeetingsResponse = await response.json();
    return data.meetings;
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

    if (meeting.status === 'completed' || meeting.status === 'failed') {
      return meeting;
    }

    // Wait for the specified interval
    await new Promise(resolve => setTimeout(resolve, intervalMs));
    attempts++;
  }

  throw new Error('Polling timed out: meeting processing is taking too long');
}
