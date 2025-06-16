<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { statusWebSocket, type StatusMessage } from '../services/websocket';

  export let meetingId: string;
  export let isRecordingActive: boolean = true;

  let recordingDuration = 0;
  let audioDevices: Array<{name: string, id: string, type?: string}> = [];
  let audioProblems: string[] = [];
  let isConnected = false;
  let connectionError = '';
  let reconnectAttempt = 0;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;


  // Format duration in seconds to mm:ss
  function formatDuration(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const remainingSeconds = Math.floor(seconds % 60);
    return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`;
  }

  onMount(() => {
    // Connect to WebSocket for status updates
    connectWebSocket();

    return () => {
      // Clean up
      disconnectWebSocket();
    };
  });

  onDestroy(() => {
      disconnectWebSocket();
      clearReconnectTimeout();
      // Reset state
      reconnectAttempt = 0;
  });

  // Connect to the WebSocket
  async function connectWebSocket() {
    try {
      await statusWebSocket.connect(meetingId);
      isConnected = true;
      connectionError = '';
      reconnectAttempt = 0;

      // Set up message handler
      statusWebSocket.onMessage((message: StatusMessage) => {
        handleWebSocketMessage(message);
      });

      // Set up error handler
      statusWebSocket.onError(() => {
        isConnected = false;
        connectionError = 'Connection lost. Attempting to reconnect...';
        scheduleReconnect();
      });

      // Set up close handler
      statusWebSocket.onClose(() => {
        isConnected = false;

        // Only attempt to reconnect if recording is still active
        if (isRecordingActive) {
          connectionError = 'Connection closed. Attempting to reconnect...';
          scheduleReconnect();
        } else {
          connectionError = 'Recording stopped';
        }
      });

      // Start ping interval to keep connection alive
      const pingInterval = setInterval(() => {
        if (statusWebSocket.isConnected()) {
          statusWebSocket.ping();
        } else {
          clearInterval(pingInterval);
          // If not connected and no error already showing, schedule reconnect
          if (isConnected) {
            isConnected = false;
            connectionError = 'Connection lost. Attempting to reconnect...';
            scheduleReconnect();
          }
        }
      }, 30000); // Send ping every 30 seconds
    } catch (error) {
      isConnected = false;
      connectionError = 'Failed to connect to status service';
      console.error('WebSocket connection error:', error);
      scheduleReconnect();
    }
  }

  // Schedule reconnection with backoff
  function scheduleReconnect() {
    // Only try to reconnect if recording is active
    if (!isRecordingActive) {
      connectionError = 'Recording stopped';
      return;
    }

    clearReconnectTimeout();

    // Maximum of 10 reconnect attempts
    if (reconnectAttempt >= 10) {
      connectionError = 'Could not reconnect after multiple attempts';
      return;
    }

    // Calculate delay with exponential backoff
    const delay = Math.min(10000, 1000 * Math.pow(1.5, reconnectAttempt));
    connectionError = `Connection lost. Reconnecting in ${Math.round(delay/1000)}s...`;

    reconnectTimeout = setTimeout(async () => {
      // Check again if recording is still active before attempting reconnect
      if (!isRecordingActive) {
        connectionError = 'Recording stopped';
        return;
      }

      connectionError = 'Attempting to reconnect...';
      reconnectAttempt++;

      try {
        await statusWebSocket.resetAndReconnect(meetingId);
        isConnected = true;
        connectionError = '';
        reconnectAttempt = 0;
      } catch (error) {
        console.error('Reconnect attempt failed:', error);
        if (isRecordingActive) {
          scheduleReconnect();
        }
      }
    }, delay);
  }

  function clearReconnectTimeout() {
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout);
      reconnectTimeout = null;
    }
  }

  // Disconnect from the WebSocket
  function disconnectWebSocket() {
    clearReconnectTimeout();
    statusWebSocket.disconnect(true); // true prevents auto reconnect
    isConnected = false;
  }

  // Handle WebSocket messages
  function handleWebSocketMessage(message: StatusMessage) {
    if (message.event === 'status_update' || message.event === 'initial_status') {
      // Update status information
      if (message.recording_duration !== undefined) {
        recordingDuration = message.recording_duration;
      }

      if (message.audio_devices) {
        audioDevices = message.audio_devices;
      }

      if (message.audio_problems) {
        audioProblems = message.audio_problems;
      }
    } else if (message.event === 'meeting_stopped') {
      // Handle meeting stopped event
      isRecordingActive = false;
      connectionError = 'Recording stopped';
    }
  }
</script>

<div class="flex flex-col h-full border border-gray-200 rounded-md bg-white">
  <div class="flex justify-between items-center p-3 border-b border-gray-200">
    <h3 class="text-lg font-semibold">Recording Status</h3>
    <div class="flex items-center">
      {#if isConnected}
        <span class="flex items-center text-xs py-1 px-2 rounded-full text-emerald-700 bg-emerald-100">
          <span class="w-2 h-2 bg-emerald-600 rounded-full mr-1.5 animate-[pulse_2s_infinite]"></span>
          Live
        </span>
      {:else}
        <span class="flex items-center text-xs py-1 px-2 rounded-full text-red-700 bg-red-100">
          <span class="w-2 h-2 bg-red-600 rounded-full mr-1.5 animate-[pulse_1s_infinite]"></span>
          {connectionError || 'Disconnected'}
        </span>
        {#if reconnectAttempt > 0}
          <button
            class="ml-2 text-xs py-1 px-2 rounded bg-blue-100 hover:bg-blue-200 text-blue-700"
            on:click={() => {
              if (isRecordingActive) {
                connectionError = 'Reconnecting...';
                statusWebSocket.resetAndReconnect(meetingId);
              } else {
                connectionError = 'Cannot reconnect: recording stopped';
              }
            }}
          >
            Reconnect Now
          </button>
        {/if}
      {/if}
    </div>
  </div>

  <div
    class="flex-1 p-4 overflow-y-auto bg-gray-50 rounded-b-md"
  >
    {#if !isConnected}
      <div class="flex justify-center items-center h-full text-gray-500 italic">
        <p>Connect to see recording status</p>
      </div>
    {:else}
      <div class="space-y-4">
        <!-- Recording Duration -->
        <div class="bg-white p-3 rounded-lg shadow-sm border border-gray-200">
          <h4 class="text-sm font-medium text-gray-700 mb-2">Recording Duration</h4>
          <div class="text-2xl font-semibold text-indigo-700">{formatDuration(recordingDuration)}</div>
        </div>

        <!-- Audio Devices -->
        <div class="bg-white p-3 rounded-lg shadow-sm border border-gray-200">
          <h4 class="text-sm font-medium text-gray-700 mb-2">Audio Devices</h4>
          {#if audioDevices.length === 0}
            <p class="text-sm text-gray-500">No audio devices detected</p>
          {:else}
            <ul class="space-y-1">
              {#each audioDevices as device (device.id)}
                              <li class="flex items-center text-sm">
                                <span class="w-2 h-2 bg-emerald-600 rounded-full mr-2"></span>
                                <span>{device.name}</span>
                                {#if device.type}
                                  <span class="ml-1 text-xs text-gray-500">({device.type})</span>
                                {/if}
                              </li>
                            {/each}
            </ul>
          {/if}
        </div>

        <!-- Audio Problems -->
        {#if audioProblems.length > 0}
          <div class="bg-red-50 p-3 rounded-lg shadow-sm border border-red-200">
            <h4 class="text-sm font-medium text-red-700 mb-2">Problems Detected</h4>
            <ul class="space-y-1">
              {#each audioProblems as problem (problem)}
                              <li class="flex items-center text-sm text-red-700">
                                <span class="w-2 h-2 bg-red-600 rounded-full mr-2"></span>
                                <span>{problem}</span>
                              </li>
                            {/each}
            </ul>
          </div>
        {/if}
      </div>
    {/if}
  </div>
</div>
