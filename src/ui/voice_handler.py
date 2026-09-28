import io
import requests
from src.utils.optional_import import optional_import

sounddevice = optional_import(
    "sounddevice", hint="Audio streaming needs the PortAudio system library."
)
sd = sounddevice  # backwards-compatible alias for the original `import sounddevice as sd`
import soundfile as sf
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class VoiceHandler:
    """
    Voice input/output handler for desktop mate
    Integrates with Aether backend APIs
    """
    
    def __init__(self, backend_url="http://localhost:8000"):
        self.backend_url = backend_url
        self.sample_rate = 16000
        self.is_recording = False
        self.recording_data = []
    
    def start_recording(self):
        """Start recording voice input"""
        logger.info("🎤 Starting voice recording...")
        self.is_recording = True
        self.recording_data = []
        
        def callback(indata, frames, time, status):
            if status:
                logger.warning(f"Recording status: {status}")
            if self.is_recording:
                self.recording_data.append(indata.copy())
        
        self.stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            callback=callback,
            dtype=np.float32
        )
        self.stream.start()
    
    def stop_recording(self):
        """Stop recording and return audio data"""
        logger.info("🛑 Stopping voice recording...")
        self.is_recording = False
        
        if hasattr(self, 'stream'):
            self.stream.stop()
            self.stream.close()
        
        if self.recording_data:
            audio_data = np.concatenate(self.recording_data, axis=0)
            return audio_data
        return None
    
    def transcribe(self, audio_data):
        """Transcribe audio to text using Aether backend"""
        try:
            # Convert numpy array to WAV bytes
            buffer = io.BytesIO()
            sf.write(buffer, audio_data, self.sample_rate, format='WAV')
            buffer.seek(0)
            
            # Send to backend
            files = {'audio': ('audio.wav', buffer, 'audio/wav')}
            response = requests.post(
                f"{self.backend_url}/api/v1/voice/transcribe",
                files=files,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('text', '')
                logger.info(f"📝 Transcribed: {text}")
                return text
            else:
                logger.error(f"❌ Transcription failed: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"❌ Transcription error: {e}")
            return None
    
    def get_response(self, user_text):
        """Get AI response from Aether backend"""
        try:
            response = requests.post(
                f"{self.backend_url}/api/v1/chat/conversation",
                json={
                    "message": user_text,
                    "session_id": "desktop-mate-session",
                    "use_voice": True
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_text = result.get('content', '') or result.get('response', '')
                logger.info(f"🤖 AI Response: {ai_text}")
                return ai_text
            else:
                logger.error(f"❌ Chat failed: {response.status_code}")
                return "I'm having trouble connecting to my brain right now."
        
        except Exception as e:
            logger.error(f"❌ Chat error: {e}")
            return "Sorry, I encountered an error."
    
    def speak(self, text):
        """Speak text using Aether TTS"""
        try:
            response = requests.post(
                f"{self.backend_url}/api/v1/voice/synthesize",
                json={"text": text},
                timeout=30
            )
            
            if response.status_code == 200:
                audio_bytes = response.content
                logger.info(f"🔊 Received TTS audio: {len(audio_bytes)} bytes")
                
                # Play audio
                self.play_audio(audio_bytes)
                return True
            else:
                logger.error(f"❌ TTS failed: {response.status_code}")
                return False
        
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return False
    
    def play_audio(self, audio_bytes):
        """Play audio from bytes"""
        try:
            # Save to temp file and play with Windows Media Player
            import tempfile
            import subprocess
            
            # Create temp WAV file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
            temp_file.write(audio_bytes)
            temp_file.close()
            
            # Play with Windows Media Player (guaranteed to work)
            subprocess.run(['powershell', '-c', f'(New-Object Media.SoundPlayer "{temp_file.name}").PlaySync()'], 
                          check=False, timeout=10)
            
            # Cleanup
            import os
            try:
                os.unlink(temp_file.name)
            except:
                pass
            
            logger.info("✅ Audio playback complete")
        
        except Exception as e:
            logger.error(f"❌ Audio playback error: {e}")
    
    def full_conversation(self):
        """Full voice conversation flow"""
        # Record
        self.start_recording()
        input("Press Enter to stop recording...")
        audio_data = self.stop_recording()
        
        if audio_data is None:
            return None, None
        
        # Transcribe
        user_text = self.transcribe(audio_data)
        if not user_text:
            return None, None
        
        # Get response
        ai_text = self.get_response(user_text)
        
        # Speak response
        self.speak(ai_text)
        
        return user_text, ai_text
