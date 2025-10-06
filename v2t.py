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

import os
import time
import wave
import threading
import tempfile
import subprocess
from pathlib import Path

import pyaudio
import keyboard
from pynput.keyboard import Key, Controller as KeyboardController
import ctypes

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
        print("   Press G5 again to stop and process")
        
        self.recording_state = "recording"
        self.is_recording = True
        self.audio_frames = []
        self.recording_start_time = time.time()
        
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
                print("⚠️  Recording too short - ignored. Press G5 again to start new recording.")
                self.recording_state = "stopped"
                self.is_recording = False
                if hasattr(self, 'stream'):
                    self.stream.stop_stream()
                    self.stream.close()
                return
        
        print("⏹️  RECORDING STOPPED - Processing audio...")
        self.recording_state = "stopped"
        self.is_recording = False
        
        # Clean up audio stream
        if hasattr(self, 'stream'):
            self.stream.stop_stream()
            self.stream.close()
        
        # Wait for recording thread completion
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2.0)
        
        if self.audio_frames:
            self._process_audio()
        else:
            print("⚠️  No audio captured - Press G5 to start new recording")
    
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
                        # Schedule stop from main thread to avoid deadlock
                        keyboard.press_and_release('f10')
                        break
                
                audio_chunk = self.stream.read(self.chunk_size, exception_on_overflow=False)
                self.audio_frames.append(audio_chunk)
            except Exception as e:
                print(f"⚠️  Audio capture error: {e}")
                break
    
    def _process_audio(self):
        """Convert captured audio to text via whisper.cpp."""
        # Generate temporary audio file
        temp_audio_path = Path(self.temp_dir) / f"recording_{int(time.time())}.wav"
        
        try:
            # Save audio data as WAV file
            with wave.open(str(temp_audio_path), 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(self.audio.get_sample_size(self.audio_format))
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(b''.join(self.audio_frames))
            
            print("🔄 Transcribing audio... (GPU accelerated)")
            
            # Execute whisper.cpp transcription with optimized parameters
            cmd = [
                str(self.whisper_path),
                "-m", str(self.model_path),
                "-f", str(temp_audio_path),
                "-t", "8",  # Use 8 threads for optimal performance
                "--no-timestamps"
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.whisper_path.parent
            )
            
            if result.returncode == 0:
                # Extract transcription from output
                transcription = self._extract_transcription(result.stdout)
                if transcription.strip():
                    self._inject_text(transcription.strip())
                    print("🎯 Ready for next recording - Press G5 to start")
                else:
                    print("⚠️  No speech detected - Press G5 to try again")
            else:
                print(f"❌ Transcription failed: {result.stderr}")
                print("🔄 Press G5 to try again")
        
        except subprocess.TimeoutExpired:
            print("⚠️  Transcription timeout - audio may be too long")
            print("💡 Try shorter recordings for better performance")
        except Exception as e:
            print(f"❌ Processing error: {e}")
        finally:
            # Clean up temporary files
            if temp_audio_path.exists():
                temp_audio_path.unlink()
    
    def _extract_transcription(self, whisper_output):
        """Extract clean transcription text from whisper.cpp output."""
        lines = whisper_output.strip().split('\n')
        
        # Find the transcription content (skip system info)
        transcription_lines = []
        
        for line in lines:
            # Skip system information and metadata
            if any(skip_marker in line.lower() for skip_marker in [
                'whisper_', 'system_info', 'main:', 'load time', 'mel time',
                'sample time', 'encode time', 'decode time', 'batchd time',
                'prompt time', 'total time', 'ggml_cuda_init'
            ]):
                continue
            
            # Look for actual transcription content
            if line.strip() and not line.startswith('[') and not line.startswith('whisper_'):
                # Clean up the line
                clean_line = line.strip()
                # Remove common prefixes that might remain
                if clean_line and not any(clean_line.startswith(prefix) for prefix in [
                    'main:', 'system_info:', 'whisper_'
                ]):
                    transcription_lines.append(clean_line)
        
        # Combine and clean transcription
        transcription = ' '.join(transcription_lines)
        
        # Remove common artifacts and normalize
        transcription = transcription.replace('[BLANK_AUDIO]', '')
        transcription = transcription.replace('  ', ' ')  # Remove double spaces
        transcription = transcription.strip()
        
        return transcription
    
    def _inject_text(self, text):
        """Insert transcribed text into active application with enhanced formatting."""
        print(f"✅ Transcription: '{text}'")
        print("⌨️  Injecting text...")
        
        # Small delay to ensure proper focus
        time.sleep(0.1)
        
        # Type the transcribed text
        self.keyboard_controller.type(text)
        
        print("🎯 Text injection complete")
    
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
        """Configure toggle-based F10 key functionality."""
        print("🔧 Configuring toggle F10 key bindings...")
        
        # F10 key for toggle recording (single press activation)
        keyboard.on_press_key('f10', lambda _: self.toggle_recording())
        # ESC global double-press to exit
        keyboard.on_press_key('esc', lambda _: self._handle_escape_press())
        
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
        except Exception as e:
            return False
    
    def _reconnect_audio(self):
        """Attempt to reconnect audio system."""
        try:
            # Terminate old connection
            if hasattr(self, 'audio'):
                try:
                    self.audio.terminate()
                except:
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
        
        # Stop any active recording
        if self.is_recording:
            self.is_recording = False
            if hasattr(self, 'stream'):
                try:
                    self.stream.stop_stream()
                    self.stream.close()
                except:
                    pass
        
        # Clean up audio system
        if hasattr(self, 'audio'):
            try:
                self.audio.terminate()
            except:
                pass
        
        # Remove temporary directory
        import shutil
        if hasattr(self, 'temp_dir') and Path(self.temp_dir).exists():
            try:
                shutil.rmtree(self.temp_dir, ignore_errors=True)
            except:
                pass
        
        print("🧹 Cleanup complete - Voice2Text system stopped")

if __name__ == "__main__":
    # Initialize and launch dictation system
    controller = Voice2TextController()
    controller.run()