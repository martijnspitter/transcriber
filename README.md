# Meeting Transcriber

A powerful tool for automatic transcription and summarization of meetings, designed for Mac users.

## Project Overview

Meeting Transcriber is a solution for capturing, transcribing, and summarizing meetings from any platform (Zoom, Teams, Google Meet, etc.). It uses BlackHole audio device to capture system audio, combines it with microphone input, and uses AI to transform spoken content into structured, searchable text and concise summaries, making it easier to reference important information later.

### Key Features

- **Universal Audio Capture**: Records audio from any meeting platform
- **Automatic Transcription**: Converts speech to text with high accuracy
- **AI-Powered Summarization**: Creates concise meeting summaries
- **Markdown Output**: Generates structured, formatted documents
- **Local Processing**: Processes data on your own machine for privacy

## Technology Decisions

### Backend

- **Go**: High-performance, statically typed language
  - Efficient resource utilization
  - Fast execution speed
  - Simple deployment with single binary

- **Whisper CLI**: OpenAI's speech recognition tool
  - High-accuracy transcription across multiple languages
  - Command-line interface for local processing
  - Support for various output formats including SRT with timestamps

- **Ollama with Mistral**: Local LLM for summarization
  - Privacy-focused (no data sent to external services)
  - Good performance-to-resource ratio
  - High-quality summarization capabilities

- **Audio Capture**:
  - FFmpeg with AVFoundation for macOS audio capture
  - BlackHole virtual audio device for system audio routing
  - Combines microphone input with system audio
  - Thread-safe concurrent audio processing

### Frontend

- **SvelteKit**: Full-featured framework for building Svelte applications
  - Efficient, reactive UI framework
  - Built-in routing and server-side rendering capabilities
  - Excellent performance with minimal bundle size

- **TailwindCSS**: Utility-first CSS framework
  - Rapid UI development
  - Consistent styling
  - Enhanced with Typography plugin for rich text rendering

## Current State

The project currently includes:

- **Working Backend API**: FastAPI implementation with endpoints for:
  - Starting meetings
  - Stopping meetings
  - Retrieving meeting status
  - Listing all meetings

- **Frontend UI**: SvelteKit implementation with features for:
  - Starting and stopping meeting recordings
  - Adding and naming participants
  - Real-time recording status updates
  - Markdown rendering of meeting summaries

- **Audio Processing**: Recording, saving, and processing meeting audio (including simultaneous microphone and system audio capture on macOS)
- **Transcription Engine**: Integration with Whisper for speech-to-text
- **Summarization**: Text processing with Ollama/Mistral or fallback methods

## Installation

### Prerequisites

- Go 1.20+
- Node.js 18+ and npm
- FFmpeg (for audio processing)
- Whisper CLI tool
- BlackHole virtual audio device (for system audio capture)
- Ollama (for AI-powered summarization)

### Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/meeting-transcriber.git
   cd meeting-transcriber
   ```

2. Install required tools:
   ```bash
   # Install BlackHole audio device
   brew install blackhole-2ch

   # Install Whisper CLI
   pip install -U openai-whisper

   # Install FFmpeg
   brew install ffmpeg

   # Install Ollama and pull the Mistral model
   brew install ollama
   ollama pull mistral
   ```

3. Build the backend:
   ```bash
   cd backend
   go build -o transcriber ./cmd/backend
   ```

4. Setup the frontend:
   ```bash
   cd frontend
   npm install
   ```

## Running the Application

### Backend

1. Start the Go backend server:
   ```bash
   cd backend
   ./transcriber
   ```

2. The API will be available at http://localhost:8000

3. Start the frontend development server:
   ```bash
   cd frontend
   npm run dev
   ```

4. The frontend will be available at http://localhost:5173

### Audio Setup

1. Configure the BlackHole device as an output device in your system settings
2. Use Multi-Output Device to route audio to both your speakers and BlackHole
3. When recording, the application will capture audio from both your microphone and the BlackHole device

## Project Roadmap

### Phase 1: Core Functionality ✅
- ✅ Audio capture from system
- ✅ Simultaneous microphone + system audio capture on macOS
- ✅ Transcription with Whisper
- ✅ Summary generation with Mistral
- ✅ Backend API with FastAPI
- ✅ Custom markdown rendering for summaries

### Phase 2: User Interface (Completed)
- ✅ SvelteKit + Tailwind CSS frontend
- ✅ Start/stop meeting interface
- ✅ Real-time status updates
- ✅ Participant management
- ✅ Markdown summary display

### Phase 3: Speaker Recognition (Planned)
- ✅ Audio channel separation
- ⏱️ Voice profile creation and management
- ⏱️ Speaker identification in transcripts

### Phase 4: Advanced Features (Planned)
- ✅ Custom markdown formatting for second brain integration
- ✅ Action item extraction
- ⏱️ Meeting search functionality
- ⏱️ Integration with calendar systems
- ⏱️ Automatic meeting detection

### Phase 5: Enhancements (Planned)
- ✅ Accuracy improvements
- ✅ Performance optimization

## Usage

### Using the Web Interface

1. Open the application in your browser at http://localhost:5173
2. Create a new meeting by entering a title and adding participants
3. Click the "Start Recording" button to begin recording
4. When finished, click the "Stop Recording" button
5. The application will process the recording and display the status
6. Once complete, the summary will be displayed in formatted markdown
7. Files are saved to `~/obsidian-vault/meetings/` for future reference

### Using the API Directly

1. Start a new meeting:
   - Send a POST request to `/api/meetings` with a title and participant list
   - The API will return a meeting ID

2. Stop and process the meeting:
   - Send a POST request to `/api/meetings/{meeting_id}/stop`
   - The system will process the audio, generate a transcript and summary

3. Retrieve results:
   - Send a GET request to `/api/meetings/{meeting_id}`
   - Transcripts and summaries are saved as markdown files in `~/obsidian-vault/meetings/`
   - The API response includes the file paths and contents

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
