"""
Intelligent Element Detection System
Multi-strategy approach for reliable UI automation across different configurations
"""
from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
import time
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import os

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DetectionStrategy(Enum):
    """Element detection strategies in order of preference"""
    IMAGE_MATCH = "image_match"
    OCR_TEXT = "ocr_text"
    ACCESSIBILITY = "accessibility"
    COLOR_PATTERN = "color_pattern"
    RELATIVE_POSITION = "relative_position"


@dataclass
class ElementLocation:
    """Detected element location and metadata"""
    x: int
    y: int
    width: int
    height: int
    confidence: float
    strategy: DetectionStrategy
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of element"""
        return (self.x + self.width // 2, self.y + self.height // 2)


class ElementDetector:
    """
    Intelligent UI element detector with multiple fallback strategies
    Replaces hardcoded coordinates with adaptive detection
    """
    
    def __init__(self, templates_dir: str = "ui_templates"):
        self.templates_dir = templates_dir
        self.cache: Dict[str, ElementLocation] = {}
        self.cache_ttl = 5  # seconds
        self.last_cache_time: Dict[str, float] = {}
        
        # Create templates directory if it doesn't exist
        os.makedirs(templates_dir, exist_ok=True)
        
        logger.info(f"ElementDetector initialized with templates dir: {templates_dir}")
    
    def find_element(
        self,
        identifier: str,
        strategies: Optional[List[DetectionStrategy]] = None,
        use_cache: bool = True
    ) -> Optional[ElementLocation]:
        """
        Find UI element using multiple detection strategies
        
        Args:
            identifier: Element identifier (image path, text, accessibility name)
            strategies: Ordered list of strategies to try (defaults to all)
            use_cache: Whether to use cached location
            
        Returns:
            ElementLocation if found, None otherwise
        """
        # Check cache first
        if use_cache and identifier in self.cache:
            cached_time = self.last_cache_time.get(identifier, 0)
            if time.time() - cached_time < self.cache_ttl:
                logger.debug(f"Using cached location for '{identifier}'")
                return self.cache[identifier]
        
        # Default to all strategies
        if strategies is None:
            strategies = [
                DetectionStrategy.IMAGE_MATCH,
                DetectionStrategy.OCR_TEXT,
                DetectionStrategy.ACCESSIBILITY,
                DetectionStrategy.COLOR_PATTERN,
                DetectionStrategy.RELATIVE_POSITION
            ]
        
        # Try each strategy in order
        for strategy in strategies:
            try:
                location = self._try_strategy(identifier, strategy)
                if location:
                    logger.info(f"Found '{identifier}' using {strategy.value} at {location.center}")
                    # Cache the result
                    self.cache[identifier] = location
                    self.last_cache_time[identifier] = time.time()
                    return location
            except Exception as e:
                logger.debug(f"Strategy {strategy.value} failed for '{identifier}': {e}")
                continue
        
        logger.warning(f"Element '{identifier}' not found with any strategy")
        return None
    
    def _try_strategy(self, identifier: str, strategy: DetectionStrategy) -> Optional[ElementLocation]:
        """Try a specific detection strategy"""
        
        if strategy == DetectionStrategy.IMAGE_MATCH:
            return self._find_by_image(identifier)
        
        elif strategy == DetectionStrategy.OCR_TEXT:
            return self._find_by_text_ocr(identifier)
        
        elif strategy == DetectionStrategy.ACCESSIBILITY:
            return self._find_by_accessibility(identifier)
        
        elif strategy == DetectionStrategy.COLOR_PATTERN:
            return self._find_by_color(identifier)
        
        elif strategy == DetectionStrategy.RELATIVE_POSITION:
            return self._find_by_relative_position(identifier)
        
        return None
    
    def _find_by_image(self, image_path: str, confidence: float = 0.8) -> Optional[ElementLocation]:
        """Find element by image template matching"""
        try:
            # If image_path is not a full path, look in templates directory
            if not os.path.isabs(image_path):
                image_path = os.path.join(self.templates_dir, image_path)
            
            if not os.path.exists(image_path):
                logger.debug(f"Image template not found: {image_path}")
                return None
            
            location = pyautogui.locateOnScreen(image_path, confidence=confidence)
            
            if location:
                return ElementLocation(
                    x=location.left,
                    y=location.top,
                    width=location.width,
                    height=location.height,
                    confidence=confidence,
                    strategy=DetectionStrategy.IMAGE_MATCH
                )
        except Exception as e:
            logger.debug(f"Image matching failed: {e}")
        
        return None
    
    def _find_by_text_ocr(self, text: str) -> Optional[ElementLocation]:
        """Find element by text using OCR"""
        try:
            import pytesseract
            from PIL import Image
            import numpy as np
            
            # Capture screen
            screenshot = pyautogui.screenshot()
            
            # Use pytesseract to find text locations
            data = pytesseract.image_to_data(screenshot, output_type=pytesseract.Output.DICT)
            
            # Search for matching text
            for i, word in enumerate(data['text']):
                if text.lower() in word.lower() and data['conf'][i] > 60:
                    x = data['left'][i]
                    y = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    
                    return ElementLocation(
                        x=x, y=y, width=w, height=h,
                        confidence=data['conf'][i] / 100.0,
                        strategy=DetectionStrategy.OCR_TEXT
                    )
        except ImportError:
            logger.debug("pytesseract not available for OCR detection")
        except Exception as e:
            logger.debug(f"OCR detection failed: {e}")
        
        return None
    
    def _find_by_accessibility(self, name: str) -> Optional[ElementLocation]:
        """Find element using Windows accessibility API"""
        try:
            from pywinauto import Desktop
            from pywinauto.findwindows import ElementNotFoundError
            
            app = Desktop(backend="uia")
            window = app.window(active_only=True)
            
            if not window.exists():
                return None
            
            # Try to find element with accessibility name
            try:
                element = window.child_window(best_match=name, timeout=2)
                if element.exists():
                    rect = element.rectangle()
                    return ElementLocation(
                        x=rect.left,
                        y=rect.top,
                        width=rect.width(),
                        height=rect.height(),
                        confidence=0.9,
                        strategy=DetectionStrategy.ACCESSIBILITY
                    )
            except ElementNotFoundError:
                pass
        except ImportError:
            logger.debug("pywinauto not available for accessibility detection")
        except Exception as e:
            logger.debug(f"Accessibility detection failed: {e}")
        
        return None
    
    def _find_by_color(self, color_signature: str) -> Optional[ElementLocation]:
        """Find element by color pattern (for buttons, icons)"""
        # TODO: Implement color-based detection
        # This would look for specific color patterns like green buttons, red icons, etc.
        return None
    
    def _find_by_relative_position(self, position_spec: str) -> Optional[ElementLocation]:
        """
        Find element by relative position
        Format: "anchor_element:direction:distance"
        Example: "OK_button:below:50"
        """
        # TODO: Implement relative positioning
        # This would find element relative to another known element
        return None
    
    def click_element(
        self,
        identifier: str,
        offset: Tuple[int, int] = (0, 0),
        double_click: bool = False
    ) -> bool:
        """
        Find and click an element
        
        Args:
            identifier: Element identifier
            offset: (x, y) offset from element center
            double_click: Whether to double-click
            
        Returns:
            True if clicked successfully
        """
        location = self.find_element(identifier)
        
        if not location:
            logger.error(f"Cannot click '{identifier}' - element not found")
            return False
        
        center_x, center_y = location.center
        click_x = center_x + offset[0]
        click_y = center_y + offset[1]
        
        try:
            if double_click:
                pyautogui.doubleClick(click_x, click_y)
            else:
                pyautogui.click(click_x, click_y)
            
            logger.info(f"Clicked '{identifier}' at ({click_x}, {click_y})")
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False
    
    def wait_for_element(
        self,
        identifier: str,
        timeout: float = 10.0,
        poll_interval: float = 0.5
    ) -> Optional[ElementLocation]:
        """
        Wait for element to appear
        
        Args:
            identifier: Element identifier
            timeout: Maximum wait time in seconds
            poll_interval: How often to check
            
        Returns:
            ElementLocation if found within timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            location = self.find_element(identifier, use_cache=False)
            if location:
                logger.info(f"Element '{identifier}' appeared after {time.time() - start_time:.1f}s")
                return location
            time.sleep(poll_interval)
        
        logger.warning(f"Element '{identifier}' did not appear within {timeout}s")
        return None
    
    def element_exists(self, identifier: str, use_cache: bool = False) -> bool:
        """Check if element exists on screen"""
        return self.find_element(identifier, use_cache=use_cache) is not None
    
    def get_element_info(self, identifier: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about an element"""
        location = self.find_element(identifier)
        
        if not location:
            return None
        
        return {
            "identifier": identifier,
            "location": {
                "x": location.x,
                "y": location.y,
                "width": location.width,
                "height": location.height,
                "center": location.center
            },
            "confidence": location.confidence,
            "strategy": location.strategy.value
        }
    
    def clear_cache(self):
        """Clear cached element locations"""
        self.cache.clear()
        self.last_cache_time.clear()
        logger.debug("Element cache cleared")
    
    def capture_template(self, element_name: str, region: Tuple[int, int, int, int]) -> str:
        """
        Capture a template image for future detection
        
        Args:
            element_name: Name for the template
            region: (x, y, width, height) region to capture
            
        Returns:
            Path to saved template
        """
        try:
            screenshot = pyautogui.screenshot(region=region)
            template_path = os.path.join(self.templates_dir, f"{element_name}.png")
            screenshot.save(template_path)
            logger.info(f"Template saved: {template_path}")
            return template_path
        except Exception as e:
            logger.error(f"Template capture failed: {e}")
            raise


# Global instance
element_detector = ElementDetector()
