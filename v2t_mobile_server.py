#!/usr/bin/env python3
"""
Voice2Text Mobile API Server
============================
Web service extension for iOS/mobile integration with existing whisper.cpp infrastructure.

Features:
- RESTful API for audio processing
- Web interface for mobile browsers
- Real-time audio upload and transcription
- Cross-platform compatibility
"""

import time
import wave
import tempfile
import subprocess
from pathlib import Path
import base64

from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS

import whisper_runner

class Voice2TextMobileServer:
    """Mobile-optimized API server for remote dictation processing."""
    
    def __init__(self):
        # Existing whisper.cpp configuration
        self.whisper_path = Path("G:/whisper.cpp/build/bin/Release/whisper-cli.exe")
        self.model_path = Path("G:/whisper.cpp/ggml-base.en.bin")
        self.temp_dir = tempfile.mkdtemp(prefix="voice2text_mobile_")
        
        # Flask application setup
        self.app = Flask(__name__)
        CORS(self.app)  # Enable cross-origin requests from mobile browsers
        
        # Configure API endpoints
        self.setup_routes()
        
        print("🌐 Voice2Text Mobile API Server Initialized")
        print(f"🤖 Whisper Engine: {self.model_path.name}")
        print("📱 Ready for mobile connections")
    
    def setup_routes(self):
        """Configure REST API endpoints and web interface."""
        
        @self.app.route('/')
        def mobile_interface():
            """Serve mobile-optimized web interface."""
            return render_template_string(MOBILE_INTERFACE_HTML)
        
        @self.app.route('/api/transcribe', methods=['POST'])
        def transcribe_audio():
            """Process audio data and return transcription."""
            try:
                # Validate request format
                if 'audio' not in request.json:
                    return jsonify({'error': 'No audio data provided'}), 400
                
                # Decode base64 audio data
                audio_data = base64.b64decode(request.json['audio'])

                t0 = time.perf_counter()
                transcription = self.process_mobile_audio(audio_data)
                elapsed = time.perf_counter() - t0

                if transcription:
                    return jsonify({
                        'success': True,
                        'transcription': transcription,
                        'processing_time': f"{elapsed:.2f}s",
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'No speech detected in audio'
                    }), 400
            
            except Exception as e:
                return jsonify({
                    'success': False,
                    'error': f'Processing failed: {str(e)}'
                }), 500
        
        @self.app.route('/api/status', methods=['GET'])
        def server_status():
            """Return server operational status."""
            return jsonify({
                'status': 'operational',
                'model': self.model_path.name,
                'capabilities': ['transcription', 'gpu_acceleration'],
                'version': '1.0.0'
            })
    
    def process_mobile_audio(self, audio_data):
        """Process mobile-captured audio through whisper.cpp pipeline."""
        timestamp = int(time.time() * 1000)  # Use milliseconds for uniqueness
        
        # Detect format and use appropriate extension from start
        audio_format = self._detect_audio_format(audio_data)
        if audio_format == 'webm':
            temp_input_path = Path(self.temp_dir) / f"mobile_input_{timestamp}.webm"
        elif audio_format == 'ogg':
            temp_input_path = Path(self.temp_dir) / f"mobile_input_{timestamp}.ogg"
        else:
            temp_input_path = Path(self.temp_dir) / f"mobile_input_{timestamp}.wav"
            
        temp_wav_path = Path(self.temp_dir) / f"mobile_recording_{timestamp}.wav"
        
        try:
            # Save raw audio data with proper extension
            with open(temp_input_path, 'wb') as audio_file:
                audio_file.write(audio_data)
            
            print(f"🔄 Processing mobile audio ({len(audio_data)} bytes, format: {audio_format})...")
            
            # Skip pydub - use FFmpeg directly via subprocess
            try:
                # Find FFmpeg
                ffmpeg_path = "C:\\ProgramData\\chocolatey\\bin\\ffmpeg.exe"
                if not Path(ffmpeg_path).exists():
                    ffmpeg_path = "ffmpeg.exe"  # Try PATH
                
                print(f"🔧 Using FFmpeg directly: {ffmpeg_path}")
                
                # Convert WebM to WAV using FFmpeg directly
                ffmpeg_cmd = [
                    ffmpeg_path,
                    "-i", str(temp_input_path),     # Input WebM file
                    "-ar", "16000",                 # 16kHz sample rate
                    "-ac", "1",                     # Mono (1 channel)
                    "-sample_fmt", "s16",           # 16-bit samples
                    "-y",                           # Overwrite output
                    str(temp_wav_path)              # Output WAV file
                ]
                
                print(f"🔧 Running: {' '.join(ffmpeg_cmd)}")
                
                result = subprocess.run(
                    ffmpeg_cmd,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    print(f"✅ Audio converted successfully using direct FFmpeg")
                    process_file = temp_wav_path
                else:
                    print(f"❌ FFmpeg conversion failed: {result.stderr}")
                    raise Exception("FFmpeg conversion failed")
                
                
            except Exception as pydub_error:
                print(f"⚠️  pydub conversion failed: {pydub_error}")
                print(f"🔄 Using direct whisper.cpp processing...")
                
                # Use original file directly - whisper.cpp can handle WebM/OGG
                process_file = temp_input_path
            
            print(f"🔄 Processing audio with whisper.cpp...")

            result = whisper_runner.run_whisper_cli(
                self.whisper_path,
                self.model_path,
                process_file,
                threads=8,
                timeout=30,
            )

            if result.returncode == 0:
                transcription = whisper_runner.extract_transcription(result.stdout)
                print(f"✅ Mobile transcription: '{transcription}'")
                return transcription.strip()
            else:
                print(f"❌ Transcription failed: {result.stderr}")
                print(f"📋 Command used: {' '.join(cmd)}")
                return None
        
        except Exception as e:
            print(f"❌ Mobile processing error: {e}")
            return None
        finally:
            # Cleanup temporary files safely
            time.sleep(0.1)  # Brief pause to ensure files are released
            
            for temp_file in [temp_input_path, temp_wav_path]:
                try:
                    if temp_file.exists():
                        temp_file.unlink()
                except Exception as cleanup_error:
                    print(f"⚠️  Cleanup warning: {cleanup_error}")
    
    def _detect_audio_format(self, audio_data):
        """Detect audio format from binary data."""
        # Check for WebM signature
        if audio_data.startswith(b'\x1a\x45\xdf\xa3'):
            return 'webm'
        # Check for OGG signature  
        elif audio_data.startswith(b'OggS'):
            return 'ogg'
        # Check for WAV signature
        elif audio_data.startswith(b'RIFF') and b'WAVE' in audio_data[:12]:
            return 'wav'
        # Default assumption
        return 'webm'

    def run_server(self, host='0.0.0.0', port=5000, debug=False, ssl_context=None):
        """Launch mobile API server with optional HTTPS support."""
        protocol = "https" if ssl_context else "http"
        print(f"\n🚀 Voice2Text Mobile Server Starting")
        print(f"📱 Mobile Interface: {protocol}://{host}:{port}")
        print(f"🔗 API Endpoint: {protocol}://{host}:{port}/api/transcribe")
        if ssl_context:
            print("🔒 HTTPS Enabled - iOS microphone access authorized")
        print("="*50)
        
        self.app.run(host=host, port=port, debug=debug, ssl_context=ssl_context)

# Mobile-optimized web interface
MOBILE_INTERFACE_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice2Text Mobile</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }
        .container {
            max-width: 400px;
            margin: 0 auto;
            text-align: center;
        }
        .record-btn {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: none;
            background: #ff4757;
            color: white;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            margin: 20px 0;
            transition: all 0.3s ease;
            box-shadow: 0 8px 16px rgba(0,0,0,0.3);
        }
        .record-btn:active {
            transform: scale(0.95);
        }
        .record-btn.recording {
            background: #ff6b7a;
            animation: pulse 1s infinite;
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(255, 71, 87, 0.7); }
            70% { box-shadow: 0 0 0 20px rgba(255, 71, 87, 0); }
            100% { box-shadow: 0 0 0 0 rgba(255, 71, 87, 0); }
        }
        .result-area {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
            min-height: 100px;
            backdrop-filter: blur(10px);
        }
        .copy-btn {
            background: #3742fa;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            margin: 10px;
        }
        .status {
            font-size: 14px;
            opacity: 0.8;
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 Voice2Text Mobile</h1>
        <p>Tap to start recording, tap again to stop</p>
        
        <button class="record-btn" id="recordBtn" onclick="toggleRecording()" ontouchstart="toggleRecording()">
            TAP TO<br>RECORD
        </button>
        
        <div class="status" id="status">Ready to record</div>
        
        <div class="result-area" id="resultArea">
            <p>Your transcription will appear here...</p>
        </div>
        
        <button class="copy-btn" id="copyBtn" onclick="copyText()" style="display:none;">
            📋 Copy Text
        </button>
    </div>

    <script>
        let mediaRecorder;
        let audioChunks = [];
        let isRecording = false;
        let recordingStartTime = null;

        async function toggleRecording() {
            // Prevent rapid double-taps
            if (event) {
                event.preventDefault();
            }
            
            if (isRecording) {
                stopRecording();
            } else {
                startRecording();
            }
        }

        async function startRecording() {
            if (isRecording) return;
            
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                recordingStartTime = Date.now();
                
                mediaRecorder.ondataavailable = event => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = processAudio;
                
                mediaRecorder.start();
                isRecording = true;
                
                // Update UI for recording state
                document.getElementById('recordBtn').classList.add('recording');
                document.getElementById('recordBtn').innerHTML = 'STOP<br>RECORDING';
                document.getElementById('status').textContent = 'Recording... Tap again to stop';
                
                // Start duration counter
                updateRecordingDuration();
                
            } catch (error) {
                document.getElementById('status').textContent = 'Error: Could not access microphone';
            }
        }

        function stopRecording() {
            if (!isRecording || !mediaRecorder) return;
            
            // Check for accidental quick taps (like desktop version)
            const recordingDuration = Date.now() - recordingStartTime;
            if (recordingDuration < 500) {
                document.getElementById('status').textContent = 'Recording too short - tap again to start new recording';
                resetToIdleState();
                return;
            }
            
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            isRecording = false;
            
            resetToIdleState();
            document.getElementById('status').textContent = 'Processing audio...';
        }

        function resetToIdleState() {
            document.getElementById('recordBtn').classList.remove('recording');
            document.getElementById('recordBtn').innerHTML = 'TAP TO<br>RECORD';
            recordingStartTime = null;
        }

        function updateRecordingDuration() {
            if (!isRecording) return;
            
            const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
            document.getElementById('status').textContent = `Recording... ${elapsed}s (tap again to stop)`;
            
            setTimeout(updateRecordingDuration, 1000);
        }

        async function processAudio() {
            const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
            const reader = new FileReader();
            
            reader.onload = async function() {
                const audioData = reader.result.split(',')[1]; // Remove data URL prefix
                
                try {
                    const response = await fetch('/api/transcribe', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ audio: audioData })
                    });
                    
                    const result = await response.json();
                    
                    if (result.success) {
                        document.getElementById('resultArea').innerHTML = 
                            `<p><strong>Transcription:</strong></p><p>"${result.transcription}"</p>`;
                        document.getElementById('copyBtn').style.display = 'inline-block';
                        document.getElementById('status').textContent = 'Transcription complete! Ready for next recording';
                        window.lastTranscription = result.transcription;
                    } else {
                        document.getElementById('resultArea').innerHTML = 
                            `<p style="color: #ff6b7a;">Error: ${result.error}</p>`;
                        document.getElementById('status').textContent = 'Processing failed - tap to try again';
                    }
                } catch (error) {
                    document.getElementById('resultArea').innerHTML = 
                        `<p style="color: #ff6b7a;">Network error: Could not connect to server</p>`;
                    document.getElementById('status').textContent = 'Connection failed';
                }
            };
            
            reader.readAsDataURL(audioBlob);
        }

        function copyText() {
            if (window.lastTranscription) {
                navigator.clipboard.writeText(window.lastTranscription).then(() => {
                    document.getElementById('status').textContent = 'Text copied to clipboard!';
                    setTimeout(() => {
                        document.getElementById('status').textContent = 'Ready for next recording';
                    }, 2000);
                });
            }
        }
    </script>
</body>
</html>
'''

if __name__ == "__main__":
    # Initialize and launch mobile server
    server = Voice2TextMobileServer()
    server.run_server(host='0.0.0.0', port=5000, debug=False)