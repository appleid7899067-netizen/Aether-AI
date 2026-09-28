from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
import subprocess
import time
import os
import sys
from typing import Tuple, Optional, List, Dict, Any
from pathlib import Path

if sys.platform == 'win32':
    import win32gui
    import win32con
    import win32process
    import psutil

from src.utils.logger import get_logger

logger = get_logger(__name__)


pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.5


class GUIController:
    def __init__(self, fail_safe: bool = True, pause_duration: float = 0.5):
        pyautogui.FAILSAFE = fail_safe
        pyautogui.PAUSE = pause_duration
        # On a headless server (Docker / Render / CI) pyautogui is unavailable and
        # calling it raises; fall back to a sane default so the module can still be
        # imported and every non-GUI feature keeps working.
        self.gui_available = True
        try:
            self.screen_size = pyautogui.size()
        except Exception as exc:  # noqa: BLE001
            self.gui_available = False
            self.screen_size = (1920, 1080)
            logger.warning(f"GUI automation unavailable ({exc}); using headless defaults")

    def get_screen_size(self) -> Tuple[int, int]:
        return self.screen_size
    
    def get_mouse_position(self) -> Tuple[int, int]:
        return pyautogui.position()
    
    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> bool:
        try:
            pyautogui.moveTo(x, y, duration=duration)
            logger.debug(f"Moved mouse to ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Failed to move mouse: {e}")
            return False
    
    def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: str = 'left',
        clicks: int = 1,
        interval: float = 0.0
    ) -> bool:
        try:
            if x is not None and y is not None:
                pyautogui.click(x, y, clicks=clicks, interval=interval, button=button)
            else:
                pyautogui.click(clicks=clicks, interval=interval, button=button)
            logger.debug(f"Clicked at ({x}, {y}) with {button} button")
            return True
        except Exception as e:
            logger.error(f"Failed to click: {e}")
            return False
    
    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        return self.click(x, y, clicks=2)
    
    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        return self.click(x, y, button='right')
    
    def drag_to(
        self,
        x: int,
        y: int,
        duration: float = 0.5,
        button: str = 'left'
    ) -> bool:
        try:
            pyautogui.dragTo(x, y, duration=duration, button=button)
            logger.debug(f"Dragged to ({x}, {y})")
            return True
        except Exception as e:
            logger.error(f"Failed to drag: {e}")
            return False
    
    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        try:
            if x is not None and y is not None:
                pyautogui.scroll(clicks, x=x, y=y)
            else:
                pyautogui.scroll(clicks)
            logger.debug(f"Scrolled {clicks} clicks")
            return True
        except Exception as e:
            logger.error(f"Failed to scroll: {e}")
            return False
    
    def type_text(self, text: str, interval: float = 0.0) -> bool:
        try:
            pyautogui.write(text, interval=interval)
            logger.debug(f"Typed text: {text[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Failed to type text: {e}")
            return False
    
    def press_key(self, key: str, presses: int = 1, interval: float = 0.0) -> bool:
        try:
            pyautogui.press(key, presses=presses, interval=interval)
            logger.debug(f"Pressed key: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to press key: {e}")
            return False
    
    def hotkey(self, *keys: str) -> bool:
        try:
            pyautogui.hotkey(*keys)
            logger.debug(f"Pressed hotkey: {'+'.join(keys)}")
            return True
        except Exception as e:
            logger.error(f"Failed to press hotkey: {e}")
            return False
    
    def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> Optional[Any]:
        try:
            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()
            logger.debug("Took screenshot")
            return screenshot
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return None
    
    def locate_on_screen(
        self,
        image_path: str,
        confidence: float = 0.9,
        grayscale: bool = True
    ) -> Optional[Tuple[int, int, int, int]]:
        try:
            location = pyautogui.locateOnScreen(
                image_path,
                confidence=confidence,
                grayscale=grayscale
            )
            if location:
                logger.debug(f"Found image at {location}")
            return location
        except Exception as e:
            logger.error(f"Failed to locate image: {e}")
            return None
    
    def click_image(
        self,
        image_path: str,
        confidence: float = 0.9,
        offset: Tuple[int, int] = (0, 0)
    ) -> bool:
        location = self.locate_on_screen(image_path, confidence)
        if location:
            center_x = location[0] + location[2] // 2 + offset[0]
            center_y = location[1] + location[3] // 2 + offset[1]
            return self.click(center_x, center_y)
        return False


class ApplicationLauncher:
    COMMON_APPS = {
        'notepad': 'notepad.exe',
        'calculator': 'calc.exe',
        'explorer': 'explorer.exe',
        'cmd': 'cmd.exe',
        'powershell': 'powershell.exe',
        'browser': 'chrome.exe',
        'chrome': 'chrome.exe',
        'firefox': 'firefox.exe',
        'edge': 'msedge.exe',
        'vscode': 'code.cmd',
        'excel': 'excel.exe',
        'word': 'winword.exe',
        'outlook': 'outlook.exe',
    }
    
    def __init__(self):
        self.running_processes = {}
    
    def launch_application(
        self,
        app_name: str,
        args: Optional[List[str]] = None,
        wait: bool = False
    ) -> Optional[subprocess.Popen]:
        try:
            app_name_lower = app_name.lower()
            
            if app_name_lower in self.COMMON_APPS:
                command = self.COMMON_APPS[app_name_lower]
            elif os.path.exists(app_name):
                command = app_name
            else:
                command = app_name
            
            cmd_list = [command]
            if args:
                cmd_list.extend(args)
            
            process = subprocess.Popen(
                cmd_list,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.running_processes[process.pid] = {
                'process': process,
                'app_name': app_name,
                'start_time': time.time()
            }
            
            logger.info(f"Launched application: {app_name} (PID: {process.pid})")
            
            if wait:
                process.wait()
            
            return process
        except Exception as e:
            logger.error(f"Failed to launch application {app_name}: {e}")
            return None
    
    def close_application(self, pid: int, force: bool = False) -> bool:
        try:
            if sys.platform == 'win32':
                import psutil
                process = psutil.Process(pid)
                
                if force:
                    process.kill()
                else:
                    process.terminate()
                
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    process.kill()
                
                if pid in self.running_processes:
                    del self.running_processes[pid]
                
                logger.info(f"Closed application with PID {pid}")
                return True
            else:
                os.kill(pid, 9 if force else 15)
                return True
        except Exception as e:
            logger.error(f"Failed to close application: {e}")
            return False
    
    def is_application_running(self, app_name: str) -> bool:
        try:
            import psutil
            for proc in psutil.process_iter(['name']):
                if app_name.lower() in proc.info['name'].lower():
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to check if application is running: {e}")
            return False
    
    def get_running_applications(self) -> List[Dict[str, Any]]:
        apps = []
        for pid, info in self.running_processes.items():
            try:
                process = info['process']
                apps.append({
                    'pid': pid,
                    'app_name': info['app_name'],
                    'running': process.poll() is None,
                    'start_time': info['start_time']
                })
            except:
                pass
        return apps


class WindowManager:
    def __init__(self):
        if sys.platform != 'win32':
            logger.warning("WindowManager only supports Windows")
    
    def get_active_window_title(self) -> Optional[str]:
        if sys.platform != 'win32':
            return None
        try:
            hwnd = win32gui.GetForegroundWindow()
            return win32gui.GetWindowText(hwnd)
        except Exception as e:
            logger.error(f"Failed to get active window title: {e}")
            return None
    
    def get_all_windows(self) -> List[Dict[str, Any]]:
        if sys.platform != 'win32':
            return []
        
        windows = []
        
        def callback(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    windows.append({
                        'hwnd': hwnd,
                        'title': title,
                        'rect': win32gui.GetWindowRect(hwnd)
                    })
        
        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.error(f"Failed to enumerate windows: {e}")
        
        return windows
    
    def focus_window(self, title: str) -> bool:
        if sys.platform != 'win32':
            return False
        
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                win32gui.SetForegroundWindow(hwnd)
                logger.info(f"Focused window: {title}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to focus window: {e}")
            return False
    
    def minimize_window(self, title: str) -> bool:
        if sys.platform != 'win32':
            return False
        
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
                logger.info(f"Minimized window: {title}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to minimize window: {e}")
            return False
    
    def maximize_window(self, title: str) -> bool:
        if sys.platform != 'win32':
            return False
        
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
                logger.info(f"Maximized window: {title}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to maximize window: {e}")
            return False
    
    def close_window(self, title: str) -> bool:
        if sys.platform != 'win32':
            return False
        
        try:
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                logger.info(f"Closed window: {title}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to close window: {e}")
            return False
