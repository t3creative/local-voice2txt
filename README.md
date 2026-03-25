# Voice2Text Dictation System
## Advanced GPU-Accelerated Speech-to-Text Solution

---

## Executive Summary

The Voice2Text Dictation System is a production-ready, locally-processed speech-to-text solution that transforms natural speech into precise text across any Windows application. Through intelligent hotkey activation and cross-application compatibility features, it delivers enterprise-grade dictation capabilities with complete privacy and control.

**Core Value Proposition**: Eliminate typing bottlenecks while maintaining accuracy standards through GPU-accelerated processing, universal application compatibility, and intelligent text injection strategies that adapt to different environments.

---

## 1. Current Features & Capabilities

### 1.1 Core Functionality

- **Toggle Recording**: Press F10 to start/stop recording - simple, intuitive control
- **GPU-Accelerated Processing**: Leverages whisper.cpp with CUDA for fast, accurate transcription
- **Universal Text Injection**: Works across all Windows applications without configuration
- **System Tray Integration**: Visual status indicator (red when recording, white when idle)
- **Background Processing**: Non-blocking transcription in thread pool for responsive operation

### 1.2 Cross-Application Compatibility

The system intelligently adapts to different application types:

- **Terminal Detection**: Automatically detects PowerShell, CMD, Claude Code, and other terminals
- **Intelligent Injection Strategy**: 
  - Uses clipboard paste for longer text in terminals (prevents input buffer overflow)
  - Uses delayed character-by-character typing for shorter text or native apps
  - Automatically chunks very long transcriptions (>10,000 chars) to prevent issues
- **Password Field Protection**: Automatically blocks injection into password fields for security
- **Application Blocking**: Configurable list to block injection into specific applications (games, VMs, etc.)
- **Focus Verification**: Verifies window focus before injection and handles window switches gracefully
- **Retry Logic**: Automatically retries failed injections with configurable retry count

### 1.3 Text Processing Features

- **Voice Commands**: Natural language commands for formatting:
  - "new line" / "newline" → inserts line break
  - "new paragraph" / "new para" → inserts double line break
  - "all caps [phrase] end caps" → capitalizes phrase
  - "cap [word]" / "capitalize [word]" → capitalizes single word
  - "no caps [word]" → forces lowercase
- **Unicode Support**: Handles Unicode characters, emojis, and international text
- **Special Character Handling**: Proper handling of newlines, tabs, and other control characters
- **Clipboard Management**: Saves and restores clipboard content when using paste method

### 1.4 Reliability & Robustness

- **Health Monitoring**: Automatic system health checks every 30 seconds
- **Audio Device Recovery**: Automatic reconnection if audio device disconnects
- **Idle Management**: 
  - Warning after 4 hours of inactivity
  - Auto-shutdown after 12 hours of inactivity
- **Recording Limits**: Maximum 5 minutes per recording (auto-stops to prevent issues)
- **Minimum Duration Check**: Ignores accidental quick toggles (<0.5 seconds)
- **Error Recovery**: Graceful handling of errors with automatic recovery attempts
- **Resource Cleanup**: Automatic cleanup of temporary files and resources

### 1.5 User Experience

- **Visual Feedback**: System tray icon changes color based on recording state
- **Console Output**: Detailed status messages for transparency
- **Exit Options**: 
  - Double-press ESC to exit (works from any application)
  - Ctrl+C in terminal
  - System tray menu option

---

## 2. Technical Architecture

### 2.1 System Components

#### Audio Capture Layer
- **Technology**: PyAudio with optimized 16kHz sampling for speech recognition
- **Configuration**: 16-bit PCM, mono channel, 1024 frame chunks
- **Performance**: Minimal latency capture through threaded processing architecture
- **Reliability**: Overflow protection and automatic device reconnection

#### Processing Engine
- **Core Technology**: whisper.cpp with CUDA acceleration
- **Model**: Optimized base.en model (142MB) providing balanced accuracy-to-speed ratios
- **Threading**: 8 threads for optimal CPU utilization
- **Resource Management**: Temporary file handling with automatic cleanup protocols
- **Timeout Protection**: 30-second timeout prevents hanging on problematic audio

#### Text Injection Framework
- **Implementation**: pynput keyboard controller with intelligent strategies
- **Delivery Methods**: 
  - Clipboard paste (Ctrl+V) for terminals and longer text
  - Character-by-character typing with configurable delays
- **Compatibility**: Handles Unicode, special characters, and different application types
- **Safety**: Password field detection, application blocking, focus verification

### 2.2 Data Flow Architecture

```
User Speech Input → F10 Hotkey Detection → Audio Capture (Threaded) → 
Temporary WAV Generation → whisper.cpp Processing (Thread Pool) → 
Text Extraction & Command Parsing → Safety Checks → 
Intelligent Text Injection (Clipboard/Typing) → Resource Cleanup
```

### 2.3 Integration Points

- **whisper.cpp Integration**: Direct subprocess execution with optimized parameters
- **System Hotkeys**: Global hotkeys via `pynput` `GlobalHotKeys` (F10 toggle, ESC exit)
- **File Management**: Temporary directory with automatic cleanup
- **System Tray**: pystray integration for background operation
- **Windows API**: ctypes for window title detection and clipboard operations

---

## 3. Installation & Setup

### 3.1 Prerequisites

- **Windows 10/11** (tested on Windows 10+)
- **Python 3.7+**
- **whisper.cpp** with CUDA support (compiled executable)
- **NVIDIA GPU** with CUDA support (recommended for best performance)
- **Microphone** access permissions

### 3.2 Required Python Packages

```bash
pip install pyaudio pynput pillow pystray
```

Optional (for enhanced clipboard support):
```bash
pip install pywin32  # Windows clipboard API (recommended)
pip install pyperclip  # Alternative clipboard library
```

### 3.3 Configuration

Edit `v2t.py` and update these paths in the `__init__` method:

```python
self.whisper_path = Path("G:/whisper.cpp/build/bin/Release/whisper-cli.exe")
self.model_path = Path("G:/whisper.cpp/ggml-base.en.bin")
```

Adjust these paths to match your whisper.cpp installation.

### 3.4 whisper.cpp Setup

1. Build whisper.cpp with CUDA support:
```bash
cmake -B build -DGGML_CUDA=ON
cmake --build build --config Release
```

2. Download the base.en model:
```bash
# Place ggml-base.en.bin in your whisper.cpp directory
```

3. Verify the executable works:
```bash
whisper-cli.exe -m ggml-base.en.bin -f test.wav
```

---

## 4. Usage

### 4.1 Basic Operation

1. **Start the application**:
   ```bash
   python v2t.py
   ```

2. **Begin recording**: Press **F10** (system tray icon turns red)

3. **Speak clearly** into your microphone

4. **Stop recording**: Press **F10** again (transcription processes automatically)

5. **Text injection**: Transcribed text is automatically injected into the active application

### 4.2 Voice Commands

Use natural language commands for formatting:

- **Line breaks**: Say "new line" or "newline"
- **Paragraphs**: Say "new paragraph" or "new para"
- **Capitalization**: 
  - "all caps [phrase] end caps" - capitalizes entire phrase
  - "cap [word]" or "capitalize [word]" - capitalizes single word
  - "no caps [word]" - forces lowercase

**Example**: 
- Say: "Hello world new line this is a test new paragraph all caps important end caps"
- Result: 
  ```
  Hello world
  this is a test

  IMPORTANT
  ```

### 4.3 Exit Options

- **Double-press ESC** (works from any application)
- **Ctrl+C** (when terminal is focused)
- **System tray menu** → Exit

---

## 5. Configuration Options

All configuration options are in the `__init__` method of `Voice2TextController`. Key settings:

### 5.1 Text Injection Settings

```python
# Terminal detection and clipboard usage
self.use_clipboard_for_long_text = True  # Enable clipboard paste
self.clipboard_threshold = 50  # Switch to clipboard above this many characters
self.char_delay_terminals = 0.02  # 20ms delay for terminals
self.char_delay_default = 0.01  # 10ms delay for native apps
self.terminal_keywords = ['powershell', 'pwsh', 'cmd', 'terminal', 'claude', 'windows terminal', 'wt']
```

### 5.2 Cross-Application Compatibility

```python
# Text chunking for very long transcriptions
self.max_text_length_per_injection = 10000  # Chunk text above this length
self.chunk_delay = 0.2  # Delay between chunks (seconds)

# Clipboard management
self.save_clipboard_before_paste = True  # Save/restore clipboard

# Security features
self.detect_password_fields = True  # Block password field injection
self.password_field_keywords = ['password', 'passwd', 'pwd', 'pin', 'secret', 'key']
self.blocked_app_keywords = []  # Add keywords like ['game', 'vmware'] to block apps

# Reliability
self.verify_focus = True  # Verify window focus before injection
self.injection_retry_count = 2  # Number of retries on failure
```

### 5.3 System Behavior

```python
# Health monitoring
self.heartbeat_interval = 30  # Health check interval (seconds)
self.idle_warning_hours = 4  # Warn after this many hours
self.auto_shutdown_hours = 12  # Auto-shutdown after this many hours
self.max_recording_duration = 300  # Maximum 5 minutes per recording
```

### 5.4 Customization Examples

**Block specific applications**:
```python
self.blocked_app_keywords = ['game', 'vmware', 'virtualbox']
```

**Disable password field detection** (if too aggressive):
```python
self.detect_password_fields = False
```

**Use clipboard more aggressively**:
```python
self.clipboard_threshold = 20  # Lower threshold = more clipboard usage
```

**Adjust delays for slower systems**:
```python
self.char_delay_terminals = 0.03  # 30ms delay
self.char_delay_default = 0.02  # 20ms delay
```

---

## 6. Troubleshooting

### 6.1 Common Issues

**Problem**: Text not injecting into application
- **Solution**: Check if application is in blocked list (`blocked_app_keywords`)
- **Solution**: Verify window focus (try clicking the target window before recording)
- **Solution**: Check if password field detection is incorrectly triggering

**Problem**: Transcription is slow
- **Solution**: Ensure CUDA is enabled in whisper.cpp build
- **Solution**: Check GPU utilization during processing
- **Solution**: Consider using smaller model (tiny.en) for faster processing

**Problem**: Audio not capturing
- **Solution**: Check microphone permissions in Windows settings
- **Solution**: Verify audio device is connected and selected as default
- **Solution**: Check console for audio device reconnection messages

**Problem**: React error #185 in Claude Code/PowerShell
- **Solution**: This is now handled automatically - system detects terminals and uses clipboard paste
- **Solution**: If issues persist, lower `clipboard_threshold` to use clipboard more often

**Problem**: Clipboard not working
- **Solution**: Install pywin32: `pip install pywin32`
- **Solution**: System will fall back to PowerShell clipboard commands automatically

### 6.2 Debug Mode

Enable verbose output by checking console messages. The system provides detailed status information:
- Recording state changes
- Injection method selection (clipboard vs typing)
- Terminal detection
- Error messages and warnings
- Health check status

---

## 7. Performance Characteristics

### 7.1 Processing Speed

- **Audio Capture**: Real-time (no delay)
- **Transcription**: 1-5 seconds depending on audio length and GPU
- **Text Injection**: 
  - Clipboard method: <100ms
  - Typing method: ~10-20ms per character

### 7.2 Resource Usage

- **CPU**: Low (primarily audio capture thread)
- **GPU**: Moderate during transcription (CUDA acceleration)
- **Memory**: ~200-500MB (whisper.cpp model + buffers)
- **Disk**: Temporary files cleaned automatically

### 7.3 Accuracy

- **Base Model**: High accuracy for clear speech
- **Best Results**: Quiet environment, clear microphone, moderate speaking pace
- **Limitations**: May struggle with heavy accents, background noise, or very fast speech

---

## 8. Security & Privacy

### 8.1 Data Privacy

- **100% Local Processing**: All audio and transcription processed locally
- **No Network Communication**: No data sent to external servers
- **No Cloud Dependencies**: Works completely offline
- **Temporary Files**: Automatically deleted after processing

### 8.2 Security Features

- **Password Field Protection**: Automatically blocks injection into password fields
- **Application Blocking**: Configurable blocking of specific applications
- **Focus Verification**: Verifies window focus before injection
- **Safe Defaults**: Conservative settings prevent accidental data exposure

---

## 9. Advanced Features

### 9.1 System Tray Integration

The system runs in the background with a system tray icon:
- **White icon**: System ready, not recording
- **Red icon**: Currently recording
- **Right-click menu**: Exit option

### 9.2 Health Monitoring

Automatic system health checks:
- Audio device connectivity
- System resource availability
- Idle time tracking
- Automatic recovery from common issues

### 9.3 Error Recovery

Robust error handling:
- Automatic audio device reconnection
- Retry logic for failed injections
- Graceful degradation on errors
- Detailed error logging

---

## 10. Limitations & Known Issues

### 10.1 Current Limitations

- **Windows Only**: Designed for Windows (uses Windows API)
- **Single Language**: English only (base.en model)
- **Model Size**: Fixed to configured model (no runtime switching)
- **Hotkey**: Single hotkey (F10) - not configurable without code changes

### 10.2 Known Considerations

- **Terminal Compatibility**: Some terminals may require clipboard method (handled automatically)
- **Game Compatibility**: Some games block input injection (use blocked_app_keywords)
- **Virtual Machines**: May require slower typing delays (adjust char_delay settings)
- **Remote Desktop**: May have different behavior (focus verification helps)

---

## 11. Future Enhancement Opportunities

While the current system is production-ready, potential enhancements include:

- **Multi-language Support**: Additional whisper.cpp models for other languages
- **Configurable Hotkeys**: Runtime hotkey configuration without code changes
- **Voice Activity Detection**: Auto-stop on silence detection
- **Transcription History**: Logging and review of past transcriptions
- **Custom Vocabulary**: Domain-specific term learning
- **Application Profiles**: Different settings per application
- **Real-time Streaming**: Live transcription preview

---

## 12. Technical Support

### 12.1 Getting Help

1. Check console output for error messages
2. Review configuration settings
3. Verify whisper.cpp installation and model availability
4. Check Windows audio device settings

### 12.2 System Requirements

- **OS**: Windows 10/11
- **Python**: 3.7+
- **GPU**: NVIDIA GPU with CUDA support (recommended)
- **RAM**: 4GB+ (8GB+ recommended)
- **Storage**: ~500MB for model and temporary files

---

## Conclusion

The Voice2Text Dictation System provides a robust, privacy-focused solution for speech-to-text dictation across Windows applications. With intelligent cross-application compatibility, comprehensive error handling, and automatic adaptation to different environments, it delivers reliable performance for a wide range of use cases.

The system is production-ready and suitable for daily use, with extensive configuration options for fine-tuning to specific needs and environments.

**Quick Start**: Configure paths, install dependencies, run `python v2t.py`, and press F10 to start dictating!
