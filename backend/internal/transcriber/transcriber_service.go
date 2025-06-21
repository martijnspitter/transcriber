package transcriber

import (
	"fmt"
	"os"
	"time"

	"github.com/google/uuid"
	"github.com/martijnspitter/transcriber/internal/audio_capture"
	"github.com/martijnspitter/transcriber/internal/logger"
	osoperations "github.com/martijnspitter/transcriber/internal/os_operations"
	"github.com/martijnspitter/transcriber/internal/types"
)

type TranscriberService struct {
	meeting  *types.Meeting
	logger   *logger.Logger
	recorder *audiocapture.CombinedAudio
	meetings map[string]*types.Meeting
}

func NewTranscriberService(logger *logger.Logger) *TranscriberService {
	return &TranscriberService{
		logger:   logger,
		meetings: make(map[string]*types.Meeting),
	}
}

func (t *TranscriberService) StartRecording(title string, participants []string) (string, error) {
	if title == "" {
		title = "New Meeting"
	}
	timestamp := time.Now()
	meetingID := uuid.NewString()
	t.meeting = &types.Meeting{
		Id:            meetingID,
		Title:         title,
		CreatedAt:     timestamp,
		Start_time:    timestamp,
		Status:        string(types.MeetingStatusRecording),
		Participants:  participants,
		Audio_devices: []types.AudioDevice{}, // Initialize with empty slice instead of nil
	}

	// Store the meeting in the map for later retrieval
	t.meetings[meetingID] = t.meeting

	// Create output filepath
	fileName := osoperations.FormatFileName("recording", t.meeting.CreatedAt, ".wav")
	// Create a temporary output directory
	tempDir, err := osoperations.CreateTempDirectory("recording_output")
	if err != nil {
		return "", fmt.Errorf("failed to create temp directory: %w", err)
	}
	defer osoperations.RemoveTempDirectory(tempDir) // Clean up temp dir when done
	finalFilePath := osoperations.CreateFilePath(tempDir, fileName)

	// Create combined audio capture instance
	audioCapture := audiocapture.NewCombinedAudio(finalFilePath)
	t.recorder = audioCapture

	go func() {
		t.logger.Info("Starting audio capture", "meetingId", t.meeting.Id, "title", t.meeting.Title)

		err := audioCapture.Start()
		if err != nil {
			t.logger.Error("Failed to start audio capture", err)
			return
		}

		t.logger.Info("Audio capture and merge completed successfully",
			"meetingId", t.meeting.Id,
			"file", finalFilePath,
		)

		t.meeting.Transcript_path = finalFilePath
	}()

	return t.meeting.Id, nil
}

func (t *TranscriberService) StopMeeting(meetingId string) error {
	// ===========================================================================
	// Checks
	// ===========================================================================
	if t.meeting == nil || t.meeting.Id != meetingId {
		return fmt.Errorf("no active meeting found with ID: %s", meetingId)
	}
	t.logger.Info("Stopping meeting", "meetingId", meetingId)

	// ===========================================================================
	// Stop the audio recorder
	// ===========================================================================
	if t.recorder != nil {
		t.recorder.Stop()
	}

	// ===========================================================================
	// Update meetign
	// ===========================================================================
	// Store the meeting reference for async processing
	meeting := t.meeting

	// Update status to indicate processing has begun
	meeting.Status = string(types.MeetingStatusProcessing)
	meeting.Duration = int(time.Since(meeting.Start_time).Seconds())

	// Update the meeting in the map
	t.meetings[meetingId] = meeting

	// ===========================================================================
	// Process meeting
	// ===========================================================================
	go func() {
		// Check if the audio file exists
		timeoutCounter := 0
		for timeoutCounter < 10 {
			time.Sleep(1 * time.Second)
			if _, err := os.Stat(meeting.Transcript_path); err == nil {
				break
			}
			timeoutCounter++
		}

		if _, err := os.Stat(meeting.Transcript_path); os.IsNotExist(err) {
			errorMsg := fmt.Sprintf("recording file not created: %s", meeting.Transcript_path)
			t.logger.Error(errorMsg)
			meeting.Status = string(types.MeetingStatusFailed)
			meeting.Error = errorMsg
			t.meetings[meetingId] = meeting
			return
		}

		// ===========================================================================
		// Transcribe meeting
		// ===========================================================================
		transcriber := NewTranscriber(meeting.Transcript_path, t.logger, meeting)
		transcription, err := transcriber.TranscribeAudio()
		if err != nil {
			errorMsg := fmt.Sprintf("failed to transcribe audio: %v", err)
			t.logger.Error(errorMsg, "error", err)
			meeting.Status = string(types.MeetingStatusFailed)
			meeting.Error = errorMsg
			t.meetings[meetingId] = meeting
			return
		}
		meeting.Transcript = transcription

		// ===========================================================================
		// Summarize meeting
		// ===========================================================================
		summary, err := t.Summarize()
		if err != nil {
			errorMsg := fmt.Sprintf("failed to summarize transcription: %v", err)
			t.logger.Error(errorMsg, "error", err)
			meeting.Status = string(types.MeetingStatusFailed)
			meeting.Error = errorMsg
			t.meetings[meetingId] = meeting
			return
		}
		meeting.Summary = summary

		// ===========================================================================
		// Save summary to vault
		// ===========================================================================
		err = osoperations.SaveMeetingToVault(meeting)
		if err != nil {
			errorMsg := fmt.Sprintf("failed to save meeting to vault: %v", err)
			t.logger.Error(errorMsg, "error", err)
			meeting.Status = string(types.MeetingStatusFailed)
			meeting.Error = errorMsg
			t.meetings[meetingId] = meeting
			return
		}

		// Mark as completed if everything went well
		meeting.Status = string(types.MeetingStatusCompleted)
		t.meetings[meetingId] = meeting
		t.logger.Info("Meeting processing completed successfully", "meetingId", meetingId)
	}()

	// Return immediately after starting the processing
	return nil
}

// GetMeetingStatus retrieves the status and details of a meeting by its ID
func (t *TranscriberService) GetMeetingStatus(meetingId string) (*types.Meeting, error) {
	// Check if the requested meeting is the current active meeting
	if t.meeting != nil && t.meeting.Id == meetingId {
		return t.meeting, nil
	}

	// Check if the meeting exists in our meetings map
	if meeting, exists := t.meetings[meetingId]; exists {
		return meeting, nil
	}

	return nil, fmt.Errorf("meeting not found with ID: %s", meetingId)
}

// GetAllMeetings returns all meetings (both active and completed)
func (t *TranscriberService) GetAllMeetings() []*types.Meeting {
	meetings := make([]*types.Meeting, 0, len(t.meetings))

	// Add all meetings from the map
	for _, meeting := range t.meetings {
		meetings = append(meetings, meeting)
	}

	return meetings
}
