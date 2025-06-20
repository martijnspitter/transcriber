package types

import "time"

type MeetingStatus string

const (
	MeetingStatusRecording MeetingStatus = "recording"
	MeetingStatusCompleted MeetingStatus = "completed"
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
