import os
import datetime
import threading
import time
import logging
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from faster_whisper import WhisperModel
import ollama
import asyncio
from .audio_manager import AudioManager

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TranscriberService:
    def __init__(self):
        self.active_meetings = {}
        self.output_dir = os.path.expanduser("~/Documents/Meeting_Transcripts")

        # Create output directory if it doesn't exist
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)

        # Initialize whisper model
        self.whisper_model = None
        self.sample_rate = 16000

        # Initialize the audio manager service
        self.audio_service = AudioManager(sample_rate=self.sample_rate, output_dir=self.output_dir)

        # Real-time transcription (keeping for backward compatibility)
        self.live_transcription_callbacks = {}  # meeting_id -> list of callback functions
        self.real_time_interval = 5  # Process real-time transcription every 5 seconds

        # Status updates
        self.status_update_callbacks = {}  # meeting_id -> list of callback functions
        self.status_update_interval = 2  # Send status updates every 2 seconds

        # Check for system audio capabilities
        if hasattr(self.audio_service, 'check_system_audio_capture'):
            self.system_audio_available, self.system_audio_message = self.audio_service.check_system_audio_capture()
        else:
            self.system_audio_available = self.audio_service.system_audio_available
            self.system_audio_message = "System audio capture available via macOS Core Audio"
        logger.info(f"System audio capture: {self.system_audio_available}")
        if self.system_audio_message:
            logger.info(self.system_audio_message)

        # Store the main event loop for use across threads
        try:
            self.main_loop = asyncio.get_event_loop()
        except RuntimeError:
            self.main_loop = None
            logger.warning("Could not get event loop at initialization. Will try again when needed.")

    def _load_whisper_model(self):
        """Load the whisper model if not already loaded"""
        if self.whisper_model is None:
            logger.info("Loading whisper model...")

            self.whisper_model = WhisperModel("base", device="cpu", compute_type="int8")

            logger.info("Whisper model loaded successfully")

    def start_meeting(self, meeting_id, title="Untitled Meeting", participants=None, device_id=None, capture_system_audio=True):
        """Start recording a meeting

        Args:
            meeting_id (str): Unique identifier for the meeting
            title (str): The meeting title
            participants (list): List of participant names
            device_id (int): Optional ID of audio device to use for recording
            capture_system_audio (bool): Whether to attempt to capture system audio (default: True)

        Returns:
            tuple: (success (bool), message (str))
        """

        # If system audio is requested, ensure permissions are set up
        if capture_system_audio and hasattr(self.audio_service, 'show_screen_recording_permission_dialog'):
            self.audio_service.show_screen_recording_permission_dialog()

        # Initialize participants if None
        if participants is None:
            participants = []

        # Check if meeting already exists
        if meeting_id in self.active_meetings:
            return False, "Meeting already in progress"

        # Initialize meeting data
        meeting_data = {
            "id": meeting_id,
            "title": title,
            "start_time": datetime.datetime.now(),
            "status": "recording",
            "participants": participants,
            "audio_file": None,
            "transcript_path": None,
            "summary_path": None,
            "audio_devices": [],
            "audio_problems": [],
            "recording_duration": 0,
            "real_time_thread": None,
            "real_time_stop_flag": threading.Event(),
            "device_id": device_id,
            "using_system_audio": capture_system_audio
        }

        try:
            # Start audio recording using the audio service with specified options
            success, message = self.audio_service.start_recording(
                meeting_id,
                device_id=device_id,
                capture_system_audio=capture_system_audio
            )
            if not success:
                logger.error(f"Failed to start audio recording: {message}")
                return False, message

            # Start status update thread
            meeting_data["real_time_thread"] = threading.Thread(
                target=self._status_update_worker,
                args=(meeting_id, meeting_data["real_time_stop_flag"])
            )
            meeting_data["real_time_thread"].daemon = True
            meeting_data["real_time_thread"].start()

            self.active_meetings[meeting_id] = meeting_data
            logger.info(f"Started meeting: {meeting_id}")
            return True, "Meeting started"
        except Exception as e:
            logger.error(f"Failed to start meeting: {e}")
            return False, f"Failed to start meeting: {str(e)}"

    # The _record_meeting_audio method has been moved to AudioCaptureService

    def stop_meeting(self, meeting_id):
        """Stop recording a meeting and start processing"""
        if meeting_id not in self.active_meetings:
            return False, "Meeting not found"

        meeting = self.active_meetings[meeting_id]

        if meeting["status"] != "recording":
            return False, f"Meeting is not recording, current status: {meeting['status']}"

        try:
            # Stop audio recording using the audio service
            success, message = self.audio_service.stop_recording(meeting_id)
            if not success:
                logger.error(f"Failed to stop audio recording: {message}")
                return False, message

            # Set real-time transcription stop flag and wait for thread to finish
            meeting["real_time_stop_flag"].set()
            if meeting["real_time_thread"] and meeting["real_time_thread"].is_alive():
                meeting["real_time_thread"].join(timeout=5.0)

            # Update meeting data
            meeting["end_time"] = datetime.datetime.now()
            meeting["duration_seconds"] = (meeting["end_time"] - meeting["start_time"]).seconds
            meeting["status"] = "processing"

            # Process the meeting in a background thread
            process_thread = threading.Thread(
                target=self._process_meeting,
                args=(meeting_id,)
            )
            process_thread.daemon = True
            process_thread.start()

            logger.info(f"Stopped meeting: {meeting_id}, processing started")
            return True, "Meeting stopped, processing started"

        except Exception as e:
            logger.error(f"Error stopping meeting {meeting_id}: {e}")
            meeting["status"] = "error"
            return False, f"Error stopping meeting: {str(e)}"

    def _process_meeting(self, meeting_id):
            """Process the recorded meeting: save audio, transcribe, summarize"""
            meeting = self.active_meetings[meeting_id]

            try:
                # Get audio data from the audio service
                success, audio_data, message = self.audio_service.get_audio_data(meeting_id)
                if not success:
                    meeting["status"] = "error"
                    logger.error(f"No audio data recorded for meeting {meeting_id}: {message}")
                    return

                # Check if the audio data is valid
                if audio_data is None or not isinstance(audio_data, np.ndarray) or audio_data.size == 0:
                    meeting["status"] = "error"
                    logger.error(f"Audio data invalid for meeting {meeting_id}")
                    return

                # Generate filenames with timestamps
                timestamp = meeting["start_time"].strftime("%Y-%m-%d_%H-%M-%S")
                safe_title = "".join(c if c.isalnum() else "_" for c in meeting["title"])
                base_filename = f"{safe_title}_{timestamp}"

                # Save audio file
                audio_file = os.path.join(self.output_dir, f"{base_filename}.wav")
                try:
                    audio_data = np.int16(audio_data * 32767)  # Convert to int16
                    wavfile.write(audio_file, self.sample_rate, audio_data)
                    meeting["audio_file"] = audio_file
                    logger.info(f"Audio saved to {audio_file}")
                except Exception as e:
                    meeting["status"] = "error"
                    logger.error(f"Failed to save audio file for meeting {meeting_id}: {e}")
                    return

                # Load Whisper model if needed
                try:
                    self._load_whisper_model()
                except Exception as e:
                    logger.error(f"Failed to load whisper model: {e}")
                    meeting["status"] = "error"
                    return

                # Transcribe audio
                logger.info(f"Transcribing meeting {meeting_id}")
                try:
                    transcript, segments = self._transcribe_audio(audio_file)
                    meeting["transcript_segments"] = segments
                except Exception as e:
                    logger.error(f"Failed to transcribe audio for meeting {meeting_id}: {e}")
                    meeting["status"] = "error"
                    meeting["transcript_segments"] = []
                    meeting["current_transcript"] = "Transcription failed"
                    return

                # Summarize transcript
                logger.info(f"Summarizing meeting {meeting_id}")
                summary = self._summarize_text(transcript)
                # Ensure summary is a string, not None
                if summary is None:
                    summary = "Summary generation failed. Please review the transcript."
                    logger.warning(f"Summary generation failed for meeting {meeting_id}")

                # Store the summary content in memory for UI display before writing to file
                meeting["summary_content"] = summary
                logger.info(f"Transcript for meeting {meeting_id}:\n{transcript}")
                logger.info(f"Summary for meeting {meeting_id}: {summary}")

                # Save transcript and summary as markdown files
                transcript_file = os.path.join(self.output_dir, f"{base_filename}_transcript.md")
                summary_file = os.path.join(self.output_dir, f"{base_filename}_summary.md")

                with open(transcript_file, 'w') as f:
                    f.write(f"# {meeting['title']} - Transcript\n\n")
                    f.write(f"Date: {meeting['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(f"Duration: {meeting['duration_seconds']} seconds\n\n")
                    f.write(f"Participants: {', '.join(meeting['participants'])}\n\n")
                    f.write(transcript)

                with open(summary_file, 'w') as f:
                    f.write(f"# {meeting['title']} - Summary\n\n")
                    f.write(f"Date: {meeting['start_time'].strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                    f.write(f"Duration: {meeting['duration_seconds']} seconds\n\n")
                    f.write(f"Participants: {', '.join(meeting['participants'])}\n\n")
                    f.write(summary)

                # Update meeting data with paths (summary content already stored)
                meeting["transcript_path"] = transcript_file
                meeting["summary_path"] = summary_file
                meeting["status"] = "completed"
                logger.info(f"Meeting {meeting_id} processed successfully")

            except Exception as e:
                logger.error(f"Error processing meeting {meeting_id}: {e}")
                meeting["status"] = "error"

    def _transcribe_audio(self, audio_file):
        """Transcribe audio file using Whisper"""
        try:
            if self.whisper_model:
                # Use faster-whisper
                segments, info = self.whisper_model.transcribe(audio_file, beam_size=5)
                transcript = ""
                segment_list = []
                for segment in segments:
                    transcript += segment.text + " "
                    segment_list.append({
                        "text": segment.text,
                        "start": segment.start,
                        "end": segment.end
                    })
                return transcript, segment_list
            else:
                return "Transcription not available - no transcription engine installed", []

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return f"Transcription failed: {str(e)}", []

    def _summarize_text(self, text):
        """Summarize transcript text using Ollama if available"""
        try:
            response = ollama.chat(model='mistral', messages=[
                {
                    'role': 'system',
                    'content': 'You are an assistant that summarizes meeting transcripts concisely, highlighting key points, action items, and decisions made. If the transcript is too long, focus on the most important parts and provide a brief summary. If the transcript is very short, provide a detailed summary with all relevant information. If the transcript is empty or contains no meaningful content, return "No content to summarize."'
                },
                {
                    'role': 'user',
                    'content': f"Please summarize this meeting transcript:\n\n{text}"
                }
            ])
            return response['message']['content']
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            logger.info("Falling back to simple summarization")
            # Fall through to simple summarization on error

    def get_meeting_status(self, meeting_id):
        """Get the status of a meeting"""
        if meeting_id not in self.active_meetings:
            return None

        meeting = self.active_meetings[meeting_id]

        # Calculate recording duration for active meetings
        if meeting["status"] == "recording":
            start_time = meeting["start_time"]
            current_time = datetime.datetime.now()
            if isinstance(start_time, str):
                try:
                    start_time = datetime.datetime.fromisoformat(start_time)
                except ValueError:
                    try:
                        start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f")
                    except ValueError:
                        start_time = current_time  # Fallback
            if isinstance(start_time, datetime.datetime):
                meeting["recording_duration"] = (current_time - start_time).total_seconds()

        return {
            "id": meeting["id"],
            "title": meeting["title"],
            "status": meeting["status"],
            "start_time": meeting["start_time"],
            "end_time": meeting.get("end_time"),  # Use get() to avoid KeyError
            "duration_seconds": meeting.get("duration_seconds"),
            "participants": meeting["participants"],
            "transcript_path": meeting.get("transcript_path"),
            "summary_path": meeting.get("summary_path"),
            "recording_duration": meeting.get("recording_duration", 0),
            "audio_devices": meeting.get("audio_devices", []),
            "audio_problems": meeting.get("audio_problems", []),
            "last_status_update": meeting.get("last_status_update", datetime.datetime.now().isoformat()),
            "summary_content": meeting.get("summary_content"),
            "current_transcript": meeting.get("current_transcript", ""),
            "transcript_segments": meeting.get("transcript_segments", [])
        }

    def get_all_meetings(self):
        """Get status for all meetings"""
        return [self.get_meeting_status(meeting_id) for meeting_id in self.active_meetings]

    def _status_update_worker(self, meeting_id, stop_flag):
        """Worker thread for sending status updates about recording health"""
        try:
            logger.info(f"Starting status updates for meeting {meeting_id}")
            no_signal_count = 0  # Counter to track consecutive silent audio checks

            while not stop_flag.is_set():
                if meeting_id not in self.active_meetings:
                    logger.warning(f"Meeting {meeting_id} no longer exists, stopping status updates")
                    break

                meeting = self.active_meetings[meeting_id]

                # Update meeting duration
                start_time = meeting.get("start_time")
                current_time = datetime.datetime.now()
                if start_time:
                    if isinstance(start_time, str):
                        try:
                            start_time = datetime.datetime.fromisoformat(start_time)
                        except ValueError:
                            try:
                                start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S.%f")
                            except ValueError:
                                start_time = current_time  # Fallback if parsing fails
                    meeting["recording_duration"] = (current_time - start_time).total_seconds()

                # Check audio health
                audio_problems = []

                # Get audio devices information
                try:
                    # Get the actual devices being used for this recording from the audio service
                    formatted_devices = []

                    # Check if the audio service has active recordings for this meeting
                    if hasattr(self.audio_service, 'active_recordings') and meeting_id in self.audio_service.active_recordings:
                        # Get the recording data
                        recording = self.audio_service.active_recordings[meeting_id]

                        # Add microphone device if it's being used
                        if 'input_device' in recording and recording['input_device'] is not None:
                            device_id = recording['input_device']
                            device_name = "Microphone"

                            # Try to find the device name from available devices
                            if hasattr(self.audio_service, 'available_devices'):
                                for device in self.audio_service.available_devices.get("input", []):
                                    if str(device.get("id")) == str(device_id):
                                        device_name = device.get("name", "Microphone")
                                        break

                            formatted_devices.append({
                                "id": str(device_id),
                                "name": device_name,
                                "type": "microphone"
                            })

                        # Add system audio if it's being used
                        if recording.get('system_audio_enabled', False):
                            formatted_devices.append({
                                "id": "system_audio",
                                "name": "System Audio",
                                "type": "system"
                            })

                    meeting["audio_devices"] = formatted_devices
                    if not formatted_devices:
                        audio_problems.append("No audio input devices detected")
                except Exception as e:
                    logger.error(f"Error getting audio devices: {e}")
                    audio_problems.append("Error detecting audio devices")

                # Check for audio signal by examining if recent audio contains silence
                # We do this by checking if audio is being recorded correctly
                try:
                    # Check if we can access the meeting's recording
                    is_recording_active = meeting.get("status") == "recording"

                    if is_recording_active:
                        # Check if recording service is active
                        if hasattr(self.audio_service, 'is_recording') and callable(getattr(self.audio_service, 'is_recording')):
                            if not self.audio_service.is_recording(meeting_id):
                                audio_problems.append("Recording service not active")

                        # Check for silence by attempting to get recent audio data
                        try:
                            # We don't want to add more functionality that could break audio capture
                            # Just check if audio service is responding correctly
                            is_ok = self.audio_service.get_recording_status(meeting_id) if hasattr(self.audio_service, 'get_recording_status') else True

                            if not is_ok:
                                no_signal_count += 1
                                if no_signal_count >= 3:  # After multiple consecutive silent checks
                                    audio_problems.append("No audio signal detected - check microphone or system audio")
                            else:
                                no_signal_count = 0  # Reset the counter if audio is detected
                        except Exception as e:
                            logger.debug(f"Could not check audio signal: {e}")
                            # Don't add problems for this - it might be a transient issue
                except Exception as e:
                    logger.debug(f"Error checking audio signal: {e}")

                # Update meeting status
                meeting["audio_problems"] = audio_problems
                meeting["last_status_update"] = current_time.isoformat()

                # Notify all registered callbacks about the status update
                self._notify_status_update(meeting_id, meeting)

                # Sleep to avoid high CPU usage
                time.sleep(self.status_update_interval)

            logger.info(f"Status updates stopped for meeting {meeting_id}")

        except Exception as e:
            logger.error(f"Error in status update worker: {e}")

    def register_transcript_callback(self, meeting_id, callback):
        """Register a callback function for transcript updates (deprecated)"""
        # For backward compatibility, redirect to status callback
        return self.register_status_callback(meeting_id, callback)

    def unregister_transcript_callback(self, meeting_id, callback):
        """Unregister a callback function (deprecated)"""
        # For backward compatibility, redirect to status callback
        return self.unregister_status_callback(meeting_id, callback)

    def register_status_callback(self, meeting_id, callback):
        """Register a callback function for status updates"""
        if not hasattr(self, 'status_update_callbacks') or self.status_update_callbacks is None:
            self.status_update_callbacks = {}

        if meeting_id not in self.status_update_callbacks:
            self.status_update_callbacks[meeting_id] = []

        # Make sure we have a reference to the main event loop
        if self.main_loop is None:
            try:
                self.main_loop = asyncio.get_event_loop()
                logger.info("Stored main event loop during callback registration")
            except RuntimeError:
                logger.warning("No event loop available during callback registration")

        if callback not in self.status_update_callbacks[meeting_id]:
            self.status_update_callbacks[meeting_id].append(callback)
        return True

    def unregister_status_callback(self, meeting_id, callback):
        """Unregister a callback function"""
        if not hasattr(self, 'status_update_callbacks') or self.status_update_callbacks is None:
            return False

        if meeting_id in self.status_update_callbacks:
            if callback in self.status_update_callbacks[meeting_id]:
                self.status_update_callbacks[meeting_id].remove(callback)
                return True
        return False

    def _notify_status_update(self, meeting_id, status_data):
        """Notify all registered callbacks about a status update"""
        if not hasattr(self, 'status_update_callbacks') or self.status_update_callbacks is None:
            return

        if meeting_id in self.status_update_callbacks:
            for callback in self.status_update_callbacks[meeting_id]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        # If we don't have a main event loop reference, we can't run async callbacks
                        if self.main_loop is None:
                            try:
                                self.main_loop = asyncio.get_event_loop()
                            except RuntimeError:
                                logger.error("No event loop available for async callback - skipping")
                                continue

                        # Create a complete coroutine object
                        coro = callback(meeting_id, status_data)

                        # Schedule the coroutine to run in the main event loop
                        try:
                            asyncio.run_coroutine_threadsafe(coro, self.main_loop)
                        except RuntimeError as e:
                            logger.error(f"Failed to schedule async callback: {e}")
                    else:
                        # Call regular function
                        callback(meeting_id, status_data)
                except Exception as e:
                    logger.error(f"Error in status update callback: {e}")

    def _notify_transcript_update(self, meeting_id, full_transcript, new_text):
        """Notify all registered callbacks about a transcript update (deprecated)"""
        # No longer used, but kept for compatibility
        pass

    def get_audio_devices(self):
        """
        Get a list of all available audio input devices

        Returns:
            list: List of dictionaries with device information
        """
        return self.audio_service.get_available_devices()

    def set_audio_device(self, device_id):
        """
        Set the device to use for audio capture

        Args:
            device_id (int): The ID of the device to use

        Returns:
            tuple: (success (bool), message (str))
        """
        return self.audio_service.set_input_device(device_id)

    def get_system_audio_status(self):
        """
        Get information about system audio capture capabilities

        Returns:
            dict: System audio capture status and recommendations
        """
        return self.audio_service.get_system_audio_status()

    def refresh_audio_devices(self):
        """
        Refresh the list of available audio devices

        Returns:
            bool: Whether the refresh was successful
        """
        return self.audio_service.update_device_info()
