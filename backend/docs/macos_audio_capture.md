# macOS Audio Capture: Simultaneous Microphone and System Sound

## Background

Capturing both microphone input and system audio output simultaneously on macOS presents several challenges due to the operating system's security and permissions model. This document explains the implementation approach we've taken to solve this problem.

## The Challenge

Traditional audio capture libraries like `sounddevice` or `PyAudio` are limited in their ability to capture system audio on macOS. This is because:

1. **Security Restrictions**: macOS restricts access to system audio output
2. **Permission Model**: Capturing system audio requires special permissions
3. **Hardware Limitations**: Standard audio APIs don't provide easy access to both input and output streams simultaneously

The previous implementation relied on virtual audio devices (like BlackHole or Soundflower) which:
- Required manual installation of third-party software
- Needed complex audio routing setup
- Created feedback loops when trying to use both mic and system audio
- Were unreliable across different macOS versions

## Our Solution: Core Audio APIs

The new implementation uses Apple's native Core Audio APIs via PyObjC to directly access both microphone input and system audio output. This approach:

1. Requires proper permission requests
2. Uses native macOS frameworks
3. Avoids the need for virtual audio devices
4. Works reliably across macOS versions

## Implementation Details

### Key Components

- **PyObjC**: Provides Python bindings for Objective-C frameworks
- **AVFoundation**: Handles audio device access and permissions
- **Core Audio**: Low-level API for audio capture
- **Audio Units**: Used for system audio capture

### Permission Requirements

To use the macOS audio capture feature, the application needs:

1. **Microphone Permission**: Standard microphone access
2. **Screen Recording Permission**: Required for system audio capture (yes, this is counter-intuitive but necessary)

The application will prompt for these permissions when first used.

## Usage

The `MacOSAudioCaptureService` is automatically used when running on macOS. The `AudioManager` class handles platform detection and service selection.

### Checking System Audio Availability

```python
from app.services.audio_manager import AudioManager

audio_manager = AudioManager()
supports_both = audio_manager.supports_simultaneous_capture()
```

### Starting Recording with Both Microphone and System Audio

```python
# Start recording with system audio enabled
success, message = audio_manager.start_recording(
    recording_id="meeting123",
    capture_system_audio=True
)
```

## Troubleshooting

### Common Issues

1. **Missing Permissions**:
   - Make sure the application has both Microphone and Screen Recording permissions in System Preferences > Security & Privacy > Privacy
   - For CLI applications, grant permissions to Terminal.app

2. **PyObjC Dependencies**:
   - Ensure all PyObjC dependencies are installed with: `pip install -r requirements.txt`

3. **Audio Not Being Captured**:
   - Check active recording status with `audio_manager.get_service_info()`
   - Verify your microphone is working in other applications

### Debugging

When audio capture issues occur, check the application logs for messages from:
- `MacOSAudioCaptureService`
- Core Audio permission errors
- AVFoundation initialization failures

## Limitations

1. **Limited Control**: Fine-grained control over audio levels is not yet implemented
2. **macOS Version Differences**: The API behavior may vary slightly between macOS versions
3. **Speaker Recognition**: Speaker diarization is not handled in the audio capture layer

## Future Improvements

1. Advanced audio mixing capabilities
2. Per-channel audio level adjustment
3. Audio processing filters
4. Device hot-swapping without restarting recording
5. Better error recovery for temporary audio interruptions
