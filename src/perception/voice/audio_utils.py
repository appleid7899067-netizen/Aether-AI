import numpy as np
from src.utils.optional_import import optional_import

pyaudio = optional_import(
    "pyaudio", hint="Microphone capture needs the PortAudio system library."
)
import wave
import io
import logging
from typing import Optional, Callable
from collections import deque
import webrtcvad

logger = logging.getLogger(__name__)


class AudioConfig:
    SAMPLE_RATE = 16000
    CHANNELS = 1
    FORMAT = pyaudio.paInt16
    CHUNK_SIZE = 1024
    FRAME_DURATION_MS = 30
    VAD_MODE = 3
    ENERGY_THRESHOLD = 1000
    SILENCE_DURATION_MS = 1500


class AudioInputHandler:
    def __init__(
        self,
        sample_rate: int = AudioConfig.SAMPLE_RATE,
        channels: int = AudioConfig.CHANNELS,
        chunk_size: int = AudioConfig.CHUNK_SIZE,
        vad_enabled: bool = True
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.vad_enabled = vad_enabled
        
        self.audio = pyaudio.PyAudio()
        self.stream: Optional[pyaudio.Stream] = None
        self.vad = webrtcvad.Vad(AudioConfig.VAD_MODE) if vad_enabled else None
        
        self.buffer = deque(maxlen=100)
        self.is_recording = False
        
        logger.info(f"AudioInputHandler initialized: {sample_rate}Hz, {channels} channel(s)")

    def start_stream(self):
        if self.stream is not None:
            logger.warning("Stream already started")
            return
        
        try:
            self.stream = self.audio.open(
                format=AudioConfig.FORMAT,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            self.stream.start_stream()
            logger.info("Audio stream started")
        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            raise

    def stop_stream(self):
        if self.stream is None:
            return
        
        try:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
            logger.info("Audio stream stopped")
        except Exception as e:
            logger.error(f"Failed to stop audio stream: {e}")

    def _audio_callback(self, in_data, frame_count, time_info, status):
        if status:
            logger.warning(f"Audio callback status: {status}")
        
        audio_data = np.frombuffer(in_data, dtype=np.int16)
        
        # Do NOT normalize chunks individually, it breaks VAD
        # Instead, apply a fixed digital gain (volume boost)
        # Convert to float for math, then clip and convert back
        audio_float = audio_data.astype(np.float32) * 2.5
        audio_clipped = np.clip(audio_float, -32768, 32767).astype(np.int16)
        
        # Debug Log Energy occasionally (every ~100 chunks to avoid spam, or just let VAD handle it)
        # energy = self.calculate_energy(audio_clipped)
        # if energy > 1000:
        #     logger.debug(f"Mic Energy: {energy}")

        self.buffer.append(audio_clipped)
        
        return (in_data, pyaudio.paContinue)

    def read_chunk(self) -> Optional[np.ndarray]:
        if not self.buffer:
            return None
        return self.buffer.popleft()

    def read_audio(self, duration_seconds: float) -> np.ndarray:
        num_chunks = int(duration_seconds * self.sample_rate / self.chunk_size)
        audio_chunks = []
        
        for _ in range(num_chunks):
            chunk = self.read_chunk()
            if chunk is not None:
                audio_chunks.append(chunk)
        
        if not audio_chunks:
            return np.array([], dtype=np.int16)
        
        return np.concatenate(audio_chunks)

    def record_until_silence(
        self, 
        max_duration_seconds: float = 30,
        silence_duration_ms: int = AudioConfig.SILENCE_DURATION_MS,
        callback: Optional[Callable[[np.ndarray], None]] = None
    ) -> np.ndarray:
        frames = []
        silence_chunks = 0
        max_silence_chunks = int(silence_duration_ms / AudioConfig.FRAME_DURATION_MS)
        max_chunks = int(max_duration_seconds * self.sample_rate / self.chunk_size)
        
        logger.info("Recording until silence...")
        
        chunk_count = 0
        while chunk_count < max_chunks:
            chunk = self.read_chunk()
            if chunk is None:
                continue
            
            frames.append(chunk)
            chunk_count += 1
            
            if callback:
                callback(chunk)
            
            if self.is_silence(chunk):
                silence_chunks += 1
                if silence_chunks >= max_silence_chunks:
                    logger.info("Silence detected, stopping recording")
                    break
            else:
                silence_chunks = 0
        
        if not frames:
            return np.array([], dtype=np.int16)
        
        audio_data = np.concatenate(frames)
        logger.info(f"Recording complete: {len(audio_data) / self.sample_rate:.2f}s")
        return audio_data

    def is_speech(self, audio_chunk: np.ndarray) -> bool:
        if not self.vad_enabled or self.vad is None:
            return bool(self.calculate_energy(audio_chunk) > AudioConfig.ENERGY_THRESHOLD)
        
        try:
            # Energy safeguard - if energy is extremely low, it's definitely silence
            energy = self.calculate_energy(audio_chunk)
            if energy < 50: # Hard silence threshold
                return False
            
            audio_bytes = audio_chunk.tobytes()
            
            frame_size = int(self.sample_rate * AudioConfig.FRAME_DURATION_MS / 1000)
            if len(audio_chunk) < frame_size:
                # Force energy check for short chunks
                return bool(energy > AudioConfig.ENERGY_THRESHOLD)
            
            # VAD is primary
            is_speech_vad = self.vad.is_speech(audio_bytes[:frame_size * 2], self.sample_rate)
            
            # Hybrid approach: VAD AND Energy (to avoid low-level electronic noise triggering VAD)
            return bool(is_speech_vad and energy > (AudioConfig.ENERGY_THRESHOLD / 2))
        except Exception as e:
            logger.warning(f"VAD error, falling back to energy: {e}")
            return bool(self.calculate_energy(audio_chunk) > AudioConfig.ENERGY_THRESHOLD)

    def is_silence(self, audio_chunk: np.ndarray) -> bool:
        return bool(not self.is_speech(audio_chunk))

    @staticmethod
    def calculate_energy(audio_chunk: np.ndarray) -> float:
        return np.sqrt(np.mean(audio_chunk.astype(float) ** 2))

    @staticmethod
    def normalize_audio(audio_data: np.ndarray) -> np.ndarray:
        max_val = np.max(np.abs(audio_data))
        if max_val == 0:
            return audio_data
        
        normalized = audio_data.astype(np.float32) / max_val
        return (normalized * 32767).astype(np.int16)

    @staticmethod
    def apply_noise_reduction(audio_data: np.ndarray, noise_reduce_strength: float = 0.5) -> np.ndarray:
        if len(audio_data) < 100:
            return audio_data
        
        noise_profile = np.median(np.abs(audio_data[:100]))
        
        threshold = noise_profile * noise_reduce_strength
        mask = np.abs(audio_data) > threshold
        
        return audio_data * mask

    def save_to_wav(self, audio_data: np.ndarray, filename: str):
        try:
            with wave.open(filename, 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(AudioConfig.FORMAT))
                wf.setframerate(self.sample_rate)
                wf.writeframes(audio_data.tobytes())
            logger.info(f"Audio saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save audio: {e}")

    def audio_to_bytes(self, audio_data: np.ndarray) -> bytes:
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(AudioConfig.FORMAT))
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_data.tobytes())
        return buffer.getvalue()

    def list_audio_devices(self) -> list[dict]:
        devices = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': device_info['name'],
                    'sample_rate': int(device_info['defaultSampleRate']),
                    'channels': device_info['maxInputChannels']
                })
        return devices

    def cleanup(self):
        self.stop_stream()
        self.audio.terminate()
        logger.info("AudioInputHandler cleaned up")

    def __enter__(self):
        self.start_stream()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
