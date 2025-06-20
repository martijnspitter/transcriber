package audiocapture

import (
	"fmt"
	"os"
	"os/exec"
	"strings"
	"time"
)

type CombinedAudio struct {
	inputAudio  *InputAudio
	outputAudio *OutputAudio
	duration    int
	stopChan    chan struct{}
	outputPath  string
}

func NewCombinedAudio(duration int, outputPath string) *CombinedAudio {
	inputOptions := InputOptions{
		OutputPath: "input.wav",
		Duration:   duration,
	}
	outputOptions := OutputAudioOptions{
		OutputPath: "output.wav",
		Duration:   duration,
	}

	InputAudio := NewInputAudio(inputOptions)
	OutputAudio := NewOutputAudio(outputOptions)

	return &CombinedAudio{
		inputAudio:  InputAudio,
		outputAudio: OutputAudio,
		duration:    duration,
		stopChan:    make(chan struct{}),
		outputPath:  outputPath,
	}
}

// Start begins the combined audio capture process
func (ca *CombinedAudio) Start() error {
	if ca.inputAudio.isRecording || ca.outputAudio.isRecording {
		return fmt.Errorf("recording already in progress")
	}

	// Get the audio devices for logging
	devices, _ := ListAudioDevices()
	if len(devices) > 0 {
		fmt.Println("Available audio devices before recording:")
		for _, device := range devices {
			fmt.Println(device)
		}
	}

	// Start the recordings in separate goroutines
	micDone := make(chan error, 1)
	outputDone := make(chan error, 1)

	// Start mic recording
	go func() {
		err := ca.inputAudio.Start()
		micDone <- err
	}()

	// Start system audio recording
	go func() {
		err := ca.outputAudio.Start()
		outputDone <- err
	}()

	// Set up merge process to run after both recordings finish
	go func() {
		// Create wait channel for duration-based recording
		var waitChan <-chan time.Time
		if ca.duration > 0 {
			waitChan = time.After(time.Duration(ca.duration+1) * time.Second)
			<-waitChan
		} else {
			// For manual stopping, wait for the stop signal
			<-ca.stopChan
		}

		// Wait for both recordings to complete
		err1 := <-micDone
		err2 := <-outputDone

		// Check for errors
		if err1 != nil && err2 != nil {
			fmt.Printf("Error recording audio: mic error: %v, output error: %v\n", err1, err2)
			return
		}

		// Now mix the two audio files together
		mixArgs := []string{
			"-i", ca.inputAudio.outputPath,
			"-i", ca.outputAudio.outputPath,
			"-filter_complex", "amix=inputs=2:duration=longest:dropout_transition=2", // Mix the audio streams
			"-ac", "2", // Output stereo
			"-ar", fmt.Sprintf("%d", ca.inputAudio.options.SampleRate),
			"-c:a", "pcm_s16le", // Output as PCM
			"-y", // Overwrite existing file
			ca.outputPath,
		}

		fmt.Printf("Running audio mix command: ffmpeg %s\n", strings.Join(mixArgs, " "))

		// Execute the mix command
		mixCmd := exec.Command("ffmpeg", mixArgs...)
		mixCmd.Stderr = os.Stderr
		err := mixCmd.Run()

		if err != nil {
			fmt.Printf("Error mixing audio: %v\n", err)
		} else {
			// Clean up temp files if successful
			os.Remove(ca.inputAudio.outputPath)
			os.Remove(ca.outputAudio.outputPath)
			fmt.Printf("Successfully mixed audio to %s\n", ca.outputPath)
		}
	}()

	return nil
}

// Stop stops the ongoing recording
func (ca *CombinedAudio) Stop() error {
	if !ca.inputAudio.isRecording && !ca.outputAudio.isRecording {
		return fmt.Errorf("no recording in progress")
	}

	// Stop input audio recording
	if err := ca.inputAudio.Stop(); err != nil {
		return fmt.Errorf("failed to stop input audio: %w", err)
	}

	// Stop output audio recording
	if err := ca.outputAudio.Stop(); err != nil {
		return fmt.Errorf("failed to stop output audio: %w", err)
	}

	// Send stop signal
	close(ca.stopChan)

	// Create a new channel for next recording
	ca.stopChan = make(chan struct{})

	return nil
}

// GetOutputPath returns the path to the recorded file
func (ca *CombinedAudio) GetOutputPath() string {
	return ca.outputPath
}

// IsRecording returns whether a recording is currently in progress
func (ca *CombinedAudio) IsRecording() bool {
	return ca.inputAudio.IsRecording() || ca.outputAudio.IsRecording()
}
