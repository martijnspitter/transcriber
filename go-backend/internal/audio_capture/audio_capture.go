package audiocapture

import (
	"bufio"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"
)

// ListAudioDevices returns a list of available audio input and output devices
// using ffmpeg's avfoundation device enumeration
func ListAudioDevices() ([]string, error) {
	// Run ffmpeg with special device listing argument
	cmd := exec.Command("ffmpeg", "-f", "avfoundation", "-list_devices", "true", "-i", "")

	// Capture stderr because ffmpeg outputs device list to stderr
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, fmt.Errorf("failed to create stderr pipe: %w", err)
	}

	// Start the command
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("failed to start ffmpeg: %w", err)
	}

	// Read and parse the output
	var devices []string
	scanner := bufio.NewScanner(stderr)
	audioDevicePattern := regexp.MustCompile(`\[AVFoundation.+?\] \[(\d+)\] (.+)`)
	isAudioSection := false

	for scanner.Scan() {
		line := scanner.Text()
		// Print the line for debugging
		fmt.Println(line)

		// Check if we've reached the audio devices section
		if strings.Contains(line, "AVFoundation audio devices:") {
			isAudioSection = true
			continue
		}

		// Only process audio devices
		if isAudioSection {
			matches := audioDevicePattern.FindStringSubmatch(line)
			if len(matches) == 3 {
				deviceInfo := fmt.Sprintf("Audio Device %s: %s", matches[1], matches[2])
				devices = append(devices, deviceInfo)
			}
		}
	}

	// Wait for the command to finish
	cmd.Wait() // Ignore error as ffmpeg returns non-zero when using -list_devices

	if len(devices) == 0 {
		return nil, fmt.Errorf("no audio devices found")
	}

	return devices, nil
}

// CaptureAndMergeAudio captures both microphone input and system output audio simultaneously
// and saves it to a combined file
func CaptureAndMergeAudio(durationSeconds int, outputDir string) (string, error) {
	if durationSeconds <= 0 {
		return "", fmt.Errorf("duration must be positive")
	}

	timestamp := time.Now().Format("20060102_150405")

	// List devices for debugging purposes
	devices, _ := ListAudioDevices()
	if len(devices) > 0 {
		fmt.Println("Available audio devices:")
		for _, device := range devices {
			fmt.Println(device)
		}
	}

	// Create output filepath
	finalFilePath := filepath.Join(outputDir, fmt.Sprintf("recording_%s.wav", timestamp))

	// Create combined audio capture instance
	combined := NewCombinedAudio(durationSeconds, finalFilePath)

	// Start combined audio capture
	err := combined.Start()
	if err != nil {
		return "", fmt.Errorf("failed to start audio capture: %w", err)
	}

	fmt.Println("Capturing both microphone and system audio")
	fmt.Printf("Recording for %d seconds to %s\n", durationSeconds, finalFilePath)

	// For duration-based recording, the combined audio recorder handles the wait and mixing process internally
	if combined.IsRecording() && durationSeconds <= 0 {
		// Only manually stop for non-duration recordings
		recordingTime := time.Duration(durationSeconds+1) * time.Second
		fmt.Printf("Waiting %v for recording to complete...\n", recordingTime)
		time.Sleep(recordingTime)

		fmt.Println("Stopping combined audio capture...")
		combined.Stop()
	}

	// Check if file was created - this might need a delay since mixing happens after recording
	timeoutCounter := 0
	for timeoutCounter < 10 {
		time.Sleep(1 * time.Second)
		if _, err := os.Stat(finalFilePath); err == nil {
			break
		}
		timeoutCounter++
	}

	if _, err := os.Stat(finalFilePath); os.IsNotExist(err) {
		return "", fmt.Errorf("recording file not created: %s", finalFilePath)
	}

	return finalFilePath, nil
}
