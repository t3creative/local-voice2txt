#!/usr/bin/env python3
"""
Voice2Text Dictation System - Toggle Mode
==========================================
Advanced speech-to-text solution with toggle activation and universal text injection.

Features:
- Press-to-start, press-to-stop toggle recording (F10)
- GPU-accelerated whisper.cpp processing
- Universal application text injection
- Real-time audio capture and processing
- Thread-safe state management with auto-recovery
- Robust long-running session support with health checks
- Automatic audio device reconnection
- Idle timeout and recording duration limits
"""

import sys
import time
import wave
import threading
import tempfile
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import pyaudio
from pynput.keyboard import Key, Controller as KeyboardController, GlobalHotKeys
import ctypes

import whisper_runner
from PIL import Image, ImageDraw
import pystray

class Voice2TextController:
    """Advanced dictation system with toggle hotkey integration."""
    
    def __init__(self):
        # Configuration paths - adjust these to match your setup
        self.whisper_path = Path("G:/whisper.cpp/build/bin/Release/whisper-cli.exe")
        self.model_path = Path("G:/whisper.cpp/ggml-base.en.bin")
        
        # Audio configuration optimized for speech recognition
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.sample_rate = 16000
        self.chunk_size = 1024
        
        # System components
        self.audio = pyaudio.PyAudio()
        self.keyboard_controller = KeyboardController()
        
        # Enhanced toggle state management
        self.is_recording = False
        self.audio_frames = []
        self.recording_thread = None
        self.recording_state = "stopped"  # States: "stopped", "recording"
        self.toggle_lock = threading.Lock()  # Prevent rapid toggle conflicts
        self.recording_start_time = None
        
        # Robustness and reliability settings
        self.last_activity_time = time.time()
        self.last_health_check = time.time()
        self.heartbeat_interval = 30  # Check system health every 30 seconds
        self.idle_warning_hours = 4  # Warn after 4 hours of inactivity
        self.auto_shutdown_hours = 12  # Auto-shutdown after 12 hours of inactivity
        self.max_recording_duration = 300  # Maximum 5 minutes per recording
        self.running = True  # Main loop control flag
        # Global exit via ESC (double-press) settings
        self.last_escape_press_time = 0.0
        self.escape_exit_threshold = 0.8  # seconds
        
        # Performance optimization
        self.temp_dir = tempfile.mkdtemp(prefix="voice2text_")

        # Text injection settings for terminals (PowerShell, Claude Code, etc.)
        self.use_clipboard_for_long_text = True  # Use clipboard paste for text > threshold
        self.clipboard_threshold = 50  # Characters - switch to clipboard paste above this
        self.char_delay_terminals = 0.02  # Delay between characters for terminals (20ms) - prevents input buffer overflow
        self.char_delay_default = 0.01  # Delay between characters for native apps (10ms)
        self.terminal_keywords = ['powershell', 'pwsh', 'cmd', 'terminal', 'claude', 'windows terminal', 'wt']  # Window title keywords
        
        # Cross-application compatibility settings
        self.max_text_length_per_injection = 10000  # Chunk very long text to prevent issues
        self.chunk_delay = 0.2  # Delay between chunks (seconds)
        self.save_clipboard_before_paste = True  # Save/restore clipboard when using paste method
        self.saved_clipboard_content = None  # Store original clipboard content
        self.detect_password_fields = True  # Warn/block injection into password fields
        self.password_field_keywords = ['password', 'passwd', 'pwd', 'pin', 'secret', 'key']  # Window/field detection keywords
        self.blocked_app_keywords = []  # Apps where injection should be blocked (e.g., ['game', 'vmware'])
        self.verify_focus = True  # Verify window focus before injection
        self.injection_retry_count = 2  # Number of retries if injection fails

        # System tray icon
        self.tray_icon = None
        self.tray_thread = None

        # Global F10 / ESC (pynput only — mixing `keyboard` + pynput hooks often breaks on Windows)
        self._global_hotkeys = None

        # Thread pool for non-blocking transcription processing
        self.transcription_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="transcription")

        print("🎤 Voice2Text Dictation System Initialized (Toggle Mode)")
        print(f"📁 Whisper Path: {self.whisper_path}")
        print(f"🤖 Model: {self.model_path.name}")
        print("🔥 Ready for dictation - Press F10 to toggle recording")
    
    def validate_dependencies(self):
        """Ensure all system components are operational."""
        if not self.whisper_path.exists():
            raise FileNotFoundError(f"Whisper executable not found: {self.whisper_path}")

        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        print("✅ All dependencies validated successfully")

    def _create_icon_image(self, is_recording=False):
        """Create system tray icon image (red when recording, white when idle)."""
        # Create a 64x64 image with transparency
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Draw circle - red when recording, white when idle
        color = (255, 0, 0, 255) if is_recording else (255, 255, 255, 255)
        padding = 8
        draw.ellipse([padding, padding, size - padding, size - padding], fill=color, outline=color)

        return image

    def _setup_system_tray(self):
        """Initialize and start system tray icon."""
        def on_exit(icon, item):
            """Exit handler for tray menu."""
            self.running = False
            icon.stop()

        # Create tray menu
        menu = pystray.Menu(
            pystray.MenuItem("Voice2Text - Ready", lambda: None, enabled=False),
            pystray.MenuItem("Exit", on_exit)
        )

        # Create initial icon (idle state)
        icon_image = self._create_icon_image(is_recording=False)
        self.tray_icon = pystray.Icon("voice2text", icon_image, "Voice2Text - Ready", menu)

        # Run in separate thread
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()

        print("🖥️  System tray icon initialized")

    def _update_tray_icon(self, is_recording):
        """Update system tray icon to reflect current recording state."""
        if self.tray_icon:
            icon_image = self._create_icon_image(is_recording=is_recording)
            title = "Voice2Text - Recording..." if is_recording else "Voice2Text - Ready"
            self.tray_icon.icon = icon_image
            self.tray_icon.title = title
    
    def toggle_recording(self):
        """Toggle recording state with thread-safe implementation and user feedback."""
        with self.toggle_lock:
            # Update activity time on any user interaction
            self.last_activity_time = time.time()
            
            if self.recording_state == "stopped":
                self._start_toggle_recording()
            elif self.recording_state == "recording":
                self._stop_toggle_recording()
    
    def _start_toggle_recording(self):
        """Internal method to start recording in toggle mode."""
        if self.is_recording:
            return

        print("🔴 RECORDING STARTED - Speak now...")
        print("   Press F10 again to stop and process")

        self.recording_state = "recording"
        self.is_recording = True
        self.audio_frames = []
        self.recording_start_time = time.time()

        # Update system tray icon to red
        self._update_tray_icon(is_recording=True)
        
        # Configure optimal audio stream for speech recognition
        try:
            self.stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            # Launch recording in separate thread for responsiveness
            self.recording_thread = threading.Thread(target=self._capture_audio)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
        except Exception as e:
            print(f"❌ Failed to start recording: {e}")
            self.recording_state = "stopped"
            self.is_recording = False
    
    def _stop_toggle_recording(self):
        """Internal method to stop recording in toggle mode."""
        if not self.is_recording:
            return

        # Check for accidental quick toggles
        if self.recording_start_time:
            recording_duration = time.time() - self.recording_start_time
            if recording_duration < 0.5:  # Less than 500ms
                print("⚠️  Recording too short - ignored. Press F10 again to start new recording.")
                self.recording_state = "stopped"
                self.is_recording = False
                # Update system tray icon back to idle
                self._update_tray_icon(is_recording=False)
                if hasattr(self, 'stream'):
                    self.stream.stop_stream()
                    self.stream.close()
                return

        print("⏹️  RECORDING STOPPED - Processing audio...")
        self.recording_state = "stopped"
        self.is_recording = False

        # Update system tray icon back to idle
        self._update_tray_icon(is_recording=False)
        
        # Clean up audio stream
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        
        # Wait for recording thread completion
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)

        if self.audio_frames:
            # Copy audio frames and submit to thread pool for non-blocking processing
            audio_frames_copy = self.audio_frames.copy()
            self.transcription_pool.submit(self._process_audio, audio_frames_copy)
            print("✅ Recording captured - transcribing in background...")
            print("🎯 Ready for next recording - Press F10 to start")
        else:
            print("⚠️  No audio captured - Press F10 to start new recording")
    
    def _capture_audio(self):
        """Continuous audio capture during recording session with watchdog."""
        while self.is_recording:
            try:
                # Check for excessive recording duration
                if self.recording_start_time:
                    duration = time.time() - self.recording_start_time
                    if duration > self.max_recording_duration:
                        print(f"⚠️  Maximum recording duration ({self.max_recording_duration}s) reached")
                        print("   Auto-stopping recording...")
                        # Must not call toggle_recording() on this thread: _stop_toggle_joins self.
                        threading.Thread(target=self.toggle_recording, daemon=True).start()
                        break
                
                audio_chunk = self.stream.read(self.chunk_size, exception_on_overflow=False)
                self.audio_frames.append(audio_chunk)
            except Exception as e:
                print(f"⚠️  Audio capture error: {e}")
                break
    
    def _process_audio(self, audio_frames):
        """Convert captured audio to text via whisper.cpp."""
        # Generate temporary audio file
        temp_audio_path = Path(self.temp_dir) / f"recording_{int(time.time())}.wav"

        try:
            # Save audio data as WAV file
            with wave.open(str(temp_audio_path), 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(b''.join(audio_frames))
            
            print("🔄 Transcribing audio... (GPU accelerated)")

            result = whisper_runner.run_whisper_cli(
                self.whisper_path,
                self.model_path,
                temp_audio_path,
                threads=8,
                timeout=30,
            )

            if result.returncode == 0:
                transcription = whisper_runner.extract_transcription(result.stdout)
                if transcription.strip():
                    # Parse voice commands for formatting
                    formatted_text = self._parse_voice_commands(transcription.strip())
                    self._inject_text(formatted_text)
                    print("🎯 Ready for next recording - Press F10 to start")
                else:
                    print("⚠️  No speech detected - Press F10 to try again")
            else:
                print(f"❌ Transcription failed: {result.stderr}")
                print("🔄 Press F10 to try again")
        
        except subprocess.TimeoutExpired:
            print("⚠️  Transcription timeout - audio may be too long")
            print("💡 Try shorter recordings for better performance")
        except Exception as e:
            print(f"❌ Processing error: {e}")
        finally:
            # Clean up temporary files
            if temp_audio_path.exists():
                temp_audio_path.unlink()
    
    def _parse_voice_commands(self, text):
        """Parse and execute voice formatting commands from transcribed text."""
        import re

        # Working copy
        result = text

        # 1. Handle "new line" / "newline"
        result = re.sub(r'\b(new line|newline)\b', '\n', result, flags=re.IGNORECASE)

        # 2. Handle "new paragraph" (double line break)
        result = re.sub(r'\b(new paragraph|new para)\b', '\n\n', result, flags=re.IGNORECASE)

        # 3. Handle "all caps [phrase] end caps"
        def all_caps_range(match):
            return match.group(1).upper()
        result = re.sub(r'\ball caps (.*?) end caps\b', all_caps_range, result, flags=re.IGNORECASE)

        # 4. Handle "all caps [single word]"
        def all_caps_word(match):
            return match.group(1).upper()
        result = re.sub(r'\ball caps (\w+)\b', all_caps_word, result, flags=re.IGNORECASE)

        # 5. Handle "no caps [word]" (force lowercase)
        def no_caps_word(match):
            return match.group(1).lower()
        result = re.sub(r'\bno caps (\w+)\b', no_caps_word, result, flags=re.IGNORECASE)

        # 6. Handle "cap [word]" or "capitalize [word]"
        def capitalize_word(match):
            return match.group(1).capitalize()
        result = re.sub(r'\b(?:cap|capitalize) (\w+)\b', capitalize_word, result, flags=re.IGNORECASE)

        # 7. Clean up any extra whitespace around newlines
        result = re.sub(r' *\n *', '\n', result)

        return result.strip()

    def _get_active_window_title(self):
        """Get the title of the currently active window."""
        try:
            # Windows API to get active window title
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buffer = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
            return buffer.value.lower()
        except Exception:
            return ""
    
    def _is_terminal(self):
        """Detect if the active window is a terminal (PowerShell, CMD, Claude Code, etc.)."""
        try:
            window_title = self._get_active_window_title()
            return any(keyword in window_title for keyword in self.terminal_keywords)
        except Exception:
            return False
    
    def _is_password_field(self):
        """Detect if the active window/field appears to be a password field."""
        if not self.detect_password_fields:
            return False
        try:
            window_title = self._get_active_window_title()
            # Check window title for password-related keywords
            return any(keyword in window_title for keyword in self.password_field_keywords)
        except Exception:
            return False
    
    def _is_blocked_application(self):
        """Detect if the active application is in the blocked list."""
        if not self.blocked_app_keywords:
            return False
        try:
            window_title = self._get_active_window_title()
            return any(keyword in window_title for keyword in self.blocked_app_keywords)
        except Exception:
            return False
    
    def _verify_window_focus(self, original_window_title):
        """Verify that the window still has focus (hasn't switched away)."""
        if not self.verify_focus:
            return True
        try:
            current_title = self._get_active_window_title()
            # Allow some tolerance for title changes (e.g., document name changes)
            return current_title == original_window_title or len(current_title) > 0
        except Exception:
            return True  # If we can't verify, assume it's okay
    
    def _get_clipboard_text(self):
        """Get current clipboard text content."""
        try:
            import win32clipboard
            win32clipboard.OpenClipboard()
            try:
                data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return data
            except Exception:
                win32clipboard.CloseClipboard()
                return None
        except ImportError:
            # Fallback: Use PowerShell
            try:
                ps_command = 'Get-Clipboard -Format Text'
                process = subprocess.Popen(
                    ['powershell', '-NoProfile', '-Command', ps_command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                stdout, stderr = process.communicate(timeout=1)
                if process.returncode == 0:
                    return stdout.decode('utf-8', errors='ignore').strip()
            except Exception:
                pass
            return None
        except Exception:
            return None
    
    def _restore_clipboard(self):
        """Restore previously saved clipboard content."""
        if self.saved_clipboard_content is not None:
            try:
                self._set_clipboard_text(self.saved_clipboard_content)
                self.saved_clipboard_content = None
                return True
            except Exception:
                pass
        return False
    
    def _chunk_text(self, text, max_length):
        """Split text into chunks if it exceeds max_length."""
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        # Try to split at word boundaries
        words = text.split(' ')
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length > max_length and current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = len(word)
            else:
                current_chunk.append(word)
                current_length += word_length
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks if chunks else [text[:max_length]]
    
    def _set_clipboard_text(self, text):
        """Set text to Windows clipboard using Windows API."""
        try:
            # Try win32clipboard first (if pywin32 is installed)
            import win32clipboard
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
            win32clipboard.CloseClipboard()
            return True
        except ImportError:
            # Fallback: Use PowerShell (built into Windows, no dependencies)
            try:
                # Use base64 encoding to avoid escaping issues with special characters
                import base64
                text_bytes = text.encode('utf-16-le')  # UTF-16 LE is Windows clipboard format
                text_b64 = base64.b64encode(text_bytes).decode('ascii')
                # Use -EncodedCommand to safely pass the text
                ps_command = f'''
$bytes = [System.Convert]::FromBase64String('{text_b64}')
$text = [System.Text.Encoding]::Unicode.GetString($bytes)
Set-Clipboard -Value $text
'''
                process = subprocess.Popen(
                    ['powershell', '-NoProfile', '-Command', ps_command],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                stdout, stderr = process.communicate(timeout=2)
                return process.returncode == 0
            except Exception:
                # If PowerShell fails, try pyperclip as last resort
                try:
                    import pyperclip
                    pyperclip.copy(text)
                    return True
                except ImportError:
                    return False
        except Exception:
            return False
    
    def _paste_from_clipboard(self):
        """Simulate Ctrl+V to paste from clipboard."""
        self.keyboard_controller.press(Key.ctrl)
        self.keyboard_controller.press('v')
        self.keyboard_controller.release('v')
        self.keyboard_controller.release(Key.ctrl)
    
    def _type_with_delay(self, text, delay_per_char):
        """Type text character by character with delay between each character.
        
        Handles Unicode characters and special cases gracefully.
        """
        for char in text:
            try:
                # Handle special characters that might not type correctly
                if char == '\n':
                    self.keyboard_controller.press(Key.enter)
                    self.keyboard_controller.release(Key.enter)
                elif char == '\t':
                    self.keyboard_controller.press(Key.tab)
                    self.keyboard_controller.release(Key.tab)
                else:
                    self.keyboard_controller.type(char)
                
                if delay_per_char > 0:
                    time.sleep(delay_per_char)
            except Exception as ex:
                # If a character fails, try to continue with next character
                print(f"⚠️  Warning: Failed to type character '{char}': {ex}")
                continue
    
    def _inject_text(self, text):
        """Insert transcribed text into active application with enhanced formatting.
        
        Uses intelligent injection strategy with cross-application compatibility:
        - Detects password fields and blocked applications
        - Chunks very long text to prevent issues
        - Saves/restores clipboard when using paste method
        - Verifies window focus and retries on failure
        - Handles Unicode and special characters gracefully
        """
        # Safety checks before injection
        if self._is_password_field():
            print("🔒 WARNING: Password field detected! Injection blocked for security.")
            print("   If this is not a password field, you can disable detection in settings.")
            return False
        
        if self._is_blocked_application():
            print("🚫 WARNING: Application is in blocked list! Injection blocked.")
            return False
        
        # Get original window title for focus verification
        original_window_title = self._get_active_window_title()
        
        print(f"✅ Transcription: '{text[:100]}{'...' if len(text) > 100 else ''}'")
        print("⌨️  Injecting text...")
        
        # Small delay to ensure proper focus
        time.sleep(0.1)
        
        # Verify focus before proceeding
        if not self._verify_window_focus(original_window_title):
            print("⚠️  Warning: Window focus may have changed")
        
        # Chunk very long text to prevent issues
        text_chunks = self._chunk_text(text, self.max_text_length_per_injection)
        if len(text_chunks) > 1:
            print(f"📦 Text is long ({len(text)} chars), splitting into {len(text_chunks)} chunks")
        
        # Process each chunk
        for chunk_idx, chunk in enumerate(text_chunks):
            if len(text_chunks) > 1:
                print(f"   Processing chunk {chunk_idx + 1}/{len(text_chunks)}...")
            
            # Determine injection strategy
            is_terminal = self._is_terminal()
            text_length = len(chunk)
            
            # Strategy 1: Use clipboard paste for longer text in terminals (prevents input buffer overflow)
            if (self.use_clipboard_for_long_text and 
                text_length > self.clipboard_threshold and 
                is_terminal):
                
                print(f"📋 Using clipboard paste (terminal detected, {text_length} chars)")
                
                # Save current clipboard content if enabled
                if self.save_clipboard_before_paste and chunk_idx == 0:
                    self.saved_clipboard_content = self._get_clipboard_text()
                
                # Set new text to clipboard
                success = False
                for attempt in range(self.injection_retry_count + 1):
                    if self._set_clipboard_text(chunk):
                        # Small delay to ensure clipboard is set
                        time.sleep(0.05)
                        # Paste using Ctrl+V
                        self._paste_from_clipboard()
                        success = True
                        break
                    elif attempt < self.injection_retry_count:
                        print(f"   Retry {attempt + 1}/{self.injection_retry_count}...")
                        time.sleep(0.1)
                
                if success:
                    print("🎯 Text injection complete (clipboard method)")
                else:
                    # Fallback to delayed typing if clipboard fails
                    print("⚠️  Clipboard method failed, using delayed typing fallback")
                    delay = self.char_delay_terminals
                    self._type_with_delay(chunk, delay)
                    print("🎯 Text injection complete (delayed typing fallback)")
            
            # Strategy 2: Character-by-character with appropriate delay
            else:
                # Use longer delay for terminals to prevent input buffer overflow
                delay = self.char_delay_terminals if is_terminal else self.char_delay_default
                
                if is_terminal:
                    print(f"⌨️  Typing with delay ({delay*1000:.0f}ms per char) - terminal detected")
                else:
                    print(f"⌨️  Typing with delay ({delay*1000:.0f}ms per char)")
                
                self._type_with_delay(chunk, delay)
                print("🎯 Text injection complete")
            
            # Delay between chunks if multiple chunks
            if chunk_idx < len(text_chunks) - 1:
                time.sleep(self.chunk_delay)
        
        # Restore clipboard if we saved it
        if self.save_clipboard_before_paste and self.saved_clipboard_content is not None:
            # Small delay before restoring
            time.sleep(0.1)
            if self._restore_clipboard():
                print("📋 Clipboard restored")
        
        return True
    
    def _handle_escape_press(self):
        """Handle ESC key presses; exit on double-press within threshold."""
        now = time.time()
        if now - self.last_escape_press_time <= self.escape_exit_threshold:
            print("\n🛑 Exit via ESC detected...")
            self.running = False
        else:
            print("(Press ESC again to exit)")
        self.last_escape_press_time = now
    
    def setup_hotkeys(self):
        """Configure toggle-based F10 key functionality (global, all apps)."""
        print("🔧 Configuring toggle F10 key bindings (pynput GlobalHotKeys)...")

        self._global_hotkeys = GlobalHotKeys(
            {
                "<f10>": self.toggle_recording,
                "<esc>": self._handle_escape_press,
            }
        )
        self._global_hotkeys.start()

        print("⌨️  Hotkeys configured:")
        print("   F10 (press) - Toggle recording on/off")
        print("   ESC twice - Exit application (works anywhere)")
        print("   Ctrl+C - Exit when terminal is focused")
    
    def display_status(self):
        """Display current system status for user awareness."""
        status = "🔴 RECORDING" if self.recording_state == "recording" else "⚪ READY"
        duration = ""
        
        if self.recording_state == "recording" and self.recording_start_time:
            elapsed = int(time.time() - self.recording_start_time)
            duration = f"({elapsed}s)"
        
        # This could be enhanced with a status bar or system tray notification
        return f"{status} {duration}"
    
    def _check_audio_health(self):
        """Verify audio system is still functional."""
        try:
            # Quick test to see if audio device is available
            test_stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                input_device_index=None,
                start=False  # Don't actually start recording
            )
            test_stream.close()
            return True
        except Exception:
            return False
    
    def _reconnect_audio(self):
        """Attempt to reconnect audio system."""
        try:
            # Terminate old connection
            if hasattr(self, 'audio'):
                try:
                    self.audio.terminate()
                except Exception:
                    pass
            
            # Create new PyAudio instance
            self.audio = pyaudio.PyAudio()
            print("✅ Audio system reconnected successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to reconnect audio: {e}")
            return False
    
    def _perform_health_check(self):
        """Perform system health check and recovery if needed."""
        current_time = time.time()
        
        # Check idle time
        idle_time = current_time - self.last_activity_time
        idle_hours = idle_time / 3600
        
        # Warn about extended idle
        if idle_hours > self.idle_warning_hours and idle_hours < self.idle_warning_hours + 0.1:
            print(f"\n💤 System idle for {idle_hours:.1f} hours")
            print("   Press F10 to record or ESC twice to exit")
        
        # Auto-shutdown after extreme idle
        if idle_hours > self.auto_shutdown_hours:
            print(f"\n⏰ Auto-shutdown after {idle_hours:.1f} hours of inactivity")
            self.running = False
            return
        
        # Check audio system health (but not while recording)
        if self.recording_state == "stopped":
            if not self._check_audio_health():
                print("\n⚠️  Audio system disconnected - attempting reconnection...")
                if self._reconnect_audio():
                    print("   You can continue using F10 to record")
                else:
                    print("   Please check your audio devices and restart if needed")
        
        self.last_health_check = current_time
    
    def run(self):
        """Launch the dictation system main loop with enhanced reliability and recovery."""
        try:
            self.validate_dependencies()
            self._setup_system_tray()
            self.setup_hotkeys()
            
            print("\n" + "="*60)
            print("🚀 VOICE2TEXT TOGGLE DICTATION SYSTEM ACTIVE")
            print("="*60)
            print("📋 Usage Instructions:")
            print("   1. Press F10 to START recording")
            print("   2. Speak clearly into your microphone")
            print("   3. Press F10 again to STOP and process")
            print("   4. Text will be automatically injected")
            print("   5. Press ESC twice to exit (or Ctrl+C in terminal)")
            print("")
            print("💡 Enhanced Features:")
            print("   • Auto-recovery from audio disconnection")
            print("   • Idle warning after 4 hours")
            print("   • Auto-shutdown after 12 hours of inactivity")
            print("   • Maximum recording duration: 5 minutes")
            print("   • System health checks every 30 seconds")
            print("")
            print("📊 Recording Guidelines:")
            print("   • Minimum duration: 0.5 seconds")
            print("   • Optimal duration: 3-30 seconds")
            print("   • Maximum duration: 5 minutes (auto-stops)")
            print("="*60)
            print(f"🎯 Current Status: {self.display_status()}")
            print("="*60)
            
            # Robust main event loop with recovery
            while self.running:
                try:
                    # Perform periodic health check
                    current_time = time.time()
                    if current_time - self.last_health_check > self.heartbeat_interval:
                        self._perform_health_check()
                    
                    # Small sleep to prevent CPU spinning
                    time.sleep(0.1)
                    
                except KeyboardInterrupt:
                    print("\n🛑 Keyboard interrupt received...")
                    break
                    
                except Exception as e:
                    # Handle unexpected errors gracefully
                    print(f"\n⚠️  Loop error: {e}")
                    print("   Attempting to recover...")
                    
                    # Try to recover based on error type
                    if "audio" in str(e).lower():
                        print("   Attempting audio system recovery...")
                        self._reconnect_audio()
                    
                    # Brief pause before retrying
                    time.sleep(1)
                    
                    # Continue unless explicitly stopped
                    if not self.running:
                        break
            
        except KeyboardInterrupt:
            print("\n🛑 Dictation system shutting down...")
        except Exception as e:
            print(f"❌ Critical system error: {e}")
            import traceback
            print(f"📋 Error details:\n{traceback.format_exc()}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up system resources and ensure proper shutdown."""
        # Set running flag to false
        self.running = False

        if self._global_hotkeys is not None:
            try:
                self._global_hotkeys.stop()
            except Exception:
                pass
            self._global_hotkeys = None

        # Shutdown thread pool (wait for any in-progress transcriptions)
        if hasattr(self, 'transcription_pool'):
            try:
                print("⏳ Waiting for background transcriptions to complete...")
                # timeout= exists only on Python 3.13+
                if sys.version_info >= (3, 13):
                    self.transcription_pool.shutdown(wait=True, timeout=10)
                else:
                    self.transcription_pool.shutdown(wait=True)
            except Exception:
                pass

        # Stop system tray icon
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass

        # Stop any active recording
        if self.is_recording:
            self.is_recording = False
            if hasattr(self, 'stream'):
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except Exception:
                    pass

        # Clean up audio system
        if hasattr(self, 'audio'):
            try:
                self.audio.terminate()
            except Exception:
                pass
        
        # Remove temporary directory
        import shutil
        if hasattr(self, 'temp_dir') and Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except Exception:
                pass
        
        print("🧹 Cleanup complete - Voice2Text system stopped")

if __name__ == "__main__":
    # Initialize and launch dictation system
    controller = Voice2TextController()
    controller.run()