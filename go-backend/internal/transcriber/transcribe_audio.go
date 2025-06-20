package transcriber

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/martijnspitter/transcriber/internal/logger"
	"github.com/martijnspitter/transcriber/internal/types"
)

type Summary struct {
	audioFilePath string
	summary       string
	logger        *logger.Logger
	meeting       *types.Meeting
}

func NewSummary(audioFilePath string, logger *logger.Logger, meeting *types.Meeting) *Summary {
	return &Summary{
		audioFilePath: audioFilePath,
		summary:       "",
		logger:        logger,
		meeting:       meeting,
	}
}

func (s *Summary) TranscribeAudio() (string, error) {
	// Load audio data
	s.logger.Info("Loading audio file for transcription")

	// Check if meeting data is available
	if s.meeting == nil {
		return "", fmt.Errorf("meeting data not provided")
	}
	// Create a temporary output file for the transcription
	tempDir := os.TempDir()
	outputFile := filepath.Join(tempDir, "transcription.txt")

	// Prepare the whisper command
	// Adjust model size as needed: tiny, base, small, medium, large
	modelSize := "base"
	cmd := exec.Command("whisper",
		s.audioFilePath,
		"--model", modelSize,
		"--language", "en",
		"--output_dir", tempDir)

	// Run the whisper command
	output, err := cmd.CombinedOutput()
	if err != nil {
		s.logger.Error("Whisper transcription failed", err)
		s.logger.Error("Command output", string(output))
		return "", fmt.Errorf("whisper transcription failed: %w", err)
	}

	// Read the transcription output
	transcriptionText, err := os.ReadFile(outputFile)
	if err != nil {
		return "", fmt.Errorf("failed to read transcription output: %w", err)
	}

	// Parse the transcription to extract segments with timestamps
	// Note: Whisper's output format might vary, so this parsing logic
	// might need adjustment based on the actual output format
	segments := parseWhisperOutput(string(transcriptionText))

	// Create markdown header with meeting info
	header := fmt.Sprintf("# %s\n\n", s.meeting.Title)
	header += fmt.Sprintf("**Date:** %s\n\n", s.meeting.CreatedAt.Format("January 2, 2006"))
	header += fmt.Sprintf("**Duration:** %d minutes %d seconds\n\n", s.meeting.Duration/60, s.meeting.Duration%60)

	if len(s.meeting.Participants) > 0 {
		header += "**Participants:**\n"
		for _, participant := range s.meeting.Participants {
			header += fmt.Sprintf("- %s\n", participant)
		}
		header += "\n"
	}

	header += "## Transcript\n\n"

	// Generate transcript with the formatted segments
	var transcript strings.Builder
	transcript.WriteString(header)
	transcript.WriteString(string(transcriptionText))

	// Add timestamps to each segment
	for _, segment := range segments {
		// timestamp := formatTimestamp(segment.Start)
		transcript.WriteString(fmt.Sprintf("%s\n\n", segment))
	}

	s.summary = transcript.String()

	// Generate output filename based on meeting title and date
	baseFileName := strings.ReplaceAll(s.meeting.Title, " ", "_")
	timestamp := s.meeting.CreatedAt.Format("20060102_150405")
	transcriptFileName := fmt.Sprintf("%s_%s_transcript.md", baseFileName, timestamp)
	transcriptFilePath := filepath.Join("./", transcriptFileName)

	// Write transcript to file
	if err := os.WriteFile(transcriptFilePath, []byte(s.summary), 0644); err != nil {
		return "", fmt.Errorf("failed to write transcript to file: %w", err)
	}

	s.logger.Info("Transcription completed")
	return s.summary, nil
}

// formatTimestamp converts seconds to MM:SS format
func formatTimestamp(timestamp time.Duration) string {
	return timestamp.String()
}

func parseWhisperOutput(text string) []string {
	// Split the text into segments (this is simplified)
	return strings.Split(text, "\n\n")
}
