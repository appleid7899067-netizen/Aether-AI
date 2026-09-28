from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
import time
import subprocess
import os
from typing import Optional

# Fail-safe: Move mouse to top-left corner to abort
pyautogui.FAILSAFE = True

class DesktopAutomation:
    """Handles desktop automation tasks (Vy-like features)"""
    
    @staticmethod
    def open_app(app_name: str):
        """Open an application by name with delay for focus"""
        try:
            # Try direct execution for common apps
            common_apps = {
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "calc": "calc.exe",
                "cmd": "cmd.exe",
                "terminal": "wt.exe",
                "explorer": "explorer.exe",
                "chrome": "chrome.exe",
                "paint": "mspaint.exe"
            }
            
            if app_name.lower() in common_apps:
                subprocess.Popen(common_apps[app_name.lower()])
                time.sleep(2.0) # Wait for app to open
                return f"Opening {app_name}"
            
            # Use Windows Start Menu search for others
            pyautogui.press('win')
            time.sleep(0.5)
            pyautogui.write(app_name)
            time.sleep(1.0)
            pyautogui.press('enter')
            time.sleep(2.0) # Wait for app to launch
            return f"Launching {app_name} via Start Menu"
        except Exception as e:
            return f"Failed to open {app_name}: {str(e)}"
    
    @staticmethod
    def type_text(text: str, interval: float = 0.05):
        """Type text like a human"""
        pyautogui.write(text, interval=interval)
        return "Typing completed"
    
    @staticmethod
    def press_key(key: str):
        """Press a specific key"""
        try:
            pyautogui.press(key)
            return f"Pressed {key}"
        except:
            return f"Invalid key: {key}"
    
    @staticmethod
    def move_mouse(x: int, y: int):
        """Move mouse to specific coordinates"""
        pyautogui.moveTo(x, y)
        return f"Moved mouse to ({x}, {y})"
    
    @staticmethod
    def click_at(x: int, y: int):
        """Click at specific coordinates"""
        pyautogui.click(x, y)
        return f"Clicked at ({x}, {y})"
    
    @staticmethod
    def screenshot(filename: str = "screenshot.png"):
        """Take a screenshot"""
        try:
            img = pyautogui.screenshot()
            img.save(filename)
            return f"Screenshot saved to {filename}"
        except Exception as e:
            return f"Screenshot failed: {str(e)}"

    @staticmethod
    def click_text(text: str):
        """Click a UI element by text using pywinauto (installed)"""
        try:
            from pywinauto import Desktop
            from pywinauto.findwindows import ElementNotFoundError
            
            app = Desktop(backend="uia")
            window = app.window(active_only=True)
            
            if not window.exists():
                return "Error: No active window found"
            
            # Try multiple strategies to find the element
            strategies = [
                # Strategy 1: Button with exact title
                lambda: window.child_window(title=text, control_type="Button"),
                # Strategy 2: Any control with exact title
                lambda: window.child_window(title=text),
                # Strategy 3: Button containing text
                lambda: window.child_window(title_re=f".*{text}.*", control_type="Button"),
                # Strategy 4: Any control containing text
                lambda: window.child_window(title_re=f".*{text}.*"),
                # Strategy 5: Look for accessible name
                lambda: window.child_window(best_match=text)
            ]
            
            for i, strategy in enumerate(strategies):
                try:
                    element = strategy()
                    if element.exists(timeout=1):
                        element.click_input()
                        return f"Clicked '{text}' (strategy {i+1})"
                except:
                    continue
            
            # If all strategies fail, return detailed error
            return f"Element '{text}' not found. Active window: {window.window_text()}"
            
        except ImportError as e:
            return f"Error: pywinauto import failed - {e}. Module should be installed."
        except Exception as e:
            return f"Click failed: {str(e)}"
    
    @staticmethod
    def get_window_info():
        """Get information about the active window"""
        try:
            from pywinauto import Desktop
            app = Desktop(backend="uia")
            window = app.window(active_only=True)
            
            info = {
                "title": window.window_text(),
                "class": window.class_name(),
                "visible": window.is_visible(),
                "enabled": window.is_enabled()
            }
            return info
        except Exception as e:
            return {"error": str(e)}
