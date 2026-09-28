"""
Live Vision Monitoring System - REAL-TIME SCREEN AWARENESS
Continuously monitors screen and provides context to Aether AI
"""

import threading
import time
import queue
from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
import numpy as np
from PIL import Image
import imagehash
from typing import Optional, Dict, List, Callable
from datetime import datetime
from src.features.vision import VisionSystem
from src.utils.logger import get_logger

logger = get_logger(__name__)


class LiveVisionMonitor:
    """
    Continuous screen monitoring system with intelligent change detection
    
    Features:
    - Real-time screen capture every N seconds
    - Smart change detection using perceptual hashing
    - Automatic vision analysis when screen changes
    - Proactive context awareness
    - Background monitoring thread
    """
    
    def __init__(
        self, 
        monitor_interval: float = 3.0,
        change_threshold: int = 10,
        auto_analyze: bool = True
    ):
        """
        Initialize live vision monitor
        
        Args:
            monitor_interval: Seconds between screen captures (default 3s)
            change_threshold: Hamming distance threshold for change detection
            auto_analyze: Whether to automatically analyze screen on changes
        """
        self.monitor_interval = monitor_interval
        self.change_threshold = change_threshold
        self.auto_analyze = auto_analyze
        
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        self.last_screen_hash: Optional[imagehash.ImageHash] = None
        self.last_analysis: Optional[str] = None
        self.last_analysis_time: Optional[datetime] = None
        
        self.screen_history: List[Dict] = []
        self.max_history = 10
        
        self.vision_queue = queue.Queue(maxsize=5)
        
        self.on_screen_change: Optional[Callable] = None
        self.on_analysis_complete: Optional[Callable] = None
        
        logger.info(f"LiveVisionMonitor initialized - interval={monitor_interval}s, threshold={change_threshold}")
    
    def start(self):
        """Start live monitoring in background thread"""
        if self.is_running:
            logger.warning("Live vision monitoring already running")
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info("[LIVE VISION] MONITORING STARTED - Real-time screen awareness active")
    
    def stop(self):
        """Stop live monitoring"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("[LIVE VISION] Monitoring stopped")
    
    def _monitor_loop(self):
        """Main monitoring loop - runs in background"""
        logger.info("Live vision monitor loop started")
        
        while self.is_running:
            try:
                # Capture current screen
                screenshot = pyautogui.screenshot()
                
                # Calculate perceptual hash
                current_hash = imagehash.phash(screenshot)
                
                # Check if screen changed significantly
                if self.last_screen_hash is None:
                    # First capture
                    screen_changed = True
                    hash_distance = 0
                else:
                    hash_distance = current_hash - self.last_screen_hash
                    screen_changed = hash_distance > self.change_threshold
                
                if screen_changed:
                    logger.info(f"[SCREEN CHANGE] Detected! Hash distance: {hash_distance}")
                    
                    # Save to history
                    self._add_to_history(screenshot, current_hash, hash_distance)
                    
                    # Trigger change callback
                    if self.on_screen_change:
                        try:
                            self.on_screen_change(screenshot, hash_distance)
                        except Exception as e:
                            logger.error(f"Screen change callback error: {e}")
                    
                    # Auto-analyze if enabled
                    if self.auto_analyze:
                        self._queue_analysis(screenshot)
                
                self.last_screen_hash = current_hash
                
                # Process vision analysis queue
                self._process_vision_queue()
                
                # Sleep until next check
                time.sleep(self.monitor_interval)
                
            except Exception as e:
                logger.error(f"Monitor loop error: {e}")
                time.sleep(5)
    
    def _queue_analysis(self, screenshot: Image.Image):
        """Queue screenshot for vision analysis"""
        try:
            self.vision_queue.put_nowait(screenshot)
            logger.info("[VISION QUEUE] Screenshot queued for vision analysis")
        except queue.Full:
            logger.warning("Vision queue full, skipping analysis")
    
    def _process_vision_queue(self):
        """Process queued screenshots for vision analysis"""
        if self.vision_queue.empty():
            return
        
        try:
            screenshot = self.vision_queue.get_nowait()
            
            # Save screenshot temporarily
            temp_path = f"temp_vision_{int(time.time())}.png"
            screenshot.save(temp_path)
            
            # Analyze with vision system
            logger.info("[VISION ANALYSIS] Running vision analysis on screen change...")
            
            # Create detailed prompt
            prompt = """Analyze this screen and provide:
1. What application/window is currently active
2. What the user is doing or trying to do
3. Any important information visible (errors, prompts, data)
4. Suggested next actions the user might want to take

Be concise but thorough."""
            
            analysis = VisionSystem.analyze_screen(prompt)
            
            # Clean up temp file
            try:
                import os
                os.remove(temp_path)
            except:
                pass
            
            # Store analysis
            self.last_analysis = analysis
            self.last_analysis_time = datetime.now()
            
            logger.info(f"[VISION ANALYSIS] Complete: {analysis[:100]}...")
            
            # Trigger analysis callback
            if self.on_analysis_complete:
                try:
                    self.on_analysis_complete(analysis)
                except Exception as e:
                    logger.error(f"Analysis callback error: {e}")
            
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Vision analysis error: {e}")
    
    def _add_to_history(self, screenshot: Image.Image, screen_hash: imagehash.ImageHash, distance: int):
        """Add screen capture to history"""
        entry = {
            "timestamp": datetime.now(),
            "hash": screen_hash,
            "distance": distance,
            "analysis": None
        }
        
        self.screen_history.append(entry)
        
        # Keep only recent history
        if len(self.screen_history) > self.max_history:
            self.screen_history.pop(0)
    
    def get_current_context(self) -> Optional[str]:
        """Get the most recent screen analysis"""
        if self.last_analysis:
            age = (datetime.now() - self.last_analysis_time).total_seconds()
            return f"[Screen analysis from {age:.0f}s ago]: {self.last_analysis}"
        return None
    
    def get_screen_history_summary(self) -> str:
        """Get summary of recent screen changes"""
        if not self.screen_history:
            return "No screen history available"
        
        summary = f"Last {len(self.screen_history)} screen changes:\n"
        for i, entry in enumerate(reversed(self.screen_history[-5:])):
            time_ago = (datetime.now() - entry['timestamp']).total_seconds()
            summary += f"  {i+1}. {time_ago:.0f}s ago - Change magnitude: {entry['distance']}\n"
        
        return summary
    
    def force_analysis(self) -> str:
        """Force immediate screen analysis"""
        logger.info("[FORCED ANALYSIS] Capturing screen now...")
        screenshot = pyautogui.screenshot()
        
        temp_path = f"forced_vision_{int(time.time())}.png"
        screenshot.save(temp_path)
        
        prompt = """Describe everything you see on this screen in detail:
- Active windows and applications
- Text content visible
- UI elements and their states
- Any errors, warnings, or important messages
- Current user context and what they're likely doing

Provide comprehensive analysis."""
        
        analysis = VisionSystem.analyze_screen(prompt)
        
        try:
            import os
            os.remove(temp_path)
        except:
            pass
        
        self.last_analysis = analysis
        self.last_analysis_time = datetime.now()
        
        return analysis
    
    def is_active(self) -> bool:
        """Check if monitoring is active"""
        return self.is_running
    
    def get_status(self) -> Dict:
        """Get monitor status"""
        return {
            "running": self.is_running,
            "interval": self.monitor_interval,
            "auto_analyze": self.auto_analyze,
            "history_count": len(self.screen_history),
            "last_analysis": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            "queue_size": self.vision_queue.qsize()
        }


# Global instance
live_monitor = LiveVisionMonitor(
    monitor_interval=1.0,
    change_threshold=8,
    auto_analyze=True
)


def start_live_monitoring():
    """Start global live vision monitoring"""
    live_monitor.start()


def stop_live_monitoring():
    """Stop global live vision monitoring"""
    live_monitor.stop()


def get_live_context() -> Optional[str]:
    """Get current live screen context"""
    return live_monitor.get_current_context()


def force_screen_analysis() -> str:
    """Force immediate screen analysis"""
    return live_monitor.force_analysis()
