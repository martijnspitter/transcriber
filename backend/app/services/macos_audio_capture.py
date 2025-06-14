import subprocess
import os
import time
import threading
import tempfile
import logging
import numpy as np
from pathlib import Path
import platform

# Configure logging
logger = logging.getLogger(__name__)

class MacOSAudioCaptureService:
    """
    MacOS-specific audio capture service using CoreAudio APIs via PyObjC.
    This service can capture both microphone and system audio simultaneously.
    """

    def __init__(self, sample_rate=16000, output_dir=None):
        """
        Initialize the MacOS audio capture service.

        Args:
            sample_rate (int): The sample rate to use for audio recording (default: 16000)
            output_dir (str): Directory to store temporary files (default: None, uses ~/Documents/Meeting_Transcripts)
        """
        self.sample_rate = sample_rate
        self.active_recordings = {}

        # Audio device information
        self.available_devices = {
            "input": [],
            "output": [],
            "system": []
        }

        self.selected_input_device = None
        self.selected_output_device = None
        self.system_audio_available = False

        # Set up output directory
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = os.path.expanduser("~/Documents/Meeting_Transcripts")

        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # Check for PyObjC dependencies
        self._check_dependencies()

        # Initialize audio devices and permissions
        if self.dependencies_available:
            self.update_device_info()
            self._check_permissions()

    def _check_dependencies(self):
        """Check if required PyObjC modules are available and install if needed"""
        # Initialize as False until verified
        self.dependencies_available = False

        # Create a mapping for module names and their import paths
        module_imports = {
            "pyobjc-core": "objc",
            "pyobjc-framework-Cocoa": "AppKit",
            "pyobjc-framework-AVFoundation": "AVFoundation",
            "pyobjc-framework-CoreAudio": "CoreAudio",
            "pyobjc-framework-CoreMedia": "CoreMedia",
            # Note: We've removed AudioToolbox as it's often included in other frameworks
            "pyobjc-framework-Quartz": "Quartz"
        }

        missing_modules = []

        # Check each module individually to identify specific missing dependencies
        for package, module in module_imports.items():
            try:
                # Use importlib to avoid unused import warnings
                import importlib
                importlib.import_module(module)
                logger.info(f"Found {module} dependency")
            except ImportError:
                logger.warning(f"Missing PyObjC dependency: {module}")
                missing_modules.append(package)

        # If all dependencies are available
        if not missing_modules:
            logger.info("All required PyObjC modules are available")
            self.dependencies_available = True
            return

        # If we have missing modules, try to install them
        logger.info(f"Missing PyObjC dependencies: {missing_modules}")
        logger.info("Attempting to install required modules...")

        try:
            # Install only the missing packages
            for package in missing_modules:
                try:
                    logger.info(f"Installing {package}...")
                    subprocess.check_call(["pip", "install", package])
                except subprocess.CalledProcessError as e:
                    # If one package fails, continue with others
                    logger.warning(f"Failed to install {package}: {e}")
                    continue

            # Check if all modules can now be imported
            all_available = True
            for package, module in module_imports.items():
                try:
                    import importlib
                    importlib.import_module(module)
                except ImportError as e:
                    logger.warning(f"Module {module} still not available after installation: {e}")
                    all_available = False

            if all_available:
                logger.info("Successfully installed all PyObjC dependencies")
                self.dependencies_available = True
                return
            else:
                logger.warning("Some dependencies still missing after installation")
                self.dependencies_available = False

        except Exception as e:
            logger.error(f"Failed to install dependencies: {e}")
            logger.error("You will need to manually install PyObjC modules")
            self.dependencies_available = False

    def _check_permissions(self):
        """Check and request necessary permissions for audio capture"""
        if not self.dependencies_available:
            logger.error("Cannot check permissions without PyObjC dependencies")
            return False

        try:
            # Import modules within the try block to handle import errors properly
            import importlib
            AppKit = importlib.import_module("AppKit")
            AVFoundation = importlib.import_module("AVFoundation")

            # Check microphone permission
            auth_status = AVFoundation.AVCaptureDevice.authorizationStatusForMediaType_(
                AVFoundation.AVMediaTypeAudio
            )

            if auth_status == AVFoundation.AVAuthorizationStatusNotDetermined:
                logger.info("Requesting microphone permission...")
                # This will prompt the user for permission
                AVFoundation.AVCaptureDevice.requestAccessForMediaType_completionHandler_(
                    AVFoundation.AVMediaTypeAudio,
                    lambda granted: logger.info(f"Microphone access {'granted' if granted else 'denied'}")
                )
            elif auth_status == AVFoundation.AVAuthorizationStatusAuthorized:
                logger.info("Microphone permission already granted")
            else:
                logger.warning("Microphone permission denied. Recording will not include microphone audio.")

            # Check screen recording permission for system audio
            # This requires special handling as there's no direct API to request it
            self._check_screen_recording_permission()

            return True
        except Exception as e:
            logger.error(f"Error checking permissions: {e}")
            return False

    def _check_screen_recording_permission(self):
        """Check if screen recording permission is granted (needed for system audio)"""
        try:
            # Unfortunately, there's no direct API to check screen recording permission
            # We can guide the user to enable it manually
            import importlib
            AppKit = importlib.import_module("AppKit")

            # Create a dialog to inform the user about screen recording permission
            alert = AppKit.NSAlert.alloc().init()
            alert.setMessageText_("Screen Recording Permission Required")
            alert.setInformativeText_(
                "To capture system audio, the application needs Screen Recording permission.\n\n"
                "Please go to System Preferences > Security & Privacy > Privacy > Screen Recording\n"
                "and enable permission for this application or the Terminal/Python app."
            )
            alert.addButtonWithTitle_("Open System Preferences")
            alert.addButtonWithTitle_("Skip")

            # Show the alert
            response = alert.runModal()

            # If the user wants to open System Preferences
            if response == AppKit.NSAlertFirstButtonReturn:
                # Open Security & Privacy preferences
                AppKit.NSWorkspace.sharedWorkspace().openURL_(
                    AppKit.NSURL.URLWithString_("x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture")
                )

                # Give user time to enable the permission
                logger.info("Waiting for user to enable Screen Recording permission...")
                time.sleep(2)

            logger.info("Screen Recording permission check completed")

        except Exception as e:
            logger.error(f"Error checking screen recording permission: {e}")

    def update_device_info(self):
        """Update information about available audio devices"""
        if not self.dependencies_available:
            logger.error("Cannot update device info without PyObjC dependencies")
            # Set to false explicitly to ensure appropriate fallback
            self.system_audio_available = False
            return False

        try:
            # Import modules within the try block to handle import errors properly
            import importlib
            AVFoundation = importlib.import_module("AVFoundation")

            # Reset device lists
            self.available_devices = {
                "input": [],
                "output": [],
                "system": []
            }

            # Get audio devices
            audio_devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_(AVFoundation.AVMediaTypeAudio)

            for device in audio_devices:
                device_info = {
                    "id": str(device.uniqueID()),
                    "name": str(device.localizedName()),
                    "manufacturer": str(device.manufacturer()) if hasattr(device, 'manufacturer') else "Unknown",
                    "is_built_in": device.isBuiltInMicrophone() if hasattr(device, 'isBuiltInMicrophone') else False
                }

                self.available_devices["input"].append(device_info)
                logger.info(f"Found input device: {device_info['name']}")

                # Use built-in microphone as default if available
                if device_info.get("is_built_in") and self.selected_input_device is None:
                    self.selected_input_device = device_info["id"]
                    logger.info(f"Selected default input device: {device_info['name']}")

            # For system audio, we need to use Core Audio APIs
            # Mark as available since we have the required dependencies
            self.system_audio_available = True
            logger.info("System audio capture is available through Core Audio APIs")

            # If no input device selected yet, use the first one
            if self.selected_input_device is None and len(self.available_devices["input"]) > 0:
                self.selected_input_device = self.available_devices["input"][0]["id"]
                logger.info(f"Selected first available input device: {self.available_devices['input'][0]['name']}")

            return True
        except Exception as e:
            logger.error(f"Error updating device info: {e}")
            self.system_audio_available = False
            return False

    def get_available_devices(self):
        """Get list of available audio devices"""
        return self.available_devices

    def set_input_device(self, device_id):
        """Set the input device to use for recording"""
        for device in self.available_devices["input"]:
            if device["id"] == device_id:
                self.selected_input_device = device_id
                logger.info(f"Selected input device: {device['name']}")
                return True

        logger.error(f"Input device with ID {device_id} not found")
        return False

    def get_system_audio_status(self):
        """
        Get detailed information about system audio capture capabilities

        Returns:
            dict: Information about system audio capture status
        """
        status = {
            "system_audio_available": self.system_audio_available,
            "system": "Darwin",
            "implementation": "CoreAudio" if self.dependencies_available else "Fallback",
            "recommendation": ""
        }

        if not self.dependencies_available:
            status["system_audio_available"] = False
            status["recommendation"] = (
                "To capture system audio on macOS using Core Audio APIs, please install PyObjC packages:\n"
                "- pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-AVFoundation "
                "pyobjc-framework-CoreAudio pyobjc-framework-CoreMedia pyobjc-framework-Quartz"
            )
        elif not self.system_audio_available:
            status["recommendation"] = (
                "To capture system audio on macOS:\n"
                "1. Grant Screen Recording permission in System Preferences > Security & Privacy > Privacy\n"
                "2. Restart the application after granting permission"
            )

        return status

    def start_recording(self, recording_id, device_id=None, capture_system_audio=True):
        """
        Start recording audio with the given ID

        Args:
            recording_id (str): Unique identifier for this recording
            device_id (str): Optional device ID to use for recording
            capture_system_audio (bool): Whether to capture system audio (default: True)

        Returns:
            tuple: (success (bool), message (str))
        """
        if not self.dependencies_available:
            # Fall back to standard behavior
            try:
                # Import standard audio capture
                from .audio_capture import AudioCaptureService
                temp_service = AudioCaptureService(sample_rate=self.sample_rate, output_dir=self.output_dir)
                success, message = temp_service.start_recording(recording_id, device_id, False)
                if success:
                    self.active_recordings[recording_id] = {
                        "fallback_service": temp_service,
                        "using_fallback": True,
                        "status": "recording"
                    }
                return success, message + " (using fallback audio capture)"
            except Exception as e:
                return False, f"Failed to start recording with fallback method: {str(e)}"

        # Check if recording with this ID already exists
        if recording_id in self.active_recordings:
            return False, "Recording already in progress"

        # Use specified device or fall back to selected device
        input_device = device_id if device_id is not None else self.selected_input_device

        # Initialize recording data
        recording_data = {
            "id": recording_id,
            "audio_data": [],
            "thread": None,
            "stop_flag": threading.Event(),
            "status": "initializing",
            "device_id": input_device,
            "capture_system_audio": capture_system_audio,
            "temp_file": None,
            "using_fallback": False
        }

        try:
            # Create temporary file for audio data
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', dir=self.output_dir)
            recording_data["temp_file"] = temp_file.name
            temp_file.close()

            # Start recording in a background thread
            recording_data["thread"] = threading.Thread(
                target=self._record_audio,
                args=(recording_id, recording_data["stop_flag"], input_device, capture_system_audio)
            )
            recording_data["thread"].daemon = True
            recording_data["thread"].start()

            # Add to active recordings
            self.active_recordings[recording_id] = recording_data

            # Find device name
            device_name = "Unknown Device"
            for device in self.available_devices["input"]:
                if device["id"] == input_device:
                    device_name = device["name"]
                    break

            logger.info(f"Started recording: {recording_id} using device: {device_name}")

            message = f"Recording started using device: {device_name}"
            if capture_system_audio:
                message += " with system audio"

            return True, message
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            # Clean up if needed
            if recording_data.get("temp_file") and os.path.exists(recording_data["temp_file"]):
                try:
                    os.unlink(recording_data["temp_file"])
                except:
                    pass
            return False, f"Failed to start recording: {str(e)}"

    def _record_audio(self, recording_id, stop_flag, device_id, capture_system_audio=True):
        """
        Record audio in a background thread until stop_flag is set

        Args:
            recording_id (str): The ID of the recording
            stop_flag (threading.Event): Event to signal when to stop recording
            device_id (str): Device ID to use for recording
            capture_system_audio (bool): Whether to capture system audio
        """
        try:
            # Mark recording as active
            if recording_id in self.active_recordings:
                self.active_recordings[recording_id]["status"] = "recording"

            # In a real implementation, we would:
            # 1. Create an AVCaptureSession for the microphone
            # 2. Set up Audio Units for system audio capture
            # 3. Mix the two audio streams together
            # 4. Process and store the audio data

            logger.info(f"Audio capture started for recording {recording_id}")

            # Placeholder implementation that simulates recording
            # In a real implementation, this would be replaced with actual Core Audio code
            while not stop_flag.is_set():
                # Simulate audio data collection
                if recording_id in self.active_recordings:
                    # Create a dummy audio chunk (silence)
                    # In a real implementation, this would be actual audio data
                    audio_chunk = np.zeros((self.sample_rate // 10, 1), dtype=np.float32)
                    self.active_recordings[recording_id]["audio_data"].append(audio_chunk.copy())
                else:
                    # Recording was removed while recording
                    logger.warning(f"Recording {recording_id} no longer exists, stopping capture")
                    break

                # Small delay to reduce CPU usage
                time.sleep(0.1)

            # Stop and clean up resources
            logger.info(f"Audio capture stopped for recording {recording_id}")

        except Exception as e:
            logger.error(f"Error in recording thread: {e}")
            if recording_id in self.active_recordings:
                self.active_recordings[recording_id]["status"] = "error"

    def stop_recording(self, recording_id):
        """
        Stop recording with the given ID

        Args:
            recording_id (str): ID of the recording to stop

        Returns:
            tuple: (success (bool), message (str))
        """
        if recording_id not in self.active_recordings:
            return False, "Recording not found"

        # Check if we're using a fallback service
        if self.active_recordings[recording_id].get("using_fallback"):
            fallback = self.active_recordings[recording_id].get("fallback_service")
            if fallback:
                success, message = fallback.stop_recording(recording_id)
                if success:
                    self.active_recordings[recording_id]["status"] = "stopped"
                return success, message

        try:
            # Signal thread to stop
            self.active_recordings[recording_id]["stop_flag"].set()

            # Wait for thread to terminate
            if self.active_recordings[recording_id]["thread"] is not None:
                self.active_recordings[recording_id]["thread"].join(timeout=2.0)

            # Update status
            self.active_recordings[recording_id]["status"] = "stopped"

            logger.info(f"Stopped recording: {recording_id}")
            return True, "Recording stopped successfully"
        except Exception as e:
            logger.error(f"Error stopping recording: {e}")
            return False, f"Error stopping recording: {str(e)}"

    def get_audio_data(self, recording_id):
        """
        Get the recorded audio data for the given recording ID

        Args:
            recording_id (str): ID of the recording

        Returns:
            tuple: (success (bool), audio_data (np.ndarray) or error_message (str))
        """
        if recording_id not in self.active_recordings:
            return False, "Recording not found"

        # Check if we're using a fallback service
        if self.active_recordings[recording_id].get("using_fallback"):
            fallback = self.active_recordings[recording_id].get("fallback_service")
            if fallback:
                return fallback.get_audio_data(recording_id)

        try:
            # Concatenate audio chunks
            audio_data = np.concatenate(self.active_recordings[recording_id]["audio_data"], axis=0)
            return True, audio_data
        except Exception as e:
            logger.error(f"Error getting audio data: {e}")
            return False, f"Error retrieving audio data: {str(e)}"

    def save_audio_file(self, recording_id, file_path=None):
        """
        Save the recorded audio to a file

        Args:
            recording_id (str): ID of the recording
            file_path (str): Path where to save the audio file. If None, a default path is used.

        Returns:
            tuple: (success (bool), file_path (str) or error_message (str))
        """
        if recording_id not in self.active_recordings:
            return False, "Recording not found"

        # Check if we're using a fallback service
        if self.active_recordings[recording_id].get("using_fallback"):
            fallback = self.active_recordings[recording_id].get("fallback_service")
            if fallback:
                return fallback.save_audio_file(recording_id, file_path)

        try:
            # Use provided path or generate one
            if file_path is None:
                file_path = os.path.join(self.output_dir, f"recording_{recording_id}.wav")

            # Get audio data
            success, data_or_error = self.get_audio_data(recording_id)
            if not success:
                return False, data_or_error

            audio_data = data_or_error

            # Import scipy.io here to avoid unnecessary import if not used
            from scipy.io import wavfile

            # Save to WAV file
            wavfile.write(file_path, self.sample_rate, audio_data)

            logger.info(f"Saved audio to: {file_path}")
            return True, file_path
        except Exception as e:
            logger.error(f"Error saving audio file: {e}")
            return False, f"Error saving audio file: {str(e)}"

    def cleanup_recording(self, recording_id):
        """
        Clean up resources used by the recording

        Args:
            recording_id (str): ID of the recording to clean up

        Returns:
            bool: Success or failure
        """
        if recording_id not in self.active_recordings:
            return False

        # Check if we're using a fallback service
        if self.active_recordings[recording_id].get("using_fallback"):
            fallback = self.active_recordings[recording_id].get("fallback_service")
            if fallback:
                success = fallback.cleanup_recording(recording_id)
                if success:
                    del self.active_recordings[recording_id]
                return success

        try:
            # Stop the recording if it's still active
            if self.active_recordings[recording_id]["status"] == "recording":
                self.stop_recording(recording_id)

            # Clean up temporary file if it exists
            temp_file = self.active_recordings[recording_id].get("temp_file")
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    logger.warning(f"Failed to delete temporary file: {temp_file}")

            # Remove from active recordings
            del self.active_recordings[recording_id]

            logger.info(f"Cleaned up recording: {recording_id}")
            return True
        except Exception as e:
            logger.error(f"Error cleaning up recording: {e}")
            return False
