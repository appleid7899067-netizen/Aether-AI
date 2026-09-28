import sys
import signal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logger import get_logger
from src.config import settings
from src.pipeline import get_pipeline, PipelineConfig

logger = get_logger(__name__)

# Global pipeline instance for cleanup
pipeline = None


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    logger.info("\n🛑 Shutdown signal received...")
    if pipeline:
        pipeline.stop()
        pipeline.cleanup()
    logger.info("Aether AI shut down gracefully")
    sys.exit(0)


def main():
    global pipeline
    
    # Force UTF-8 encoding for stdout/stderr to prevent emoji crashes on Windows
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
    logger.info("=" * 60)
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"Environment: {settings.environment}")
    logger.info("=" * 60)

    logger.info("Configuration loaded successfully")
    logger.info(f"API Server: {settings.api_host}:{settings.api_port}")
    logger.info(f"Wake Word: {settings.wake_word}")
    logger.info(f"Voice Provider: {settings.voice_provider}")
    
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize voice pipeline configuration
        config = PipelineConfig(
            wake_word=settings.wake_word,
            wake_word_sensitivity=0.5,
            porcupine_access_key=settings.porcupine_api_key,
            use_porcupine=bool(settings.porcupine_api_key),
            stt_model="base",
            stt_use_cloud=settings.voice_provider == "openai",
            stt_api_key=settings.openai_api_key,
            tts_provider=settings.voice_provider or "pyttsx3",
            tts_voice="female",
            tts_api_key=settings.openai_api_key,
            session_timeout_minutes=5,
            enable_continuous_mode=True
        )
        
        # Get pipeline instance
        pipeline = get_pipeline(config)
        
        logger.info("\n" + "=" * 60)
        logger.info("Voice Pipeline Ready")
        logger.info("=" * 60)
        logger.info(f"Wake Word: '{settings.wake_word}'")
        logger.info(f"STT Mode: {'Cloud (OpenAI)' if config.stt_use_cloud else 'Local (Whisper)'}")
        logger.info(f"TTS Mode: {config.tts_provider}")
        logger.info("=" * 60)
        
        # Start the pipeline
        logger.info("\n🚀 Starting voice interaction pipeline...")
        pipeline.start()
        
        # 🤖 Start Autonomous Proactive Agent (runs in background)
        try:
            from src.cognitive.agents.proactive_agent import start_autonomous_mode
            proactive = start_autonomous_mode()
            logger.info("🤖 Proactive Autonomous Agent started — Aether now self-directs!")
        except Exception as e:
            logger.warning(f"Proactive agent not started: {e}")

        # 👁️ Start Real-Time Vision Loop (every 2s)
        try:
            from src.perception.vision.realtime_vision import start_realtime_vision
            vision = start_realtime_vision()
            logger.info("👁️ Real-Time Vision started — Aether can now see the screen live!")
        except Exception as e:
            logger.warning(f"Real-time vision not started: {e}")

        logger.info("\n✅ Aether AI is now listening!")
        logger.info(f"💡 Say '{settings.wake_word}' to activate")
        logger.info("Press Ctrl+C to stop\n")
        
        # Keep main thread alive
        import time
        while pipeline.is_running:
            time.sleep(1)
            
            # Periodic cleanup of expired sessions
            if hasattr(pipeline, '_cleanup_expired_sessions'):
                pipeline._cleanup_expired_sessions()
    
    except KeyboardInterrupt:
        logger.info("\n🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        raise
    finally:
        if pipeline:
            pipeline.stop()
            pipeline.cleanup()
        logger.info("Aether AI shut down successfully")


if __name__ == "__main__":
    main()
