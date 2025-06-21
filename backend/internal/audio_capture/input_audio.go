package audiocapture

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// InputOptions defines the options for audio capture
type InputOptions struct {
	OutputPath string // Where to save the WAV file (if empty, a default path will be used)
	Duration   int    // Duration in seconds (0 means until Stop() is called)
	SampleRate int    // Sample rate in Hz (default: 44100)
}

// InputAudio manages audio capture operations
type InputAudio struct {
	cmd         *exec.Cmd
	options     InputOptions
	outputPath  string
	isRecording bool
	stopChan    chan struct{}
}

// NewInputAudio creates a new audio capture instance
func NewInputAudio(options InputOptions) *InputAudio {
	// Set defaults if not provided
	if options.SampleRate <= 0 {
		options.SampleRate = 44100
	}

	outputPath := options.OutputPath

	return &InputAudio{
		options:    options,
		outputPath: outputPath,
		stopChan:   make(chan struct{}),
	}
}

// Start begins the audio capture process
func (ac *InputAudio) Start() error {
	if ac.isRecording {
		return fmt.Errorf("recording already in progress")
	}

	var args []string

	// Construct ffmpeg command - always use microphone which will pick up system audio too
	args = []string{
		"-f", "avfoundation",
		"-i", ":2", // Use MacBook Pro Microphone (index 2 from device list)
		"-ac", "2", // Stereo audio
		"-ar", "44100", // Standard sample rate
		// Simple audio enhancement filters
		"-af", "volume=1.5",
		"-y", // Overwrite output file if it exists
		ac.outputPath,
	}

	// Add duration limit if specified
	if ac.options.Duration > 0 {
		args = append([]string{"-t", fmt.Sprintf("%d", ac.options.Duration)}, args...)
	}

	// Create the command
	ac.cmd = exec.Command("ffmpeg", args...)

	// Print the command for debugging
	fmt.Printf("Running command: ffmpeg %s\n", strings.Join(args, " "))

	// Redirect stderr for debugging (ffmpeg outputs progress to stderr)
	ac.cmd.Stderr = os.Stderr

	// Start the ffmpeg process
	err := ac.cmd.Start()
	if err != nil {
		return fmt.Errorf("failed to start ffmpeg: %w", err)
	}

	ac.isRecording = true

	// If no duration limit is set, we need to handle stopping manually
	if ac.options.Duration <= 0 {
		go func() {
			<-ac.stopChan
			// Signal received to stop recording
			if ac.cmd.Process != nil {
				ac.cmd.Process.Signal(os.Interrupt)
			}
		}()
	}

	// Wait for the command to complete in a goroutine
	go func() {
		ac.cmd.Wait()
		ac.isRecording = false
	}()

	return nil
}

// Stop stops the ongoing recording
func (ac *InputAudio) Stop() error {
	if !ac.isRecording {
		return fmt.Errorf("no recording in progress")
	}

	// Send stop signal
	close(ac.stopChan)

	// Create a new channel for next recording
	ac.stopChan = make(chan struct{})

	return nil
}

// GetOutputPath returns the path to the recorded audio file
func (ac *InputAudio) GetOutputPath() string {
	return ac.outputPath
}

// IsRecording returns whether a recording is currently in progress
func (ac *InputAudio) IsRecording() bool {
	return ac.isRecording
}
