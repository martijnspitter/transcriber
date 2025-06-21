package transcriber

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/martijnspitter/transcriber/internal/logger"
	osoperations "github.com/martijnspitter/transcriber/internal/os_operations"
	"github.com/martijnspitter/transcriber/internal/types"
)

type Transcriber struct {
	audioFilePath string
	summary       string
	logger        *logger.Logger
	meeting       *types.Meeting
}

func NewTranscriber(audioFilePath string, logger *logger.Logger, meeting *types.Meeting) *Transcriber {
	return &Transcriber{
		audioFilePath: audioFilePath,
		summary:       "",
		logger:        logger,
		meeting:       meeting,
	}
}

func (s *Transcriber) TranscribeAudio() (string, error) {
	// Check if meeting data is available
	if s.meeting == nil {
		return "", fmt.Errorf("meeting data not provided")
	}
	s.logger.Info("Starting transcription using OpenAI Whisper")

	// Get just the filename without extension for output file naming
	audioFileNameWithoutExt := osoperations.GetFileNameWithoutExtension(s.audioFilePath)

	// Create a temporary output directory
	tempDir, err := osoperations.CreateTempDirectory("whisper_output")
	if err != nil {
		return "", fmt.Errorf("failed to create temp directory: %w", err)
	}
	defer osoperations.RemoveTempDirectory(tempDir) // Clean up temp dir when done

	// Prepare the whisper command
	// Adjust model size as needed: tiny, base, small, medium, large, turbo
	modelSize := "medium"
	cmd := exec.Command("whisper",
		s.audioFilePath,
		"--model", modelSize,
		"--language", "en",
		"--output_dir", tempDir,
		"--output_format", "srt", // Use SRT format to get timestamps
		"--verbose", "False")

	// Run the whisper command
	output, err := cmd.CombinedOutput()
	if err != nil {
		s.logger.Error("Whisper transcription failed", err)
		s.logger.Error("Command output", string(output))

		// List the directory contents for debugging
		files, _ := os.ReadDir(tempDir)
		fileList := "Files in output directory: "
		for _, file := range files {
			fileList += file.Name() + ", "
		}
		s.logger.Info(fileList)

		return "", fmt.Errorf("whisper transcription failed: %w\nOutput: %s", err, string(output))
	}

	// Whisper will save the txt file with the same base name as the input file
	expectedOutputFile := filepath.Join(tempDir, audioFileNameWithoutExt+".srt")

	// Check if the expected file exists
	if _, err := os.Stat(expectedOutputFile); os.IsNotExist(err) {
		// Try to find any .txt file in the directory if the expected one doesn't exist
		files, _ := os.ReadDir(tempDir)
		found := false
		for _, file := range files {
			if strings.HasSuffix(file.Name(), ".srt") {
				expectedOutputFile = filepath.Join(tempDir, file.Name())
				found = true
				break
			}
		}

		if !found {
			s.logger.Error("No transcription file found", nil)
			fileList := "Files in output directory: "
			files, _ := os.ReadDir(tempDir)
			for _, file := range files {
				fileList += file.Name() + ", "
			}
			s.logger.Info(fileList)
			return "", fmt.Errorf("no transcription file found in output directory")
		}
	}

	// Parse the SRT file to extract segments with timestamps
	segments, err := parseSRTFile(expectedOutputFile)
	if err != nil {
		return "", fmt.Errorf("failed to parse SRT file: %w", err)
	}

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

	// Add timestamps to each segment
	for _, segment := range segments {
		transcript.WriteString(fmt.Sprintf("[%s --> %s] %s\n", segment.startTime, segment.endTime, segment.text))
	}

	s.summary = transcript.String()

	s.logger.Info("Transcription completed")
	return s.summary, nil
}

type Segment struct {
	startTime string
	endTime   string
	text      string
}

func parseSRTFile(filePath string) ([]Segment, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var segments []Segment
	scanner := bufio.NewScanner(file)

	var currentSegment Segment
	var isReadingText bool
	var textLines []string

	// Regular expression to match SRT timestamp line (e.g., "00:00:00,000 --> 00:00:05,000")
	timestampRegex := regexp.MustCompile(`(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})`)

	for scanner.Scan() {
		line := scanner.Text()

		// Check if this is a timestamp line
		matches := timestampRegex.FindStringSubmatch(line)
		if len(matches) > 0 {
			// Found timestamp line, start a new segment
			isReadingText = true
			currentSegment = Segment{
				startTime: matches[1],
				endTime:   matches[2],
			}
			textLines = []string{}
			continue
		}

		// If line is empty and we were reading text, end of segment
		if line == "" && isReadingText && len(textLines) > 0 {
			currentSegment.text = strings.Join(textLines, " ")
			segments = append(segments, currentSegment)
			isReadingText = false
			continue
		}

		// If we're in text mode and line isn't a number (segment number), add to text
		if isReadingText && !isNumeric(line) {
			textLines = append(textLines, line)
		}
	}

	// Check for any error that occurred during scanning
	if err := scanner.Err(); err != nil {
		return nil, err
	}

	// Add the last segment if there's text
	if isReadingText && len(textLines) > 0 {
		currentSegment.text = strings.Join(textLines, " ")
		segments = append(segments, currentSegment)
	}

	return segments, nil
}

// isNumeric checks if a string is a numeric value
func isNumeric(s string) bool {
	for _, r := range s {
		if r < '0' || r > '9' {
			return false
		}
	}
	return len(s) > 0
}
