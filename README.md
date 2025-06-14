# Meeting Transcriber

A powerful tool for automatic transcription and summarization of meetings, designed for Mac users.

## Project Overview

Meeting Transcriber is a solution for capturing, transcribing, and summarizing meetings from any platform (Zoom, Teams, Google Meet, etc.). It uses AI to transform spoken content into structured, searchable text and concise summaries, making it easier to reference important information later.

### Key Features

- **Universal Audio Capture**: Records audio from any meeting platform
- **Automatic Transcription**: Converts speech to text with high accuracy
- **AI-Powered Summarization**: Creates concise meeting summaries
- **Markdown Output**: Generates structured, formatted documents
- **Local Processing**: Processes data on your own machine for privacy

## Technology Decisions

### Backend

- **FastAPI**: Modern, high-performance Python web framework
  - Perfect for creating RESTful APIs
  - Built-in data validation and API documentation
  - Asynchronous processing for better performance

- **Whisper AI**: OpenAI's speech recognition model
  - High-accuracy transcription across multiple languages
  - Open-source implementation allows local processing
  - Support for various output formats

- **Ollama with Mistral**: Local LLM for summarization
  - Privacy-focused (no data sent to external services)
  - Good performance-to-resource ratio
  - High-quality summarization capabilities

- **Audio Capture**:
  - macOS Core Audio APIs via PyObjC for simultaneous microphone + system audio
  - `sounddevice`: Cross-platform audio capture interface
  - `scipy`: Audio file processing
  - ThreadPoolExecutor for non-blocking audio processing

### Frontend (Planned)

- **Svelte**: Efficient, reactive UI framework
  - Minimal runtime compared to React/Vue
  - Less code for the same functionality
  - Excellent performance for real-time updates

- **TailwindCSS**: Utility-first CSS framework
  - Rapid UI development
  - Consistent styling
  - Small production bundle size

## Current State

The project currently includes:

- **Working Backend API**: FastAPI implementation with endpoints for:
  - Starting meetings
  - Stopping meetings
  - Retrieving meeting status
  - Listing all meetings

- **Audio Processing**: Recording, saving, and processing meeting audio (including simultaneous microphone and system audio capture on macOS)
- **Transcription Engine**: Integration with Whisper for speech-to-text
- **Summarization**: Text processing with Ollama/Mistral or fallback methods

## Installation

### Prerequisites

- Python 3.9+
- pip
- FFmpeg (for audio processing)
- Ollama (optional, for better summaries)
- PyObjC (automatically installed, required for macOS audio capture)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/meeting-transcriber.git
   cd meeting-transcriber
   ```

2. Install dependencies:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. Install Ollama (optional but recommended):
   ```bash
   # On macOS with Homebrew
   brew install ollama

   # Then pull the Mistral model
   ollama pull mistral
   ```

## Running the Application

### Backend

1. Start the FastAPI server:
   ```bash
   cd backend
   python run.py
   ```

2. The API will be available at http://localhost:8000
   - API documentation: http://localhost:8000/docs

## Project Roadmap

### Phase 1: Core Functionality ✅
- ✅ Audio capture from system
- ✅ Simultaneous microphone + system audio capture on macOS
- ✅ Transcription with Whisper
- ✅ Summary generation with Mistral
- ✅ Backend API with FastAPI

### Phase 2: User Interface (In Progress)
- ✅ Svelte + Tailwind CSS frontend
- ✅ Start/stop meeting interface
- ✅ Real-time transcription display
- 🔄 Meeting management UI

### Phase 3: Speaker Recognition (Planned)
- ⏱️ Audio channel separation
- ⏱️ Speaker diarization
- ⏱️ Voice profile creation and management
- ⏱️ Speaker identification in transcripts

### Phase 4: Advanced Features (Planned)
- ⏱️ Custom markdown formatting for second brain integration
- ⏱️ Action item extraction
- ⏱️ Meeting search functionality
- ⏱️ Integration with calendar systems
- ⏱️ Automatic meeting detection

### Phase 5: Enhancements (Planned)
- ⏱️ Accuracy improvements
- ⏱️ Performance optimization
- ⏱️ Mobile support
- ⏱️ Integration with other note-taking systems

## Usage

1. Start a new meeting:
   - Send a POST request to `/api/meetings/` with a title and participant list
   - The API will return a meeting ID

2. Stop and process the meeting:
   - Send a POST request to `/api/meetings/{meeting_id}/stop`
   - The system will process the audio, generate a transcript and summary

3. Retrieve results:
   - Transcripts and summaries are saved as markdown files in `~/Documents/Meeting_Transcripts/`
   - You can also get the file paths through the API at `/api/meetings/{meeting_id}`

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for the transcription model
- [Ollama](https://ollama.com/) for local LLM hosting
- [Mistral AI](https://mistral.ai/) for the language model
