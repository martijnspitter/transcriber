package audiocapture

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)

type OutputAudioOptions struct {
	OutputPath string // Where to save the recording
	Duration   int    // Duration in seconds (0 means until Stop() is called)
}

// OutputAudio manages system audio recording
type OutputAudio struct {
	cmd         *exec.Cmd
	options     OutputAudioOptions
	outputPath  string
	isRecording bool
	stopChan    chan struct{}
}

func NewOutputAudio(options OutputAudioOptions) *OutputAudio {
	outputPath := options.OutputPath

	return &OutputAudio{
		options:    options,
		outputPath: outputPath,
		stopChan:   make(chan struct{}),
	}
}

// Start begins the system audio recording process
func (sr *OutputAudio) Start() error {
	if sr.isRecording {
		return fmt.Errorf("recording already in progress")
	}

	deviceIndex := 1

	// Use ffmpeg to capture desktop audio
	// This uses the avfoundation input for system audio
	// For audio-only capture in avfoundation, use "none:deviceIndex" format
	args := []string{
		"-f", "avfoundation",
		"-i", fmt.Sprintf("none:%d", deviceIndex), // Using the specified device index for system audio
		"-ac", "2", // Stereo
		"-ar", "48000", // 44.1 kHz sample rate (standard for audio)
		"-thread_queue_size", "4096", // Increase buffer size to prevent buffer underruns
		"-max_delay", "500000", // 0.5 second maximum delay
		"-buffer_size", "1024k", // Larger buffer size
	}

	// Add duration if specified
	if sr.options.Duration > 0 {
		args = append(args, "-t", fmt.Sprintf("%d", sr.options.Duration))
	}

	// Add output format and path with better quality settings
	args = append(args,
		"-c:a", "pcm_s24le", // Use high quality PCM audio codec
		"-af", "aresample=resampler=soxr:precision=28:osf=s32", // High quality resampler
		"-y", // Overwrite existing file
		sr.outputPath,
	)

	// Print the command for debugging
	fmt.Printf("Running system audio capture command: ffmpeg %s\n", strings.Join(args, " "))

	// Create the command
	sr.cmd = exec.Command("ffmpeg", args...)

	// Redirect stderr for logging
	sr.cmd.Stderr = os.Stderr

	// Start the recording
	if err := sr.cmd.Start(); err != nil {
		return fmt.Errorf("failed to start system audio recording: %w", err)
	}

	sr.isRecording = true

	// If no duration limit is set, we need to handle stopping manually
	if sr.options.Duration <= 0 {
		go func() {
			<-sr.stopChan
			if sr.cmd.Process != nil {
				sr.cmd.Process.Signal(os.Interrupt)
			}
		}()
	}

	// Wait for the command to complete in a goroutine
	go func() {
		sr.cmd.Wait()
		sr.isRecording = false
	}()

	return nil
}

// Stop stops the ongoing system audio recording
func (sr *OutputAudio) Stop() error {
	if !sr.isRecording {
		return fmt.Errorf("no recording in progress")
	}

	// Send stop signal
	close(sr.stopChan)

	// Create a new channel for next recording
	sr.stopChan = make(chan struct{})

	return nil
}

// GetOutputPath returns the path to the recorded file
func (sr *OutputAudio) GetOutputPath() string {
	return sr.outputPath
}

// IsRecording returns whether a recording is currently in progress
func (sr *OutputAudio) IsRecording() bool {
	return sr.isRecording
}
