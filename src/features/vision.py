from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
import base64
import requests
import os
import time
from typing import Optional
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)

class VisionSystem:
    @staticmethod
    def capture_screen(path: str = "screenshot.png") -> str:
        """Capture screen and return base64 string"""
        try:
            timestamp = int(time.time())
            path = f"screenshot_{timestamp}.png"
            
            # Capture
            logger.info("Capturing screen...")
            screenshot = pyautogui.screenshot()
            screenshot.save(path)
            
            # Convert to base64
            with open(path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Cleanup
            try:
                os.remove(path)
            except:
                pass
                
            return encoded_string
        except Exception as e:
            logger.error(f"Screen Capture Failed: {e}")
            return ""

    async def analyze_screen(prompt: str = "Describe this screen in detail.") -> str:
        """Analyze screen using ModelRouter (TaskType.VISION)"""
        from src.cognitive.llm.model_router import router
        from src.cognitive.llm.providers.base import TaskType
        
        base64_image = VisionSystem.capture_screen()
        if not base64_image:
            return "Error: Failed to capture screen."
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
                ]
            }
        ]
        
        try:
            logger.info(f"Sending Vision Request via ModelRouter (TaskType.VISION)...")
            # We use route_with_fallback for robustness
            response = await router.route_with_fallback(
                messages=messages,
                task_type=TaskType.VISION,
                max_tokens=1000,
                temperature=0.3
            )
            
            if response and hasattr(response, 'content'):
                logger.info("Vision Analysis Received via Router.")
                return response.content
            else:
                logger.error("Vision API Error: Router returned invalid response")
                return "Vision Error: Invalid response from router"
        except Exception as e:
            logger.error(f"Vision Request Failed: {e}")
            return f"Vision Request Failed: {str(e)}"

vision_system = VisionSystem()
