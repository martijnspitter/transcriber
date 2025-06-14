import platform
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

class AudioManager:
    """
    Audio Manager that selects and initializes the appropriate audio capture service
    based on the current platform and available dependencies.
    """

    def __init__(self, sample_rate=16000, output_dir=None):
        """
        Initialize the Audio Manager with the appropriate audio capture service.

        Args:
            sample_rate (int): The sample rate to use for audio recording (default: 16000)
            output_dir (str): Directory to store temporary files (default: None, uses ~/Documents/Meeting_Transcripts)
        """
        self.system = platform.system()

        # Set up output directory
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = os.path.expanduser("~/Documents/Meeting_Transcripts")

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # Initialize the appropriate audio capture service
        self.audio_service = self._init_audio_service(sample_rate, self.output_dir)

    def _init_audio_service(self, sample_rate, output_dir):
        """
        Initialize and return the appropriate audio capture service based on platform.

        Args:
            sample_rate (int): The sample rate to use for audio recording
            output_dir (str): Directory to store temporary files

        Returns:
            object: An instance of the appropriate audio capture service
        """
        if self.system == "Darwin":  # macOS
            try:
                from .macos_audio_capture import MacOSAudioCaptureService
                logger.info("Using MacOS-specific audio capture service")
                return MacOSAudioCaptureService(sample_rate, output_dir)
            except ImportError as e:
                logger.warning(f"Could not import MacOSAudioCaptureService: {e}")
                logger.info("Falling back to generic audio capture service")
                from .audio_capture import AudioCaptureService
                return AudioCaptureService(sample_rate, output_dir)
        else:
            # For Windows, Linux, and other platforms, use the standard service
            from .audio_capture import AudioCaptureService
            logger.info(f"Using standard audio capture service for {self.system}")
            return AudioCaptureService(sample_rate, output_dir)

    def __getattr__(self, name):
        """
        Delegate method calls to the underlying audio service.
        This allows the AudioManager to be used as a drop-in replacement
        for any audio capture service.

        Args:
            name (str): The name of the attribute/method to access

        Returns:
            Various: The requested attribute or method from the audio service
        """
        return getattr(self.audio_service, name)

    def get_service_info(self):
        """
        Get information about the current audio service.

        Returns:
            dict: Information about the current audio service
        """
        return {
            "platform": self.system,
            "service_type": self.audio_service.__class__.__name__,
            "output_dir": self.output_dir,
            "system_audio_available": self.audio_service.system_audio_available
        }

    def supports_simultaneous_capture(self):
        """
        Check if the current service supports simultaneous capture of
        microphone and system audio.

        Returns:
            bool: True if simultaneous capture is supported, False otherwise
        """
        # MacOS service supports simultaneous capture
        return self.system == "Darwin" and \
               self.audio_service.__class__.__name__ == "MacOSAudioCaptureService" and \
               self.audio_service.system_audio_available
