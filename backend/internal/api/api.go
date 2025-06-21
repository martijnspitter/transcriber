package api

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"os/signal"

	"syscall"
	"time"

	audiocapture "github.com/martijnspitter/transcriber/internal/audio_capture"
	"github.com/martijnspitter/transcriber/internal/logger"
	"github.com/martijnspitter/transcriber/internal/transcriber"
)

// Server represents the API server
type Server struct {
	router      *http.ServeMux
	server      *http.Server
	logger      *logger.Logger
	transcriber *transcriber.TranscriberService
}

// NewServer creates a new API server instance
func NewServer(logger *logger.Logger, transcriber *transcriber.TranscriberService) *Server {
	s := &Server{
		router:      http.NewServeMux(),
		logger:      logger,
		transcriber: transcriber,
	}

	// Register all available routes
	s.registerRoutes()

	return s
}

// registerRoutes sets up all the API endpoints
func (s *Server) registerRoutes() {
	// Health check endpoint
	s.router.HandleFunc("/health", s.handleHealth())

	// Recording endpoints
	s.router.HandleFunc("/start-recording", s.handleStartRecording())
	s.router.HandleFunc("/stop-recording", s.handleStopRecording())

	// Meeting status endpoints
	s.router.HandleFunc("/meeting-status", s.handleGetMeetingStatus())
	s.router.HandleFunc("/meetings", s.handleGetAllMeetings())

	s.router.HandleFunc("/list-audio-devices", s.handleListAudioDevices())

	// Root endpoint
	s.router.HandleFunc("/", s.handleRoot())
}

// handleHealth returns a handler for health check requests
func (s *Server) handleHealth() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		response := map[string]string{"status": "ok", "timestamp": time.Now().Format(time.RFC3339)}
		s.respondWithJSON(w, http.StatusOK, response)
	}
}

// handleRoot returns a handler for the root endpoint
func (s *Server) handleRoot() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}

		response := map[string]string{"message": "Transcriber API Server"}
		s.respondWithJSON(w, http.StatusOK, response)
	}
}

// handleStartRecording returns a handler for starting recording requests
func (s *Server) handleStartRecording() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Only allow POST method
		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		var requestBody struct {
			Title        string   `json:"title"` // in seconds
			Participants []string `json:"participants,omitempty"`
		}

		// Parse the request body for participants
		if err := json.NewDecoder(r.Body).Decode(&requestBody); err != nil {
			s.respondWithJSON(w, http.StatusBadRequest, map[string]string{
				"error": "Invalid request body",
			})
			return
		}

		meetingId, err := s.transcriber.StartRecording(requestBody.Title, requestBody.Participants)
		if err != nil {
			s.logger.Error("Failed to list audio devices", "error", err)
			s.respondWithJSON(w, http.StatusInternalServerError, map[string]string{
				"error": fmt.Sprintf("Failed to list audio devices: %v", err),
			})
			return
		}

		s.respondWithJSON(w, http.StatusAccepted, map[string]interface{}{
			"meeting_id": meetingId,
		})
	}
}

// handleStopRecording returns a handler for stopping recording requests
func (s *Server) handleStopRecording() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Only allow POST method
		if r.Method != http.MethodPost {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		var requestBody struct {
			MeetingId string `json:"meeting_id"` // in seconds
		}

		// Parse the request body for meeting ID
		if err := json.NewDecoder(r.Body).Decode(&requestBody); err != nil {
			s.logger.Error("Failed to decode request body", "error", err)
			s.respondWithJSON(w, http.StatusBadRequest, map[string]string{
				"error": "Invalid request body",
			})
			return
		}

		err := s.transcriber.StopMeeting(requestBody.MeetingId)
		if err != nil {
			s.logger.Error("Failed to stop meeting", "error", err, "meetingId", requestBody.MeetingId)
			s.respondWithJSON(w, http.StatusInternalServerError, map[string]string{
				"error": fmt.Sprintf("Failed to stop meeting: %v", err),
			})
			return
		}

		s.respondWithJSON(w, http.StatusAccepted, map[string]interface{}{
			"message": "Meeting processing started",
		})
	}
}

// handleCaptureAndMergeAudio returns a handler for capturing and merging audio in one operation
// handleGetMeetingStatus returns a handler for getting meeting status by ID
func (s *Server) handleGetMeetingStatus() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Only allow GET method
		if r.Method != http.MethodGet {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		// Get meeting ID from query parameter
		meetingId := r.URL.Query().Get("id")
		if meetingId == "" {
			s.respondWithJSON(w, http.StatusBadRequest, map[string]string{
				"error": "Missing meeting ID parameter",
			})
			return
		}

		// Get meeting status
		meeting, err := s.transcriber.GetMeetingStatus(meetingId)
		if err != nil {
			s.logger.Error("Failed to get meeting status", "error", err, "meetingId", meetingId)
			s.respondWithJSON(w, http.StatusNotFound, map[string]string{
				"error": fmt.Sprintf("Failed to get meeting status: %v", err),
			})
			return
		}

		s.respondWithJSON(w, http.StatusOK, meeting)
	}
}

// handleGetAllMeetings returns a handler for getting all meetings
func (s *Server) handleGetAllMeetings() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Only allow GET method
		if r.Method != http.MethodGet {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		// Get all meetings
		meetings := s.transcriber.GetAllMeetings()

		s.respondWithJSON(w, http.StatusOK, map[string]interface{}{
			"status":   "success",
			"meetings": meetings,
		})
	}
}

// handleListAudioDevices returns a handler that lists available audio devices
func (s *Server) handleListAudioDevices() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// Only allow GET method
		if r.Method != http.MethodGet {
			w.WriteHeader(http.StatusMethodNotAllowed)
			return
		}

		s.logger.Info("Listing audio devices")

		devices, err := audiocapture.ListAudioDevices()
		if err != nil {
			s.logger.Error("Failed to list audio devices", "error", err)
			s.respondWithJSON(w, http.StatusInternalServerError, map[string]string{
				"error": fmt.Sprintf("Failed to list audio devices: %v", err),
			})
			return
		}

		s.respondWithJSON(w, http.StatusOK, map[string]interface{}{
			"status":  "success",
			"devices": devices,
		})
	}
}

// respondWithJSON sends a JSON response
func (s *Server) respondWithJSON(w http.ResponseWriter, status int, payload interface{}) {
	response, err := json.Marshal(payload)
	if err != nil {
		w.WriteHeader(http.StatusInternalServerError)
		w.Write([]byte("Internal Server Error"))
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	w.Write(response)
}

// Start initializes the server and starts listening for requests
func (s *Server) Start() error {
	addr := ":8000"

	// Create the HTTP server
	s.server = &http.Server{
		Addr:         addr,
		Handler:      s.router,
		ReadTimeout:  10 * time.Second,
		WriteTimeout: 10 * time.Second,
		IdleTimeout:  120 * time.Second,
	}

	// Channel to listen for errors coming from the server
	serverErrors := make(chan error, 1)

	// Start the server in a goroutine
	go func() {
		s.logger.Info("API server listening on %s", "addr", addr)
		serverErrors <- s.server.ListenAndServe()
	}()

	// Channel to listen for an interrupt or terminate signal from the OS
	shutdown := make(chan os.Signal, 1)
	signal.Notify(shutdown, os.Interrupt, syscall.SIGTERM)

	// Block until there's an error or a signal
	select {
	case err := <-serverErrors:
		s.logger.Error("Server error:", "error", err)
		return fmt.Errorf("server error: %w", err)

	case <-shutdown:
		s.logger.Info("Received shutdown signal, shutting down server...")

		// Create a context with a timeout to allow for graceful shutdown
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		// Attempt graceful shutdown
		if err := s.server.Shutdown(ctx); err != nil {
			// Force immediate shutdown if graceful shutdown fails
			s.server.Close()
			s.logger.Error("Could not gracefully shutdown the server, forcing immediate shutdown", "error", err)
			return fmt.Errorf("could not gracefully shutdown the server: %w", err)
		}

		s.logger.Info("Server shutdown complete")
	}

	return nil
}
