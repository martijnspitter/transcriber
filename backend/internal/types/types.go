package types

import "time"

type MeetingStatus string

const (
	MeetingStatusRecording         MeetingStatus = "recording"
	MeetingStatusProcessing        MeetingStatus = "processing"
	MeetingStatusRecordingCreated  MeetingStatus = "recording_created"
	MeetingStatusTranscriptCreated MeetingStatus = "transcript_created"
	MeetingStatusSummaryCreated    MeetingStatus = "summary_created"
	MeetingStatusCompleted         MeetingStatus = "completed"
	MeetingStatusFailed            MeetingStatus = "failed"
)

type Meeting struct {
	Id              string        `json:"id"`
	Title           string        `json:"title"`
	Status          string        `json:"status"`
	CreatedAt       time.Time     `json:"created_at"`
	Start_time      time.Time     `json:"start_time"`
	Participants    []string      `json:"participants"`
	Transcript_path string        `json:"transcript_path"`
	Duration        int           `json:"duration"` // in seconds
	Audio_devices   []AudioDevice `json:"audio_devices"`
	Transcript      string        `json:"transcript,omitempty"` // Optional, can be empty if not transcribed
	Summary         string        `json:"summary,omitempty"`    // Optional, can be empty if not summarized
	Error           string        `json:"error,omitempty"`      // Error message if processing failed
}

type AudioDevice struct {
	ID        uint32 `json:"id"`
	Name      string `json:"name"`
	Channels  int    `json:"channels"`
	IsInput   bool   `json:"is_input"`
	IsOutput  bool   `json:"is_output"`
	IsSystem  bool   `json:"is_system"`
	IsDefault bool   `json:"is_default"`
}
