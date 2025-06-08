<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { transcriptWebSocket, type TranscriptMessage } from '../services/websocket';

  export let meetingId: string;
  export let initialTranscript: string = '';

  let transcript = initialTranscript;
  let transcriptSegments: { text: string; timestamp?: string }[] = [];
  let transcriptElement: HTMLElement;
  let isConnected = false;
  let connectionError = '';
  let autoScroll = true;
  let reconnectAttempt = 0;
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;

  // Format timestamp to readable time
  function formatTimestamp(isoTimestamp: string): string {
    try {
      const date = new Date(isoTimestamp);
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return '';
    }
  }

  // Initialize transcript segments if we have initial text
  onMount(() => {
    if (initialTranscript) {
      transcriptSegments = [{ text: initialTranscript }];
    }

    // Connect to WebSocket for live transcription
    connectWebSocket();

    // Set up auto-scrolling
    return () => {
      // Clean up
      disconnectWebSocket();
    };
  });

  onDestroy(() => {
      disconnectWebSocket();
      clearReconnectTimeout();
    });

  // Connect to the WebSocket
  async function connectWebSocket() {
    try {
      await transcriptWebSocket.connect(meetingId);
      isConnected = true;
      connectionError = '';
      reconnectAttempt = 0;

      // Set up message handler
      transcriptWebSocket.onMessage((message: TranscriptMessage) => {
        handleWebSocketMessage(message);
      });

      // Set up error handler
      transcriptWebSocket.onError(() => {
        isConnected = false;
        connectionError = 'Connection lost. Attempting to reconnect...';
        scheduleReconnect();
      });

      // Set up close handler
      transcriptWebSocket.onClose(() => {
        isConnected = false;
        connectionError = 'Connection closed. Attempting to reconnect...';
        scheduleReconnect();
      });

      // Start ping interval to keep connection alive
      const pingInterval = setInterval(() => {
        if (transcriptWebSocket.isConnected()) {
          transcriptWebSocket.ping();
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
      connectionError = 'Failed to connect to live transcription service';
      console.error('WebSocket connection error:', error);
      scheduleReconnect();
    }
  }

  // Schedule reconnection with backoff
  function scheduleReconnect() {
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
      connectionError = 'Attempting to reconnect...';
      reconnectAttempt++;

      try {
        await transcriptWebSocket.resetAndReconnect(meetingId);
        isConnected = true;
        connectionError = '';
        reconnectAttempt = 0;
      } catch (error) {
        console.error('Reconnect attempt failed:', error);
        scheduleReconnect();
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
    transcriptWebSocket.disconnect(true); // true prevents auto reconnect
    isConnected = false;
  }

  // Handle WebSocket messages
  function handleWebSocketMessage(message: TranscriptMessage) {
    if (message.event === 'transcript_update') {
      // Update the full transcript
      transcript = message.full_transcript || transcript;

      // Add new segment
      if (message.new_text) {
        // Just add the new text as a single segment with its timestamp
        // instead of splitting the full transcript (which causes duplicates)
        transcriptSegments = [...transcriptSegments, {
          text: message.new_text.trim(),
          timestamp: message.timestamp
        }];

        // Auto-scroll if enabled
        if (autoScroll && transcriptElement) {
          setTimeout(() => {
            transcriptElement.scrollTop = transcriptElement.scrollHeight;
          }, 100);
        }
      }
    } else if (message.event === 'initial_transcript') {
      // Set initial transcript
      transcript = message.transcript || '';
      if (transcript) {
        // Split initial transcript into sentences if possible
        const sentences = transcript
          .replace(/([.!?])\s+/g, "$1|")
          .split("|")
          .filter(s => s.trim().length > 0);

        if (sentences.length > 1) {
          // Create unique timestamps for each sentence by adding offset
          const baseTime = new Date(message.timestamp).getTime();
          transcriptSegments = sentences.map((s, index) => {
            // Add 1 second offset per sentence for visual separation
            const adjustedTime = new Date(baseTime + (index * 1000));
            return {
              text: s.trim(),
              timestamp: adjustedTime.toISOString()
            };
          });
        } else {
          transcriptSegments = [{ text: transcript, timestamp: message.timestamp }];
        }
      }
    } else if (message.event === 'meeting_stopped') {
      // Optionally handle meeting stopped event
    }
  }

  // Toggle auto-scroll
  function toggleAutoScroll() {
    autoScroll = !autoScroll;
    if (autoScroll && transcriptElement) {
      transcriptElement.scrollTop = transcriptElement.scrollHeight;
    }
  }
</script>

<div class="flex flex-col h-full border border-gray-200 rounded-md bg-white">
  <div class="flex justify-between items-center p-3 border-b border-gray-200">
    <h3 class="text-lg font-semibold">Live Transcription</h3>
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
              connectionError = 'Reconnecting...';
              transcriptWebSocket.resetAndReconnect(meetingId);
            }}
          >
            Reconnect Now
          </button>
        {/if}
      {/if}

      <button
        class={`ml-3 text-xs py-1 px-2 rounded bg-gray-100 hover:bg-gray-200 ${autoScroll ? 'bg-blue-50 text-blue-700' : ''}`}
        on:click={toggleAutoScroll}
      >
        Auto-scroll {autoScroll ? 'ON' : 'OFF'}
      </button>
    </div>
  </div>

  <div
    class="flex-1 p-4 overflow-y-auto bg-gray-50 rounded-b-md"
    bind:this={transcriptElement}
  >
    {#if transcriptSegments.length === 0}
      <div class="flex justify-center items-center h-full text-gray-500 italic">
        {#if isConnected}
          <p>Waiting for speech...</p>
        {:else}
          <p>Connect to see live transcription</p>
        {/if}
      </div>
    {:else}
      <div class="space-y-3">
        {#each transcriptSegments as segment, i (`segment_${i}`)}
          <div class="transcript-segment">
            {#if segment.timestamp}
              <div class="text-xs text-gray-500 mb-1">
                {formatTimestamp(segment.timestamp)}
              </div>
            {/if}
            <div class={`whitespace-pre-line leading-relaxed ${i === transcriptSegments.length - 1 ? 'text-indigo-700 font-medium' : ''}`}>
              {segment.text}
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>

<!-- No custom CSS needed as we're using Tailwind classes -->
