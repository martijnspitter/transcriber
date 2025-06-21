<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { type Meeting } from '../services/api';

  export let meeting: Meeting;
  export let isRecordingActive: boolean = true;

  let recordingDuration = 0;
  let durationTimer: ReturnType<typeof setInterval> | null = null;

  // Format duration in seconds to mm:ss
  function formatDuration(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  }

  // Update duration based on meeting data and current time
  function updateDuration() {
    if (meeting && meeting.start_time) {
      const startTime = new Date(meeting.start_time).getTime();
      const currentTime = Date.now();

      // If meeting is still recording, calculate duration from start time to now
      if (meeting.status === 'recording') {
        recordingDuration = Math.floor((currentTime - startTime) / 1000);
      }
      // If meeting has a duration field, use that
      else if (meeting.duration) {
        recordingDuration = meeting.duration;
      }
    }
  }

  $: if (meeting) {
    updateDuration();

    // If meeting is no longer recording, stop the active flag
    if (meeting.status !== 'recording') {
      isRecordingActive = false;
    }
  }

  onMount(() => {
    // Start a timer for updating duration locally between polls
    durationTimer = setInterval(() => {
      if (isRecordingActive && meeting && meeting.status === 'recording') {
        recordingDuration += 1;
      }
    }, 1000);

    return () => {
      if (durationTimer) {
        clearInterval(durationTimer);
        durationTimer = null;
      }
    };
  });

  onDestroy(() => {
    if (durationTimer) {
      clearInterval(durationTimer);
      durationTimer = null;
    }
  });
</script>

<div class="flex flex-col h-full border border-gray-200 rounded-md bg-white">
  <div class="flex justify-between items-center p-3 border-b border-gray-200">
    <h3 class="text-lg font-semibold">Recording Status</h3>
    <div class="flex items-center">
      <span class="flex items-center text-xs py-1 px-2 rounded-full
        {meeting.status === 'recording' ? 'text-emerald-700 bg-emerald-100' :
        meeting.status === 'processing' ? 'text-amber-700 bg-amber-100' :
        meeting.status === 'completed' ? 'text-blue-700 bg-blue-100' :
        'text-red-700 bg-red-100'}">
        <span class="w-2 h-2
          {meeting.status === 'recording' ? 'bg-emerald-600 animate-[pulse_2s_infinite]' :
          meeting.status === 'processing' ? 'bg-amber-600 animate-[pulse_1.5s_infinite]' :
          meeting.status === 'completed' ? 'bg-blue-600' :
          'bg-red-600 animate-[pulse_1s_infinite]'}
          rounded-full mr-1.5"></span>
        {meeting.status === 'recording' ? 'Recording' :
        meeting.status === 'processing' ? 'Processing' :
        meeting.status === 'completed' ? 'Completed' : 'Failed'}
      </span>
    </div>
  </div>

  <div
    class="flex-1 p-4 overflow-y-auto bg-gray-50 rounded-b-md"
  >
    <div class="space-y-4">
        <!-- Meeting Status -->
        <div class="bg-white p-3 rounded-lg shadow-sm border border-gray-200">
          <h4 class="text-sm font-medium text-gray-700 mb-2">Status</h4>
          <div class="text-lg font-medium" class:text-indigo-700={meeting.status === 'recording'}
               class:text-amber-600={meeting.status === 'processing'}
               class:text-emerald-700={meeting.status === 'completed'}
               class:text-red-600={meeting.status === 'failed'}>
            {meeting.status === 'recording' ? 'Recording in progress' :
             meeting.status === 'processing' ? 'Processing recording' :
             meeting.status === 'completed' ? 'Completed' : 'Failed'}
          </div>
        </div>

        <!-- Recording Duration -->
        <div class="bg-white p-3 rounded-lg shadow-sm border border-gray-200">
          <h4 class="text-sm font-medium text-gray-700 mb-2">Recording Duration</h4>
          <div class="text-2xl font-semibold text-indigo-700">{formatDuration(recordingDuration)}</div>
        </div>

        <!-- Meeting Details -->
        <div class="bg-white p-3 rounded-lg shadow-sm border border-gray-200">
          <h4 class="text-sm font-medium text-gray-700 mb-2">Meeting Details</h4>
          <ul class="space-y-1">
            <li class="text-sm"><span class="font-medium">Title:</span> {meeting.title}</li>
            <li class="text-sm"><span class="font-medium">Participants:</span> {meeting.participants.join(', ')}</li>
          </ul>
        </div>

        <!-- Audio Devices -->
        {#if meeting.audio_devices && meeting.audio_devices.length > 0}
          <div class="bg-white p-3 rounded-lg shadow-sm border border-gray-200">
            <h4 class="text-sm font-medium text-gray-700 mb-2">Audio Devices</h4>
            <ul class="space-y-1">
              {#each meeting.audio_devices as device (device.id)}
                <li class="flex items-center text-sm">
                  <span class="w-2 h-2 bg-emerald-600 rounded-full mr-2"></span>
                  <span>{device.name}</span>
                </li>
              {/each}
            </ul>
          </div>
        {/if}

        <!-- Error Message -->
        {#if meeting.error}
          <div class="bg-red-50 p-3 rounded-lg shadow-sm border border-red-200">
            <h4 class="text-sm font-medium text-red-700 mb-2">Error</h4>
            <p class="text-sm text-red-700">{meeting.error}</p>
          </div>
        {/if}
      </div>
  </div>
</div>
