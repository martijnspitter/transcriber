import threading
import time
import logging
import os
import platform
from pathlib import Path
import numpy as np
import sounddevice as sd
from scipy.io import wavfile

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AudioCaptureService:
    """
    Service responsible for capturing audio from the system.
    Handles recording, storing, and providing access to audio data.
    Supports device selection and system audio capture.
    """

    def __init__(self, sample_rate=16000, output_dir=None):
        """
        Initialize the AudioCaptureService.

        Args:
            sample_rate (int): The sample rate to use for audio recording (default: 16000)
            output_dir (str): Directory to store temporary files (default: None, uses ~/Documents/Meeting_Transcripts)
        """
        self.sample_rate = sample_rate
        self.active_recordings = {}  # Dictionary to store active recordings
        
        # Device selection properties
        self.available_devices = []
        self.selected_device = None
        self.system_audio_device = None
        self.system_audio_available = False
        
        # Create output directory for temporary files
        if output_dir:
            self.output_dir = output_dir
        else:
            self.output_dir = os.path.expanduser("~/Documents/Meeting_Transcripts")
            
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        
        # Update device information on initialization
        self.update_device_info()

    def update_device_info(self):
        """Update information about available audio devices"""
        try:
            # Reset system audio flags
            self.system_audio_available = False
            self.system_audio_device = None
            
            # Get all available devices
            devices = sd.query_devices()
            
            # Get default device
            try:
                default_device = sd.default.device
                default_input_idx = default_device[0]
                default_output_idx = default_device[1]
            except:
                default_input_idx = None
                default_output_idx = None
            
            # Log devices found
            logger.info(f"Default audio devices: Input={default_input_idx}, Output={default_output_idx}")
            logger.info(f"Found {len(devices)} audio devices")
            
            # Reset device lists
            self.available_devices = []
            
            # Process each device
            for i, device in enumerate(devices):
                try:
                    # Extract device information safely
                    device_dict = {}
                    # Convert to dictionary if not already (handle both types of return values)
                    if isinstance(device, dict):
                        device_dict = device
                    else:
                        # Convert object to dictionary
                        for attr in ['name', 'max_input_channels', 'max_output_channels', 'hostapi']:
                            if hasattr(device, attr):
                                device_dict[attr] = getattr(device, attr)
                    
                    # Extract with fallbacks
                    device_name = str(device_dict.get('name', f"Device {i}"))
                    input_channels = int(device_dict.get('max_input_channels', 0))
                    output_channels = int(device_dict.get('max_output_channels', 0))
                    hostapi = int(device_dict.get('hostapi', 0))
                    
                    device_info = {
                        'id': i,
                        'name': device_name,
                        'max_input_channels': input_channels,
                        'max_output_channels': output_channels,
                        'default_input': i == default_input_idx,
                        'default_output': i == default_output_idx,
                        'hostapi': hostapi
                    }
                    
                    # Check device type based on name
                    name_lower = device_name.lower()
                    device_info['is_bluetooth'] = any(bt_term in name_lower for bt_term in 
                                                    ['bluetooth', 'airpods', 'wireless', 'bt'])
                    device_info['is_virtual'] = any(v_term in name_lower for v_term in 
                                                   ['virtual', 'loopback', 'blackhole', 'soundflower'])
                    
                    self.available_devices.append(device_info)
                    
                    # Log input devices for debugging
                    if device_info['max_input_channels'] > 0:
                        device_type = []
                        if device_info['is_bluetooth']: 
                            device_type.append("BLUETOOTH")
                        if device_info['is_virtual']: 
                            device_type.append("VIRTUAL")
                        if device_info['default_input']: 
                            device_type.append("DEFAULT")
                            
                        type_str = ", ".join(device_type) if device_type else ""
                        logger.info(f"Found input device [{i}]: {device_info['name']} {type_str}")
                        
                        # Look for system audio devices
                        if device_info['is_virtual']:
                            self.system_audio_device = i
                            self.system_audio_available = True
                            logger.info(f"Found system audio device: {device_info['name']}")
                    
                except Exception as e:
                    logger.warning(f"Error processing device {i}: {e}")
            
            # Default device selection strategy
            # 1. Use the selected device if already set
            # 2. Use system audio device if available
            # 3. Fall back to default input device
            # 4. Use the first available input device
            if self.selected_device is None:
                if self.system_audio_device is not None:
                    self.selected_device = self.system_audio_device
                    logger.info(f"Using system audio device: {self.get_device_name(self.selected_device)}")
                elif default_input_idx is not None:
                    self.selected_device = default_input_idx
                    logger.info(f"Using default input device: {self.get_device_name(self.selected_device)}")
                else:
                    for device in self.available_devices:
                        if device['max_input_channels'] > 0:
                            self.selected_device = device['id']
                            logger.info(f"Using first available input device: {device['name']}")
                            break
                            
            return True
        except Exception as e:
            logger.error(f"Error updating device info: {e}")
            return False
            
    def get_device_name(self, device_id):
        """Get the name of a device by its ID"""
        for device in self.available_devices:
            if device['id'] == device_id:
                return device['name']
        return f"Unknown device ({device_id})"
        
    def set_input_device(self, device_id):
        """Set the device to use for audio capture"""
        # Validate device_id
        device_found = False
        for device in self.available_devices:
            if device['id'] == device_id and device['max_input_channels'] > 0:
                device_found = True
                self.selected_device = device_id
                logger.info(f"Set input device to: {device['name']}")
                return True, f"Selected device: {device['name']}"
                
        if not device_found:
            return False, f"Invalid input device ID: {device_id}"
            
    def get_available_devices(self):
        """Get a list of all available input devices"""
        return [device for device in self.available_devices if device['max_input_channels'] > 0]
        
    def check_system_audio_capture(self):
        """
        Check if system audio capture is possible and provide guidance
        Returns a tuple of (available, message)
        """
        system = platform.system()
        message = ""
        
        if system == "Darwin":  # macOS
            # Check for virtual audio devices
            has_virtual_device = any(device.get('is_virtual', False) for device in self.available_devices)
            
            if has_virtual_device:
                self.system_audio_available = True
                message = "System audio capture is available using virtual audio device."
                return True, message
            else:
                message = ("System audio capture requires a virtual audio device like BlackHole or Soundflower.\n"
                          "Install with: brew install blackhole-2ch")
        
        elif system == "Windows":  # Windows
            # Check for Stereo Mix or similar
            has_stereo_mix = False
            for device in self.available_devices:
                name_lower = device.get('name', '').lower()
                if ('stereo mix' in name_lower or 'what u hear' in name_lower) and device['max_input_channels'] > 0:
                    has_stereo_mix = True
                    self.system_audio_device = device['id']
                    self.system_audio_available = True
                    break
                    
            if has_stereo_mix:
                message = "System audio capture is available using Stereo Mix."
                return True, message
            else:
                message = ("System audio capture requires Stereo Mix (enable in Sound settings) "
                          "or a virtual audio device like VB-Cable.")
                
        elif system == "Linux":  # Linux
            message = "System audio capture requires PulseAudio loopback module or similar."
            
        return self.system_audio_available, message
        
    def start_recording(self, recording_id, device_id=None, capture_system_audio=False):
        """
        Start recording audio with the given ID

        Args:
            recording_id (str): Unique identifier for this recording
            device_id (int): Optional device ID to use for recording
            capture_system_audio (bool): Whether to attempt system audio capture

        Returns:
            tuple: (success (bool), message (str))
        """
        # Check if recording with this ID already exists
        if recording_id in self.active_recordings:
            return False, "Recording already in progress"

        # Initialize recording data
        recording_data = {
            "id": recording_id,
            "audio_data": [],
            "thread": None,
            "stop_flag": threading.Event(),
            "status": "recording",
            "device_id": device_id if device_id is not None else self.selected_device,
            "capture_system_audio": capture_system_audio
        }

        try:
            # Start recording in a background thread
            recording_data["thread"] = threading.Thread(
                target=self._record_audio,
                args=(recording_id, recording_data["stop_flag"], 
                      recording_data["device_id"], recording_data["capture_system_audio"])
            )
            recording_data["thread"].daemon = True
            recording_data["thread"].start()

            self.active_recordings[recording_id] = recording_data
            device_name = self.get_device_name(recording_data["device_id"])
            logger.info(f"Started recording: {recording_id} using device: {device_name}")
            
            message = f"Recording started using device: {device_name}"
            if capture_system_audio and not self.system_audio_available:
                message += " (Note: System audio capture not available)"
                
            return True, message
        except Exception as e:
            logger.error(f"Failed to start recording: {e}")
            return False, f"Failed to start recording: {str(e)}"

    def _record_audio(self, recording_id, stop_flag, device_id=None, capture_system_audio=False):
        """
        Record audio in a background thread until stop_flag is set

        Args:
            recording_id (str): The ID of the recording
            stop_flag (threading.Event): Event to signal when to stop recording
            device_id (int): Device ID to use for recording
            capture_system_audio (bool): Whether to attempt system audio capture
        """
        try:
            # Select the device to use
            input_device = device_id
            if input_device is None:
                input_device = self.selected_device
            
            # Get device info for logging
            device_name = self.get_device_name(input_device)
            logger.info(f"Recording with device {input_device}: {device_name}")
            
            # If system audio is requested but not available through direct device capture
            if capture_system_audio and not self.system_audio_available:
                system = platform.system()
                if system == "Darwin":  # macOS
                    logger.warning("System audio capture requested but not available on macOS. "
                                  "Install BlackHole or Soundflower for system audio capture.")
                elif system == "Windows":  # Windows
                    logger.warning("System audio capture requested but not available on Windows. "
                                  "Enable Stereo Mix in Sound settings or install a virtual audio device.")
                        
                logger.warning("Falling back to regular microphone recording.")
            
            # Create a stream for recording audio
            stream = sd.InputStream(
                device=input_device,
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )
            
            # Start the stream
            stream.start()
            logger.info(f"Audio capture started for recording {recording_id} with device: {device_name}")
            
            # Record until stop flag is set
            while not stop_flag.is_set():
                # Read audio data
                audio_chunk, overflowed = stream.read(self.sample_rate)
                if overflowed:
                    logger.warning("Audio buffer overflowed")
                
                # Store the audio chunk if recording still exists
                if recording_id in self.active_recordings:
                    self.active_recordings[recording_id]["audio_data"].append(audio_chunk.copy())
                else:
                    # Recording was removed while recording
                    logger.warning(f"Recording {recording_id} no longer exists, stopping capture")
                    break
                
                # Small delay to reduce CPU usage
                time.sleep(0.1)
            
            # Stop and close the stream
            stream.stop()
            stream.close()
            logger.info(f"Audio capture stopped for recording {recording_id}")
            
        except Exception as e:
            logger.error(f"Error in recording thread: {e}")
            if recording_id in self.active_recordings:
                self.active_recordings[recording_id]["status"] = "error"

    def stop_recording(self, recording_id):
        """
        Stop recording audio with the given ID

        Args:
            recording_id (str): Unique identifier for the recording to stop

        Returns:
            tuple: (success (bool), message (str))
        """
        if recording_id not in self.active_recordings:
            return False, "Recording not found"

        recording = self.active_recordings[recording_id]

        if recording["status"] != "recording":
            return False, f"Recording is not active, current status: {recording['status']}"

        try:
            # Set stop flag and wait for thread to finish
            recording["stop_flag"].set()
            if recording["thread"].is_alive():
                recording["thread"].join(timeout=5.0)

            # Update recording status
            recording["status"] = "completed"
            logger.info(f"Stopped recording: {recording_id}")
            return True, "Recording stopped"

        except Exception as e:
            logger.error(f"Error stopping recording {recording_id}: {e}")
            recording["status"] = "error"
            return False, f"Error stopping recording: {str(e)}"

    def get_audio_data(self, recording_id):
        """
        Get the recorded audio data for a specific recording

        Args:
            recording_id (str): ID of the recording

        Returns:
            tuple: (success (bool), data (numpy array) or message (str))
        """
        if recording_id not in self.active_recordings:
            return False, "Recording not found"

        recording = self.active_recordings[recording_id]

        if not recording["audio_data"]:
            return False, "No audio data recorded"

        try:
            # Concatenate all audio chunks
            audio_data = np.concatenate(recording["audio_data"])
            return True, audio_data
        except Exception as e:
            logger.error(f"Error processing audio data for recording {recording_id}: {e}")
            return False, f"Error processing audio data: {str(e)}"

    def save_audio_file(self, recording_id, file_path):
        """
        Save the recorded audio for a specific recording to a WAV file

        Args:
            recording_id (str): ID of the recording
            file_path (str): Path where the audio file should be saved

        Returns:
            tuple: (success (bool), message (str))
        """
        success, result = self.get_audio_data(recording_id)
        if not success:
            return False, result

        try:
            # Convert float32 audio data to int16 for WAV file
            audio_data = np.int16(result * 32767)

            # Save as WAV file
            wavfile.write(file_path, self.sample_rate, audio_data)
            logger.info(f"Audio saved to {file_path}")
            return True, file_path
        except Exception as e:
            logger.error(f"Error saving audio file for recording {recording_id}: {e}")
            return False, f"Error saving audio file: {str(e)}"

    def get_chunk_since_index(self, recording_id, start_idx):
        """
        Get audio data chunks starting from a specific index

        Args:
            recording_id (str): ID of the recording
            start_idx (int): Starting index for the chunks

        Returns:
            tuple: (success (bool), data (numpy array) or message (str), new_index (int))
        """
        if recording_id not in self.active_recordings:
            return False, "Recording not found", start_idx

        recording = self.active_recordings[recording_id]

        if start_idx >= len(recording["audio_data"]):
            return True, None, start_idx  # No new data

        try:
            # Get chunks from start_idx to current end
            audio_chunks = recording["audio_data"][start_idx:]
            if not audio_chunks:
                return True, None, start_idx

            # Concatenate chunks
            audio_data = np.concatenate(audio_chunks)
            new_idx = len(recording["audio_data"])

            return True, audio_data, new_idx
        except Exception as e:
            logger.error(f"Error getting audio chunks for recording {recording_id}: {e}")
            return False, f"Error getting audio chunks: {str(e)}", start_idx

    def cleanup_recording(self, recording_id):
        """
        Remove a recording from active recordings and clean up resources

        Args:
            recording_id (str): ID of the recording to clean up

        Returns:
            bool: Whether the cleanup was successful
        """
        if recording_id not in self.active_recordings:
            return False

        # Make sure recording is stopped
        recording = self.active_recordings[recording_id]
        if recording["status"] == "recording":
            self.stop_recording(recording_id)

        # Remove from active recordings
        del self.active_recordings[recording_id]
        logger.info(f"Cleaned up recording: {recording_id}")
        return True
        
    def get_system_audio_status(self):
        """
        Get detailed information about system audio capture capabilities
        
        Returns:
            dict: Information about system audio capture status
        """
        status = {
            "system_audio_available": self.system_audio_available,
            "system_audio_device": None,
            "system": platform.system(),
            "virtual_devices": [],
            "recommendation": ""
        }
        
        # Check for virtual audio devices
        for device in self.available_devices:
            if device.get('is_virtual', True) and device['max_input_channels'] > 0:
                status["virtual_devices"].append({
                    "id": device['id'],
                    "name": device['name']
                })
                
        # Add system-specific recommendations
        if status["system"] == "Darwin":  # macOS
            if not status["virtual_devices"]:
                status["recommendation"] = (
                    "To capture system audio on macOS, install a virtual audio driver:\n"
                    "- BlackHole: brew install blackhole-2ch\n"
                    "- Configure macOS Sound preferences to use BlackHole as output\n"
                    "- Select BlackHole as the recording input device"
                )
        elif status["system"] == "Windows":  # Windows
            has_stereo_mix = any(
                'stereo mix' in device.get('name', '').lower() or
                'what u hear' in device.get('name', '').lower()
                for device in self.available_devices if device['max_input_channels'] > 0
            )
            
            if not has_stereo_mix:
                status["recommendation"] = (
                    "To capture system audio on Windows:\n"
                    "- Enable Stereo Mix in Sound Control Panel > Recording devices\n"
                    "- Or install a virtual audio cable program like VB-Cable\n"
                    "- Select Stereo Mix or virtual cable as the recording input device"
                )
                
        # Set system audio device if available
        if self.system_audio_device is not None:
            for device in self.available_devices:
                if device['id'] == self.system_audio_device:
                    status["system_audio_device"] = {
                        "id": device['id'],
                        "name": device['name']
                    }
                    break
                    
        return status