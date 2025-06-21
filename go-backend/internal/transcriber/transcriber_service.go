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
}

func NewTranscriberService(logger *logger.Logger) *TranscriberService {
	return &TranscriberService{
		logger: logger,
	}
}

func (t *TranscriberService) StartRecording(title string, participants []string) (string, error) {
	if title == "" {
		title = "New Meeting"
	}
	timestamp := time.Now()
	t.meeting = &types.Meeting{
		Id:            uuid.NewString(),
		Title:         title,
		CreatedAt:     timestamp,
		Start_time:    timestamp,
		Status:        string(types.MeetingStatusRecording),
		Participants:  participants,
		Audio_devices: []types.AudioDevice{}, // Initialize with empty slice instead of nil
	}

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

func (t *TranscriberService) StopMeeting(meetingId string) (string, error) {
	// ===========================================================================
	// Checks
	// ===========================================================================
	if t.meeting == nil || t.meeting.Id != meetingId {
		return "", fmt.Errorf("no active meeting found with ID: %s", meetingId)
	}
	t.logger.Info("Stopping meeting", "meetingId", meetingId)

	// ===========================================================================
	// Wait for file to be saved
	// ===========================================================================
	if t.recorder != nil {
		t.recorder.Stop()
	}
	timeoutCounter := 0
	for timeoutCounter < 10 {
		time.Sleep(1 * time.Second)
		if _, err := os.Stat(t.meeting.Transcript_path); err == nil {
			break
		}
		timeoutCounter++
	}
	if _, err := os.Stat(t.meeting.Transcript_path); os.IsNotExist(err) {
		return "", fmt.Errorf("recording file not created: %s", t.meeting.Transcript_path)
	}

	// ===========================================================================
	// Update status
	// ===========================================================================
	t.meeting.Status = string(types.MeetingStatusCompleted)
	t.meeting.Duration = int(time.Since(t.meeting.Start_time).Seconds())

	// ===========================================================================
	// Transcribe meeting
	// ===========================================================================
	transcriber := NewTranscriber(t.meeting.Transcript_path, t.logger, t.meeting)
	transcription, err := transcriber.TranscribeAudio()
	if err != nil {
		t.logger.Error("Failed to transcribe audio", err)
		return "", fmt.Errorf("failed to transcribe audio: %w", err)
	}
	t.meeting.Transcript = transcription

	// ===========================================================================
	// Summarize meeting
	// ===========================================================================
	summary, err := t.Summarize()
	if err != nil {
		t.logger.Error("Failed to summarize transcription", err)
		return "", fmt.Errorf("failed to summarize transcription: %w", err)
	}
	t.meeting.Summary = summary

	// ===========================================================================
	// Save summary to vault
	// ===========================================================================
	err = osoperations.SaveMeetingToVault(t.meeting)
	if err != nil {
		t.logger.Error("Failed to save meeting to vault", err)
		return "", fmt.Errorf("failed to save meeting to vault: %w", err)
	}

	// ===========================================================================
	// Return
	// ===========================================================================
	return summary, nil
}
