/**
 * WebSocket service for real-time transcription updates
 */

 type MessageCallback = (message: TranscriptMessage) => void;
type ErrorCallback = (error: Event) => void;
type CloseCallback = (event: CloseEvent) => void;

interface TranscriptMessage {
  event: string;
  meeting_id: string;
  full_transcript?: string;
  new_text?: string;
  transcript?: string; // For initial_transcript events
  timestamp: string;
}

class TranscriptWebSocketService {
  private socket: WebSocket | null = null;
  private isConnecting = false;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private messageCallback: MessageCallback | null = null;
  private errorCallback: ErrorCallback | null = null;
  private closeCallback: CloseCallback | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private reconnectDelay = 1000; // 1 second initial delay
  private backendRestarting = false;
  private manualDisconnect = false;
  private currentMeetingId: string | null = null;

  /**
   * Connect to the WebSocket for real-time transcription
   * @param meetingId The ID of the meeting to subscribe to
   */
  connect(meetingId: string): Promise<void> {
    // Store the meeting ID for reconnection
    this.currentMeetingId = meetingId;
    
    // Reset manual disconnect flag when attempting to connect
    this.manualDisconnect = false;
    
    if (this.socket?.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }

    if (this.isConnecting) {
      return new Promise((resolve, reject) => {
        const checkInterval = setInterval(() => {
          if (this.socket?.readyState === WebSocket.OPEN) {
            clearInterval(checkInterval);
            resolve();
          } else if (!this.isConnecting) {
            clearInterval(checkInterval);
            reject(new Error('Connection failed'));
          }
        }, 100);
      });
    }

    return new Promise((resolve, reject) => {
      this.isConnecting = true;

      // Determine WebSocket URL based on current environment
      const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
      const baseUrl = window.location.hostname === 'localhost' ?
        `${protocol}://${window.location.hostname}:8000` :
        `${protocol}://${window.location.host}`;

      const wsUrl = `${baseUrl}/api/ws/meetings/${meetingId}/transcript`;

      try {
        this.socket = new WebSocket(wsUrl);

        this.socket.onopen = () => {
          console.log('WebSocket connected');
          this.isConnecting = false;
          this.reconnectAttempts = 0;
          this.clearReconnectTimer();
          resolve();
        };

        this.socket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (this.messageCallback) {
              this.messageCallback(data);
            }
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.socket.onerror = (error) => {
          console.error('WebSocket error:', error);
          if (this.errorCallback) {
            this.errorCallback(error);
          }
        };

        this.socket.onclose = (event) => {
          console.log('WebSocket closed:', event, 'Manual disconnect:', this.manualDisconnect);
          this.isConnecting = false;

          if (this.closeCallback) {
            this.closeCallback(event);
          }

          // Only attempt to reconnect if:
          // 1. We haven't reached max attempts
          // 2. This wasn't a manual disconnect
          if (!this.manualDisconnect && this.reconnectAttempts < this.maxReconnectAttempts) {
            console.log('Scheduling reconnect attempt...');
            
            // Backend restart detection: if connection was previously successful
            if (this.reconnectAttempts > 0) {
              this.backendRestarting = true;
            }
            
            this.scheduleReconnect(meetingId);
          } else if (this.manualDisconnect) {
            console.log('Not reconnecting due to manual disconnect');
          }
        };
      } catch (error) {
        this.isConnecting = false;
        console.error('Failed to create WebSocket connection:', error);
        reject(error);
      }
    });
  }

  /**
   * Disconnect the WebSocket
   * @param preventReconnect If true, prevents automatic reconnection attempts
   */
  disconnect(preventReconnect: boolean = true): void {
    console.log('Disconnecting WebSocket, preventReconnect:', preventReconnect);
    this.clearReconnectTimer();
    
    // Set manual disconnect flag to prevent reconnection loops
    this.manualDisconnect = preventReconnect;
    
    if (this.socket) {
      // Only prevent reconnection attempts when explicitly requested
      if (preventReconnect) {
        this.reconnectAttempts = this.maxReconnectAttempts;
      }

      if (this.socket.readyState === WebSocket.OPEN ||
          this.socket.readyState === WebSocket.CONNECTING) {
        this.socket.close();
      }
      this.socket = null;
    }
  }

  /**
   * Send a ping message to keep the connection alive
   */
  ping(): void {
    if (this.socket?.readyState === WebSocket.OPEN) {
      this.socket.send('ping');
    }
  }

  /**
   * Set a callback to be called when a message is received
   * @param callback Function to be called with the parsed message data
   */
  onMessage(callback: MessageCallback): void {
    this.messageCallback = callback;
  }

  /**
   * Set a callback to be called when an error occurs
   * @param callback Function to be called with the error
   */
  onError(callback: ErrorCallback): void {
    this.errorCallback = callback;
  }

  /**
   * Set a callback to be called when the connection closes
   * @param callback Function to be called when the connection closes
   */
  onClose(callback: CloseCallback): void {
    this.closeCallback = callback;
  }

  /**
   * Clear the reconnection timer
   */
  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  /**
   * Schedule a reconnection attempt
   */
  private scheduleReconnect(meetingId: string): void {
    // Don't schedule reconnect if we manually disconnected
    if (this.manualDisconnect) {
      console.log('Not scheduling reconnect due to manual disconnect');
      return;
    }
    
    this.clearReconnectTimer();

    // Use different strategies depending on whether we think the backend is restarting
    let delay: number;
    
    if (this.backendRestarting) {
      // If we think the backend is restarting, use fixed delay but increase
      // it slightly each time to avoid overwhelming the server
      delay = Math.min(5000, 1000 + this.reconnectAttempts * 500);
      console.log('Backend appears to be restarting, using fixed reconnect delay');
    } else {
      // Otherwise use exponential backoff for normal reconnect attempts
      delay = Math.min(30000, this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts));
    }

    // Use the stored meeting ID if available
    const targetMeetingId = meetingId || this.currentMeetingId;
    
    // Don't reconnect if we don't have a meeting ID
    if (!targetMeetingId) {
      console.log('No meeting ID available, cannot reconnect');
      return;
    }

    this.reconnectTimer = setTimeout(() => {
      // Double-check we haven't been manually disconnected while waiting
      if (this.manualDisconnect) {
        console.log('Not reconnecting due to manual disconnect during delay');
        return;
      }
      
      console.log(`Attempting to reconnect (${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})...`);
      this.reconnectAttempts++;
      this.connect(targetMeetingId).then(() => {
        // Reset backend restarting flag if we reconnect successfully
        this.backendRestarting = false;
        console.log('Reconnection successful');
      }).catch((error) => {
        console.error('Reconnect failed:', error);
      });
    }, delay);
  }

  /**
   * Check if the WebSocket is connected
   */
  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  /**
   * Reset the service state and attempt a fresh connection
   * Used when the application needs to force a new connection
   */
  resetAndReconnect(meetingId: string): Promise<void> {
    console.log('Resetting connection and attempting to reconnect...');
    this.clearReconnectTimer();
    this.reconnectAttempts = 0;
    this.backendRestarting = true;
    this.manualDisconnect = false; // Ensure we're not in manual disconnect state
    
    // Store the meeting ID
    this.currentMeetingId = meetingId;
    
    // Disconnect without preventing reconnects
    this.disconnect(false);
    
    // Add a small delay to avoid connection race conditions
    return new Promise((resolve) => {
      setTimeout(() => {
        this.connect(meetingId).then(resolve).catch((error) => {
          console.error('Failed to reconnect after reset:', error);
          throw error;
        });
      }, 500);
    });
  }
}

// Export a singleton instance
export const transcriptWebSocket = new TranscriptWebSocketService();

// Export types
export type { TranscriptMessage };
