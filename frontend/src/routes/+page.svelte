<script lang="ts">
import {
  startMeeting,
  stopMeeting,
  getMeeting,
  type Meeting
} from "../services/api";
import RecordingStatus from '../components/RecordingStatus.svelte';
import MarkdownRenderer from '../components/MarkdownRenderer.svelte';
import { onDestroy } from 'svelte';

let isRecording = false;
let meetingTitle = "New Meeting";
let participants: string[] = ["Martijn Spitter"];
let newParticipantName = "";
let currentMeetingId: string | null = null;
let transcriptText = "";
let recordingTime = 0;
let timer: number | null = null;

let errorMessage = "";
let meeting: Meeting | null = null;
let pollingInterval: number | null = null;
let pollingTimeout = 2000; // Poll every 2 seconds

// Function to start recording
async function startRecording() {
  try {
    errorMessage = "";
    isRecording = true;

    // Start timer
    recordingTime = 0;
    timer = window.setInterval(() => {
      recordingTime++;
    }, 1000);

    // Call the backend API to start meeting
    const response = await startMeeting({
      title: meetingTitle,
      participants: participants
    });

    currentMeetingId = response.meeting_id;
    console.log("Started recording, meeting ID:", currentMeetingId);

    // Start the polling cycle
    startPolling();
  } catch (error) {
    console.error("Failed to start recording:", error);
    errorMessage = error instanceof Error ? error.message : "Failed to start recording";
    isRecording = false;
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }
  }
}

// Function to stop recording
async function stopRecording() {
  if (!currentMeetingId) return;

  try {
    isRecording = false;

    // Clear timer
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }

    // Call the backend API to stop meeting
    await stopMeeting(currentMeetingId);

    // Don't need to set transcript text since we'll show the RecordingStatus component
    // with processing status instead of a generic message

    // Continue polling - no need to stop it as we want to see the status updates
    // while the meeting is being processed
  } catch (error) {
    console.error("Failed to stop recording:", error);
    errorMessage = error instanceof Error ? error.message : "Failed to stop recording";
  }
}

// Centralized polling function for meeting status
function startPolling() {
  // Clear any existing polling
  stopPolling();

  // Set up a new polling interval
  pollingInterval = window.setInterval(async () => {
    if (!currentMeetingId) {
      stopPolling();
      return;
    }

    try {
      // Get the latest meeting status
      const updatedMeeting = await getMeeting(currentMeetingId);
      meeting = updatedMeeting;

      // Handle status changes
      if (meeting.status === 'failed') {
        transcriptText = meeting.error || "There was an error processing your meeting.";
        stopPolling();
      } else if (meeting.status === 'completed') {
        if (meeting.summary) {
          transcriptText = "Transcription and summarization complete!";
        } else {
          transcriptText = "Transcription complete! Files saved to your Documents folder.";
        }
        stopPolling();
      }

      // Update recording state if needed
      if (isRecording && meeting.status !== 'recording') {
        isRecording = false;
      }
    } catch (error) {
      console.error("Error polling meeting status:", error);
      // Don't stop polling on errors, just log them
    }
  }, pollingTimeout);
}

// Stop polling function
function stopPolling() {
  if (pollingInterval !== null) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
}

// Function to add a new participant
function addParticipant() {
  if (isRecording) return;
  // Only add if there's a name or we can generate one
  const name = newParticipantName.trim();
  if (name || participants.length > 0) {
    participants = [...participants, name || `Participant ${participants.length}`];
    newParticipantName = ""; // Reset the input field
  }
}

// Function to remove a participant
function removeParticipant(index: number) {
  if (isRecording || index === 0) return; // Don't remove "You"
  participants = participants.filter((_, i) => i !== index);
}

// Format seconds to display as mm:ss
function formatTime(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
}

// Clean up resources when component is destroyed
onDestroy(() => {
  if (timer !== null) {
    clearInterval(timer);
    timer = null;
  }

  stopPolling();

  // If recording is active when component is destroyed, try to stop it
  if (isRecording && currentMeetingId) {
    console.log("Stopping recording on page unmount");
    stopMeeting(currentMeetingId).catch(e =>
      console.error("Failed to stop recording on unmount:", e)
    );
  }
});</script>

<main class="min-h-screen bg-gray-50">
  <div class="container mx-auto p-4">
    <!-- Header -->
    <header class="bg-white shadow rounded-lg p-4 mb-6">
      <h1 class="text-2xl font-bold text-gray-800">Meeting Transcriber</h1>
      <p class="text-sm text-gray-500">Record, transcribe, and summarize your meetings</p>
    </header>

    <!-- Meeting Controls -->
    <div class="bg-white shadow rounded-lg p-6 mb-6">
      <div class="mb-4">
        <label for="meeting-title" class="block text-sm font-medium text-gray-700 mb-1">Meeting Title</label>
        <input type="text" id="meeting-title" bind:value={meetingTitle} class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500" disabled={isRecording} />
      </div>

      <div class="mb-6">
        <div class="flex justify-between items-center mb-1">
          <label for="participants-list" class="block text-sm font-medium text-gray-700">Participants</label>
        </div>
        {#if !isRecording}
          <div class="flex mb-2 gap-2">
            <input
              type="text"
              placeholder="Enter participant name"
              bind:value={newParticipantName}
              class="flex-grow px-3 py-1 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 text-sm"
              on:keypress={(e) => e.key === 'Enter' && addParticipant()}
              aria-label="New participant name"
            />
            <button
              class="bg-indigo-600 hover:bg-indigo-700 text-white text-sm px-3 py-1 rounded-md"
              on:click={addParticipant}
            >
              Add Participant
            </button>
          </div>
        {/if}
        <div id="participants-list" class="flex flex-wrap gap-2 mt-1 items-center">
          {#each participants as participant, i (participant)}
              <span class="bg-indigo-100 text-indigo-800 text-xs font-medium px-2.5 py-0.5 rounded flex items-center">
                {participant}
                {#if i > 0 && !isRecording}
                  <button class="ml-1 text-indigo-500 hover:text-indigo-800" on:click={() => removeParticipant(i)}>
                    ×
                  </button>
                {/if}
              </span>
          {/each}
        </div>
      </div>

      <div class="flex flex-col items-center">
        {#if isRecording}
          <div class="text-center mb-3">
            <div class="text-lg font-semibold text-red-600">{formatTime(recordingTime)}</div>
            <div class="text-sm text-gray-500">Recording in progress</div>
          </div>
          <button on:click={stopRecording} class="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-full shadow-lg flex items-center justify-center" disabled={!currentMeetingId}>
            <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              <rect x="6" y="6" width="8" height="8" rx="1"/>
            </svg>
            Stop Recording
          </button>
        {:else}
          <button on:click={startRecording} class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-6 rounded-full shadow-lg flex items-center justify-center">
            <svg class="w-5 h-5 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
              <circle cx="10" cy="10" r="6"/>
            </svg>
            Start Recording
          </button>
        {/if}
      </div>
    </div>

    <!-- Transcription Output -->
    <div class="bg-white shadow rounded-lg p-6">
      <h2 class="text-xl font-semibold text-gray-800 mb-4">Transcription</h2>

      {#if errorMessage}
        <div class="bg-red-50 p-4 rounded border border-red-200 mb-4">
          <p class="text-red-700">{errorMessage}</p>
        </div>
      {/if}

      {#if meeting && meeting.error}
        <div class="bg-red-50 p-4 rounded border mb-4">
          <p class="font-medium text-red-800 mb-2">Error Occurred</p>
          <p class="text-red-800">{meeting.error}</p>
        </div>
        <div class="mt-4 flex items-center text-sm text-gray-500">
          <svg class="w-4 h-4 mr-1 text-red-500" fill="currentColor" viewBox="0 0 20 20">
            <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1-5a1 1 0 011-1h.01a1 1 0 110 2H10a1 1 0 01-1-1zm1-9a1 1 0 00-1 1v4a1 1 0 102 0V5a1 1 0 00-1-1z" clip-rule="evenodd" />
          </svg>
          <span>Error: {meeting.error || "Unknown error occurred"}</span>
        </div>
      {:else if meeting && meeting.status === 'completed' && meeting.summary}
        <!-- Display the summary -->
        <div class="mb-6">
          <div class="mb-4 flex items-center justify-between">
            <h3 class="text-xl font-semibold text-gray-800">Meeting Summary</h3>
            <span class="bg-blue-100 text-blue-700 text-xs px-2.5 py-1 rounded-full font-medium flex items-center">
              <svg class="w-3.5 h-3.5 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              Completed
            </span>
          </div>

          <div class="bg-white p-4 rounded-lg border shadow-sm">
            <MarkdownRenderer markdown={meeting.summary} />
          </div>

          <div class="mt-4 flex items-center justify-between text-sm">
            <span class="text-gray-500">
              <svg class="w-4 h-4 mr-1 text-green-500 inline" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              Files saved at: ~/obsidian-vault/meetings/
            </span>
            <span class="text-indigo-600 font-medium">
              {new Date(meeting.created_at).toLocaleString()}
            </span>
          </div>
        </div>
      {:else if meeting && meeting.status === 'completed'}
        <!-- Show completed status with file location -->
        <div class="mb-6">
          <div class="mb-4 flex items-center justify-between">
            <h3 class="text-xl font-semibold text-gray-800">Meeting Completed</h3>
            <span class="bg-blue-100 text-blue-700 text-xs px-2.5 py-1 rounded-full font-medium flex items-center">
              <svg class="w-3.5 h-3.5 mr-1.5" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              Completed
            </span>
          </div>

          <div class="bg-white p-4 rounded-lg border shadow-sm">
            <p class="text-black">{transcriptText || "Transcription complete!"}</p>
          </div>

          <div class="mt-4 flex items-center justify-between text-sm">
            <span class="text-gray-500">
              <svg class="w-4 h-4 mr-1 text-green-500 inline" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
              </svg>
              Files saved at: ~/obsidian-vault/meetings/
            </span>
            <span class="text-indigo-600 font-medium">
              {new Date(meeting.created_at).toLocaleString()}
            </span>
          </div>
        </div>
      {:else if meeting && currentMeetingId}
        <!-- Show recording status for all other states -->
        <div class="mb-4 border rounded-lg overflow-hidden h-fit">
          <RecordingStatus
            meeting={meeting}
            isRecordingActive={isRecording}
          />
        </div>
      {:else if transcriptText}
        <div class="bg-gray-50 p-4 rounded border">
          <p class="whitespace-pre-line">{transcriptText}</p>
        </div>
      {:else}
        <div class="bg-gray-50 p-4 rounded border text-center text-gray-500">
          <p>Start recording a meeting</p>
        </div>
      {/if}
    </div>
  </div>
</main>
