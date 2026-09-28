"""
Window Management for Multi-Application Workflows
Handles window positioning, focus, and relative coordinate management
"""
from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
import time
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

from src.utils.logger import get_logger

logger = get_logger(__name__)


class WindowPosition(Enum):
    """Predefined window positions"""
    MAXIMIZED = "maximized"
    LEFT_HALF = "left_half"
    RIGHT_HALF = "right_half"
    TOP_HALF = "top_half"
    BOTTOM_HALF = "bottom_half"
    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"


@dataclass
class WindowInfo:
    """Window information"""
    title: str
    rect: Tuple[int, int, int, int]  # (left, top, width, height)
    is_active: bool
    is_visible: bool
    process_id: Optional[int] = None
    
    @property
    def center(self) -> Tuple[int, int]:
        """Get window center point"""
        left, top, width, height = self.rect
        return (left + width // 2, top + height // 2)
    
    @property
    def area(self) -> int:
        """Get window area"""
        return self.rect[2] * self.rect[3]


class WindowManager:
    """Manages application windows for reliable automation"""
    
    def __init__(self):
        self.screen_width, self.screen_height = pyautogui.size()
        self.active_windows: Dict[str, WindowInfo] = {}
        logger.info(f"WindowManager initialized - Screen: {self.screen_width}x{self.screen_height}")
    
    def find_window_by_title(self, title_pattern: str, partial_match: bool = True) -> Optional[WindowInfo]:
        """
        Find window by title
        
        Args:
            title_pattern: Window title or pattern
            partial_match: Allow partial title matching
            
        Returns:
            WindowInfo if found
        """
        try:
            from pywinauto import Desktop
            from pywinauto.findwindows import ElementNotFoundError
            
            app = Desktop(backend="uia")
            
            # Find all windows
            windows = app.windows()
            
            for window in windows:
                try:
                    window_title = window.window_text()
                    
                    # Check match
                    is_match = False
                    if partial_match:
                        is_match = title_pattern.lower() in window_title.lower()
                    else:
                        is_match = title_pattern.lower() == window_title.lower()
                    
                    if is_match and window.is_visible():
                        rect = window.rectangle()
                        
                        info = WindowInfo(
                            title=window_title,
                            rect=(rect.left, rect.top, rect.width(), rect.height()),
                            is_active=window.has_focus(),
                            is_visible=window.is_visible()
                        )
                        
                        logger.info(f"Found window: '{window_title}' at {info.rect}")
                        return info
                except:
                    continue
            
            logger.warning(f"Window not found: '{title_pattern}'")
            return None
            
        except ImportError:
            logger.error("pywinauto not available for window management")
            return None
        except Exception as e:
            logger.error(f"Window search error: {e}")
            return None
    
    def activate_window(self, title_pattern: str) -> bool:
        """
        Bring window to foreground
        
        Args:
            title_pattern: Window title pattern
            
        Returns:
            True if activated successfully
        """
        try:
            from pywinauto import Desktop
            
            app = Desktop(backend="uia")
            windows = app.windows()
            
            for window in windows:
                try:
                    if title_pattern.lower() in window.window_text().lower():
                        window.set_focus()
                        logger.info(f"Activated window: '{window.window_text()}'")
                        return True
                except:
                    continue
            
            logger.warning(f"Could not activate window: '{title_pattern}'")
            return False
            
        except Exception as e:
            logger.error(f"Window activation error: {e}")
            return False
    
    def position_window(
        self,
        title_pattern: str,
        position: WindowPosition,
        custom_rect: Optional[Tuple[int, int, int, int]] = None
    ) -> bool:
        """
        Position window on screen
        
        Args:
            title_pattern: Window title pattern
            position: Predefined position or custom
            custom_rect: (left, top, width, height) for custom positioning
            
        Returns:
            True if positioned successfully
        """
        try:
            from pywinauto import Desktop
            
            # Find window
            window_info = self.find_window_by_title(title_pattern)
            if not window_info:
                return False
            
            app = Desktop(backend="uia")
            window = app.window(title_re=f".*{title_pattern}.*")
            
            # Calculate target rectangle
            if custom_rect:
                target_rect = custom_rect
            else:
                target_rect = self._calculate_position_rect(position)
            
            # Move and resize window
            left, top, width, height = target_rect
            window.move_window(left, top, width, height)
            
            logger.info(f"Positioned window '{title_pattern}' to {position.value}")
            return True
            
        except Exception as e:
            logger.error(f"Window positioning error: {e}")
            return False
    
    def _calculate_position_rect(self, position: WindowPosition) -> Tuple[int, int, int, int]:
        """Calculate window rectangle for predefined position"""
        
        w, h = self.screen_width, self.screen_height
        
        positions = {
            WindowPosition.MAXIMIZED: (0, 0, w, h),
            WindowPosition.LEFT_HALF: (0, 0, w // 2, h),
            WindowPosition.RIGHT_HALF: (w // 2, 0, w // 2, h),
            WindowPosition.TOP_HALF: (0, 0, w, h // 2),
            WindowPosition.BOTTOM_HALF: (0, h // 2, w, h // 2),
            WindowPosition.CENTER: (w // 4, h // 4, w // 2, h // 2),
            WindowPosition.TOP_LEFT: (0, 0, w // 2, h // 2),
            WindowPosition.TOP_RIGHT: (w // 2, 0, w // 2, h // 2),
            WindowPosition.BOTTOM_LEFT: (0, h // 2, w // 2, h // 2),
            WindowPosition.BOTTOM_RIGHT: (w // 2, h // 2, w // 2, h // 2)
        }
        
        return positions.get(position, (0, 0, w, h))
    
    def get_relative_coordinates(
        self,
        window_title: str,
        screen_x: int,
        screen_y: int
    ) -> Tuple[int, int]:
        """
        Convert screen coordinates to window-relative coordinates
        
        Args:
            window_title: Window title
            screen_x: Absolute screen X coordinate
            screen_y: Absolute screen Y coordinate
            
        Returns:
            (relative_x, relative_y) tuple
        """
        window_info = self.find_window_by_title(window_title)
        
        if not window_info:
            logger.warning(f"Window not found for relative coordinates: '{window_title}'")
            return (screen_x, screen_y)
        
        left, top, _, _ = window_info.rect
        relative_x = screen_x - left
        relative_y = screen_y - top
        
        return (relative_x, relative_y)
    
    def get_screen_coordinates(
        self,
        window_title: str,
        relative_x: int,
        relative_y: int
    ) -> Tuple[int, int]:
        """
        Convert window-relative coordinates to screen coordinates
        
        Args:
            window_title: Window title
            relative_x: Window-relative X coordinate
            relative_y: Window-relative Y coordinate
            
        Returns:
            (screen_x, screen_y) tuple
        """
        window_info = self.find_window_by_title(window_title)
        
        if not window_info:
            logger.warning(f"Window not found for screen coordinates: '{window_title}'")
            return (relative_x, relative_y)
        
        left, top, _, _ = window_info.rect
        screen_x = left + relative_x
        screen_y = top + relative_y
        
        return (screen_x, screen_y)
    
    def get_percentage_coordinates(
        self,
        window_title: str,
        x_percent: float,
        y_percent: float
    ) -> Tuple[int, int]:
        """
        Get coordinates as percentage of window size
        
        Args:
            window_title: Window title
            x_percent: X position as percentage (0.0 to 1.0)
            y_percent: Y position as percentage (0.0 to 1.0)
            
        Returns:
            (screen_x, screen_y) absolute coordinates
        """
        window_info = self.find_window_by_title(window_title)
        
        if not window_info:
            return (
                int(self.screen_width * x_percent),
                int(self.screen_height * y_percent)
            )
        
        left, top, width, height = window_info.rect
        
        x = left + int(width * x_percent)
        y = top + int(height * y_percent)
        
        return (x, y)
    
    def list_visible_windows(self) -> List[WindowInfo]:
        """Get list of all visible windows"""
        try:
            from pywinauto import Desktop
            
            app = Desktop(backend="uia")
            windows = app.windows()
            
            visible_windows = []
            
            for window in windows:
                try:
                    if window.is_visible():
                        rect = window.rectangle()
                        
                        info = WindowInfo(
                            title=window.window_text(),
                            rect=(rect.left, rect.top, rect.width(), rect.height()),
                            is_active=window.has_focus(),
                            is_visible=True
                        )
                        
                        visible_windows.append(info)
                except:
                    continue
            
            logger.info(f"Found {len(visible_windows)} visible windows")
            return visible_windows
            
        except Exception as e:
            logger.error(f"List windows error: {e}")
            return []
    
    def close_window(self, title_pattern: str) -> bool:
        """Close window by title"""
        try:
            from pywinauto import Desktop
            
            app = Desktop(backend="uia")
            window = app.window(title_re=f".*{title_pattern}.*")
            
            if window.exists():
                window.close()
                logger.info(f"Closed window: '{title_pattern}'")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Window close error: {e}")
            return False
    
    def minimize_window(self, title_pattern: str) -> bool:
        """Minimize window"""
        try:
            from pywinauto import Desktop
            
            app = Desktop(backend="uia")
            window = app.window(title_re=f".*{title_pattern}.*")
            
            if window.exists():
                window.minimize()
                logger.info(f"Minimized window: '{title_pattern}'")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Window minimize error: {e}")
            return False
    
    def maximize_window(self, title_pattern: str) -> bool:
        """Maximize window"""
        try:
            from pywinauto import Desktop
            
            app = Desktop(backend="uia")
            window = app.window(title_re=f".*{title_pattern}.*")
            
            if window.exists():
                window.maximize()
                logger.info(f"Maximized window: '{title_pattern}'")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Window maximize error: {e}")
            return False


# Global instance
window_manager = WindowManager()
