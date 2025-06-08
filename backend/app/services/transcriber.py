import os
import datetime
import threading
import time
import logging
from pathlib import Path
import numpy as np
import sounddevice as sd
from scipy.io import wavfile
from faster_whisper import WhisperModel
import ollama

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

    def _load_whisper_model(self):
        """Load the whisper model if not already loaded"""
        if self.whisper_model is None:
            logger.info("Loading whisper model...")

            self.whisper_model = WhisperModel("base", device="cpu", compute_type="int8")

            logger.info("Whisper model loaded successfully")

    def start_meeting(self, meeting_id, title="Untitled Meeting", participants=None):
        """Start recording a meeting"""

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
            "audio_data": [],
            "thread": None,
            "stop_flag": threading.Event(),
            "audio_file": None,
            "transcript_path": None,
            "summary_path": None
        }

        try:
            # Start recording in a background thread
            meeting_data["thread"] = threading.Thread(
                target=self._record_meeting_audio,
                args=(meeting_id, meeting_data["stop_flag"])
            )
            meeting_data["thread"].daemon = True
            meeting_data["thread"].start()

            self.active_meetings[meeting_id] = meeting_data
            logger.info(f"Started meeting: {meeting_id}")
            return True, "Meeting started"
        except Exception as e:
            logger.error(f"Failed to start meeting: {e}")
            return False, f"Failed to start meeting: {str(e)}"

    def _record_meeting_audio(self, meeting_id, stop_flag):
        """Record audio in a background thread until stop_flag is set"""
        try:
            # Create a stream for recording audio
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32'
            )

            # Start the stream
            stream.start()
            logger.info(f"Recording started for meeting {meeting_id}")

            # Record until stop flag is set
            while not stop_flag.is_set():
                # Read audio data
                audio_chunk, overflowed = stream.read(self.sample_rate)
                if overflowed:
                    logger.warning("Audio buffer overflowed")

                # Store the audio chunk if meeting still exists
                if meeting_id in self.active_meetings:
                    self.active_meetings[meeting_id]["audio_data"].append(audio_chunk.copy())
                else:
                    # Meeting was removed while recording
                    logger.warning(f"Meeting {meeting_id} no longer exists, stopping recording")
                    break

                # Small delay to reduce CPU usage
                time.sleep(0.1)

            # Stop and close the stream
            stream.stop()
            stream.close()
            logger.info(f"Recording stopped for meeting {meeting_id}")

        except Exception as e:
            logger.error(f"Error in recording thread: {e}")
            if meeting_id in self.active_meetings:
                self.active_meetings[meeting_id]["status"] = "error"

    def stop_meeting(self, meeting_id):
        """Stop recording a meeting and start processing"""
        if meeting_id not in self.active_meetings:
            return False, "Meeting not found"

        meeting = self.active_meetings[meeting_id]

        if meeting["status"] != "recording":
            return False, f"Meeting is not recording, current status: {meeting['status']}"

        try:
            # Set stop flag and wait for recording thread to finish
            meeting["stop_flag"].set()
            if meeting["thread"].is_alive():
                meeting["thread"].join(timeout=5.0)

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
                # Combine audio chunks
                if not meeting["audio_data"]:
                    meeting["status"] = "error"
                    logger.error(f"No audio data recorded for meeting {meeting_id}")
                    return

                # Concatenate all audio chunks
                audio_data = np.concatenate(meeting["audio_data"])

                # Generate filenames with timestamps
                timestamp = meeting["start_time"].strftime("%Y-%m-%d_%H-%M-%S")
                safe_title = "".join(c if c.isalnum() else "_" for c in meeting["title"])
                base_filename = f"{safe_title}_{timestamp}"

                # Save audio file
                audio_file = os.path.join(self.output_dir, f"{base_filename}.wav")
                audio_data = np.int16(audio_data * 32767)  # Convert to int16
                wavfile.write(audio_file, self.sample_rate, audio_data)
                meeting["audio_file"] = audio_file
                logger.info(f"Audio saved to {audio_file}")

                # Load Whisper model if needed
                try:
                    self._load_whisper_model()
                except Exception as e:
                    logger.error(f"Failed to load whisper model: {e}")
                    meeting["status"] = "error"
                    return

                # Transcribe audio
                logger.info(f"Transcribing meeting {meeting_id}")
                transcript = self._transcribe_audio(audio_file)

                # Summarize transcript
                logger.info(f"Summarizing meeting {meeting_id}")
                summary = self._summarize_text(transcript)
                # Ensure summary is a string, not None
                if summary is None:
                    summary = "Summary generation failed. Please review the transcript."
                    logger.warning(f"Summary generation failed for meeting {meeting_id}")

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

                # Update meeting data with paths
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
                for segment in segments:
                    transcript += segment.text + " "
                return transcript
            else:
                return "Transcription not available - no transcription engine installed"

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return f"Transcription failed: {str(e)}"

    def _summarize_text(self, text):
        """Summarize transcript text using Ollama if available"""
        try:
            response = ollama.chat(model='mistral', messages=[
                {
                    'role': 'system',
                    'content': 'You are an assistant that summarizes meeting transcripts concisely, highlighting key points, action items, and decisions made.'
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

        return {
            "id": meeting["id"],
            "title": meeting["title"],
            "status": meeting["status"],
            "start_time": meeting["start_time"],
            "end_time": meeting.get("end_time"),  # Use get() to avoid KeyError
            "duration_seconds": meeting.get("duration_seconds"),
            "participants": meeting["participants"],
            "transcript_path": meeting.get("transcript_path"),
            "summary_path": meeting.get("summary_path")
        }

    def get_all_meetings(self):
        """Get status for all meetings"""
        return [self.get_meeting_status(meeting_id) for meeting_id in self.active_meetings]
