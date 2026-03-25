# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## System Architecture

This is a Voice2Text dictation system that provides GPU-accelerated speech-to-text functionality with universal Windows application integration. The system consists of three main components:

### Core Components

1. **Desktop Toggle Mode (`v2t.py`)**: Primary dictation system with F10 toggle hotkey
   - Uses whisper.cpp with CUDA acceleration 
   - Captures audio via PyAudio, processes through subprocess calls to whisper-cli.exe
   - Injects text using pynput keyboard controller
   - Thread-safe recording state management with toggle lock to prevent conflicts
   - Minimum 0.5-second recording duration to avoid accidental triggers
   - Recording state tracking: "stopped" and "recording"

2. **Mobile API Server (`v2t_mobile_server.py`)**: Flask-based web service
   - RESTful API endpoint at `/api/transcribe` for mobile integration
   - Serves mobile-optimized HTML interface at root `/` with touch-friendly controls
   - Processes base64-encoded audio data from mobile browsers
   - Automatic audio format detection (WebM, OGG, WAV)
   - Direct FFmpeg conversion support for WebM/OGG to WAV
   - Status endpoint at `/api/status` for health checks

3. **HTTPS Mobile Server (`v2t_mobile_server_https.py`)**: Secure mobile access
   - Same functionality as mobile server but with SSL/TLS support
   - Required for iOS Safari microphone access in web browsers
   - Auto-generates self-signed certificates using cryptography library
   - Fallback to HTTP if HTTPS setup fails
   - Runs on port 5443 by default

## Dependencies & External Tools

### Required External Components
- **whisper.cpp**: Located at `G:/whisper.cpp/build/bin/Release/whisper-cli.exe`
- **Model File**: `G:/whisper.cpp/ggml-base.en.bin` (base English model)
- **FFmpeg**: For audio format conversion (WebM/OGG to WAV) - located at `C:\ProgramData\chocolatey\bin\ffmpeg.exe` or in PATH
- **SSL Certificates**: `voice2text.crt` and `voice2text.key` for HTTPS server (auto-generated if missing)

### Python Dependencies
- `pyaudio`: Audio capture and processing
- Global hotkeys: `pynput.keyboard.GlobalHotKeys` (F10 toggle, ESC exit) — avoid mixing the separate `keyboard` package with pynput on Windows
- `pynput`: Cross-application text injection
- `flask`, `flask-cors`: Web server for mobile API
- `cryptography`: SSL certificate generation for HTTPS server
- `wave`, `subprocess`, `threading`: Core processing utilities
- `tempfile`, `pathlib`: File management utilities
- `base64`, `io`: Data encoding/decoding for mobile audio

## Configuration & Usage

### whisper.cpp Parameters
The system uses these optimized parameters for whisper-cli.exe:
- `-t 8`: 8 threads for processing
- `--no-timestamps`: Clean text output without timing data
- 30-second timeout for processing

### Audio Settings
- Format: 16-bit PCM
- Sample Rate: 16kHz (optimized for speech recognition)
- Channels: Mono
- Chunk Size: 1024 frames

### Hotkey Configuration
- **F10**: Toggle recording on/off (desktop mode)
- **Ctrl+C**: Exit application

## File Structure & Processing Flow

### Desktop Mode Flow
1. F10 press starts recording → PyAudio captures to memory buffer
2. F10 press stops recording → Saves WAV to temp directory  
3. Subprocess calls whisper-cli.exe with temp WAV file
4. Extracts transcription from stdout, filters system messages
5. Injects text via pynput keyboard controller
6. Cleans up temporary files

### Mobile Mode Flow  
1. Web interface captures audio via MediaRecorder API
2. Converts to base64 and POSTs to `/api/transcribe`
3. Server detects audio format (WebM/OGG/WAV) and decodes from base64
4. If WebM/OGG: Uses FFmpeg to convert to WAV format (16kHz, mono, 16-bit)
5. Same whisper.cpp processing as desktop mode
6. Returns JSON response with transcription text and processing time

## Important Paths & Settings

### Path Configuration
Both main scripts reference these hardcoded paths:
- Whisper executable: `G:/whisper.cpp/build/bin/Release/whisper-cli.exe`
- Model file: `G:/whisper.cpp/ggml-base.en.bin`

### Temporary File Management
- Creates temp directories with `voice2text_` prefix
- Automatic cleanup after processing
- WAV files use timestamp-based naming

## Development Notes

### Threading Architecture
- Recording runs in separate daemon thread for responsiveness
- Thread-safe state management with locks to prevent toggle conflicts
- Minimum 0.5-second recording duration to avoid accidental triggers
- Daemon threads ensure proper cleanup on application exit

### Error Handling
- Validates whisper.cpp dependencies on startup
- Graceful handling of audio device errors
- Timeout protection for long transcription processes (30-second timeout)
- Automatic cleanup on system shutdown
- FFmpeg fallback support if primary conversion fails
- SSL certificate auto-generation with fallback to HTTP

### Text Processing
- Filters whisper.cpp system output (load times, GPU info, CUDA messages, etc.)
- Removes `[BLANK_AUDIO]` markers and normalizes whitespace
- Direct keyboard simulation for universal app compatibility
- Supports multiple skip markers for clean transcription extraction

### Mobile Interface Features
- Touch-optimized UI with large tap targets (120px record button)
- Visual recording state with pulse animation
- Real-time duration counter during recording
- Copy-to-clipboard functionality for transcribed text
- Responsive design with gradient background
- Error state handling with user-friendly messages

### Security Considerations
- HTTPS support required for iOS Safari microphone access
- Self-signed certificates accepted for local development
- CORS enabled for cross-origin mobile browser requests
- Base64 encoding for secure audio data transmission