package transcriber

import (
	"time"

	"github.com/google/uuid"
	"github.com/martijnspitter/transcriber/internal/logger"
	"github.com/martijnspitter/transcriber/internal/types"
)

type Transcriber struct {
	meeting *types.Meeting
	logger  *logger.Logger
}

func NewTranscriber(logger *logger.Logger) *Transcriber {
	return &Transcriber{
		logger: logger,
	}
}

func (t *Transcriber) CreateMeeting(participants []string) string {
	t.meeting = &types.Meeting{
		Id:            uuid.NewString(),
		Title:         "New Meeting",
		CreatedAt:     time.Now(),
		Start_time:    time.Now(),
		Status:        string(types.MeetingStatusRecording),
		Participants:  participants,
		Audio_devices: []types.AudioDevice{}, // Initialize with empty slice instead of nil
	}

	return t.meeting.Id
}

func (t *Transcriber) StopMeeting(meetingId string) {
	if t.meeting == nil || t.meeting.Id != meetingId {
		return
	}

	t.meeting.Status = string(types.MeetingStatusCompleted)
	t.meeting.Duration = int(time.Since(t.meeting.Start_time).Seconds())

}
