package transcriber

import (
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/google/uuid"
	"github.com/martijnspitter/transcriber/internal/audio_capture"
	"github.com/martijnspitter/transcriber/internal/logger"
	"github.com/martijnspitter/transcriber/internal/types"
)

type Transcriber struct {
	meeting  *types.Meeting
	logger   *logger.Logger
	recorder *audiocapture.CombinedAudio
}

func NewTranscriber(logger *logger.Logger) *Transcriber {
	return &Transcriber{
		logger: logger,
	}
}

func (t *Transcriber) StartRecording(title string, participants []string) (string, error) {
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
	finalFilePath := filepath.Join("./", fmt.Sprintf("recording_%s.wav", t.meeting.CreatedAt.Format("20060102_150405")))

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

func (t *Transcriber) StopMeeting(meetingId string) (string, error) {
	if t.meeting == nil || t.meeting.Id != meetingId {
		return "", fmt.Errorf("no active meeting found with ID: %s", meetingId)
	}
	t.logger.Info("Stopping meeting", "meetingId", meetingId)

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

	t.meeting.Status = string(types.MeetingStatusCompleted)
	t.meeting.Duration = int(time.Since(t.meeting.Start_time).Seconds())

	summarizer := NewSummary(t.meeting.Transcript_path, t.logger, t.meeting)

	summary, err := summarizer.TranscribeAudio()
	if err != nil {
		t.logger.Error("Failed to transcribe audio", err)
		return "", fmt.Errorf("failed to transcribe audio: %w", err)
	}
	t.logger.Debug("summary", summary)

	return t.meeting.Transcript_path, nil
}
