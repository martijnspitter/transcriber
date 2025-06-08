<script lang="ts">
import {
  startMeeting,
  stopMeeting,
  pollMeetingUntilComplete,
  type Meeting
} from "../services/api";
import LiveTranscription from '../components/LiveTranscription.svelte';

let isRecording = false;
let meetingTitle = "New Meeting";
let participants: string[] = ["You"];
let currentMeetingId: string | null = null;
let transcriptText = "";
let recordingTime = 0;
let timer: number | null = null;
let isProcessing = false;
let errorMessage = "";
let meeting: Meeting | null = null;

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

    currentMeetingId = response.id;
    console.log("Started recording, meeting ID:", currentMeetingId);
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
    isProcessing = true;

    // Clear timer
    if (timer !== null) {
      clearInterval(timer);
      timer = null;
    }

    // Call the backend API to stop meeting
    await stopMeeting(currentMeetingId);
    transcriptText = "Processing your meeting recording...";

    // Poll for meeting status until complete
    try {
      meeting = await pollMeetingUntilComplete(currentMeetingId);
      if (meeting.status === 'completed') {
        transcriptText = `Transcription complete! Files saved at:\n\nTranscript: ${meeting.transcript_path}\nSummary: ${meeting.summary_path}`;
      } else {
        transcriptText = "There was an error processing your meeting.";
      }
    } catch (pollError) {
      console.error("Error polling meeting status:", pollError);
      transcriptText = "Transcription is taking longer than expected. Please check status later.";
    }

    isProcessing = false;
  } catch (error) {
    console.error("Failed to stop recording:", error);
    errorMessage = error instanceof Error ? error.message : "Failed to stop recording";
    isProcessing = false;
  }
}

// Function to add a new participant
function addParticipant() {
  if (isRecording) return;
  participants = [...participants, `Participant ${participants.length}`];
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
}</script>

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
          {#if !isRecording}
            <button class="text-xs text-indigo-600 hover:text-indigo-800" on:click={addParticipant}>
              + Add Participant
            </button>
          {/if}
        </div>
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

      {#if isRecording && currentMeetingId}
        <!-- Live transcription during recording -->
        <div class="h-64 mb-4 border rounded-lg overflow-hidden">
          <LiveTranscription 
            meetingId={currentMeetingId} 
            initialTranscript=""
          />
        </div>
      {:else if isProcessing}
        <div class="bg-gray-50 p-4 rounded border text-center">
          <div class="flex justify-center items-center mb-2">
            <div class="animate-spin rounded-full h-6 w-6 border-b-2 border-indigo-500"></div>
          </div>
          <p>Processing your meeting recording...</p>
        </div>
      {:else if transcriptText}
        <div class="bg-gray-50 p-4 rounded border">
          <p class="whitespace-pre-line">{transcriptText}</p>
        </div>
      {:else}
        <div class="bg-gray-50 p-4 rounded border text-center text-gray-500">
          <p>Start recording a meeting to see the transcription here</p>
          <p class="text-xs mt-2">Real-time transcription will appear as you speak</p>
        </div>
      {/if}

      {#if meeting && meeting.status === 'completed'}
        <div class="mt-4 flex gap-2">
          <a href={meeting.transcript_path} target="_blank" class="text-sm text-indigo-600 hover:text-indigo-800">
            View Full Transcript
          </a>
          <span class="text-gray-500">•</span>
          <a href={meeting.summary_path} target="_blank" class="text-sm text-indigo-600 hover:text-indigo-800">
            View Summary
          </a>
        </div>
      {/if}
    </div>
  </div>
</main>
