import os
import subprocess
import shutil
import asyncio
import psutil
from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
from typing import Dict, Any, List, Optional
from pathlib import Path
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DesktopAutomation:
    """
    Powerful desktop automation for AI to control everything
    Features: File operations, app control, browser automation, system commands
    """
    
    def __init__(self):
        self.safe_mode = True
        pyautogui.FAILSAFE = True
        logger.info("Desktop Automation initialized - AI can control desktop")
    
    async def execute_command(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Route desktop automation commands"""
        
        actions_map = {
            # File Operations
            "create_file": self.create_file,
            "read_file": self.read_file,
            "write_file": self.write_file,
            "delete_file": self.delete_file,
            "move_file": self.move_file,
            "copy_file": self.copy_file,
            "list_files": self.list_files,
            "search_files": self.search_files,
            
            # Folder Operations
            "create_folder": self.create_folder,
            "delete_folder": self.delete_folder,
            "list_folders": self.list_folders,
            
            # App Control
            "launch_app": self.launch_app,
            "close_app": self.close_app,
            "list_running_apps": self.list_running_apps,
            "switch_window": self.switch_window,
            
            # Browser Automation
            "open_url": self.open_url,
            "search_google": self.search_google,
            "open_youtube": self.open_youtube,
            
            # Mouse & Keyboard
            "click": self.click,
            "type_text": self.type_text,
            "press_key": self.press_key,
            "screenshot": self.screenshot,
            
            # System Commands
            "run_command": self.run_command,
            "get_system_info": self.get_system_info,
            "shutdown": self.shutdown,
            "restart": self.restart,
            
            # Clipboard
            "copy_to_clipboard": self.copy_to_clipboard,
            "paste_from_clipboard": self.paste_from_clipboard,
        }
        
        if action not in actions_map:
            raise ValueError(f"Unknown action: {action}")
        
        handler = actions_map[action]
        return await handler(**params)
    
    # ==================== FILE OPERATIONS ====================
    
    async def create_file(self, path: str, content: str = "") -> Dict[str, Any]:
        """Create a new file"""
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding='utf-8')
            return {
                "success": True,
                "path": str(file_path),
                "message": f"File created: {file_path.name}"
            }
        except Exception as e:
            logger.error(f"Create file failed: {e}")
            return {"success": False, "error": str(e)}
    
    async def read_file(self, path: str) -> Dict[str, Any]:
        """Read file contents"""
        try:
            content = Path(path).read_text(encoding='utf-8')
            return {
                "success": True,
                "content": content,
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def write_file(self, path: str, content: str, append: bool = False) -> Dict[str, Any]:
        """Write to file"""
        try:
            file_path = Path(path)
            if append:
                file_path.write_text(file_path.read_text() + content, encoding='utf-8')
            else:
                file_path.write_text(content, encoding='utf-8')
            return {"success": True, "path": str(file_path)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file"""
        try:
            Path(path).unlink()
            return {"success": True, "message": f"Deleted: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def move_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Move file"""
        try:
            shutil.move(source, destination)
            return {"success": True, "from": source, "to": destination}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def copy_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Copy file"""
        try:
            shutil.copy2(source, destination)
            return {"success": True, "from": source, "to": destination}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def list_files(self, path: str = ".", pattern: str = "*") -> Dict[str, Any]:
        """List files in directory"""
        try:
            files = list(Path(path).glob(pattern))
            return {
                "success": True,
                "files": [{"name": f.name, "path": str(f), "size": f.stat().st_size} for f in files if f.is_file()],
                "count": len(files)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def search_files(self, path: str, name: str) -> Dict[str, Any]:
        """Search files by name"""
        try:
            results = list(Path(path).rglob(f"*{name}*"))
            return {
                "success": True,
                "results": [str(r) for r in results],
                "count": len(results)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== FOLDER OPERATIONS ====================
    
    async def create_folder(self, path: str) -> Dict[str, Any]:
        """Create folder"""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def delete_folder(self, path: str) -> Dict[str, Any]:
        """Delete folder"""
        try:
            shutil.rmtree(path)
            return {"success": True, "message": f"Deleted folder: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def list_folders(self, path: str = ".") -> Dict[str, Any]:
        """List folders"""
        try:
            folders = [f for f in Path(path).iterdir() if f.is_dir()]
            return {
                "success": True,
                "folders": [{"name": f.name, "path": str(f)} for f in folders],
                "count": len(folders)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== APP CONTROL ====================
    
    async def launch_app(self, app_name: str, args: List[str] = None) -> Dict[str, Any]:
        """Launch application"""
        try:
            cmd = [app_name] + (args or [])
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return {
                "success": True,
                "app": app_name,
                "pid": process.pid
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def close_app(self, app_name: str) -> Dict[str, Any]:
        """Close application by name"""
        try:
            closed = 0
            for proc in psutil.process_iter(['name']):
                if app_name.lower() in proc.info['name'].lower():
                    proc.kill()
                    closed += 1
            return {"success": True, "closed": closed}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def list_running_apps(self) -> Dict[str, Any]:
        """List running applications"""
        try:
            apps = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
                apps.append({
                    "pid": proc.info['pid'],
                    "name": proc.info['name'],
                    "memory": round(proc.info['memory_percent'], 2)
                })
            return {"success": True, "apps": apps[:50], "total": len(apps)}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def switch_window(self, window_title: str) -> Dict[str, Any]:
        """Switch to window by title"""
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(window_title)
            if windows:
                windows[0].activate()
                return {"success": True, "window": window_title}
            return {"success": False, "error": "Window not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== BROWSER AUTOMATION ====================
    
    async def open_url(self, url: str) -> Dict[str, Any]:
        """Open URL in browser"""
        try:
            import webbrowser
            webbrowser.open(url)
            return {"success": True, "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def search_google(self, query: str) -> Dict[str, Any]:
        """Search on Google"""
        try:
            import webbrowser
            url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(url)
            return {"success": True, "query": query, "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def open_youtube(self, search: str = None) -> Dict[str, Any]:
        """Open YouTube"""
        try:
            import webbrowser
            if search:
                url = f"https://www.youtube.com/results?search_query={search.replace(' ', '+')}"
            else:
                url = "https://www.youtube.com"
            webbrowser.open(url)
            return {"success": True, "url": url}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== MOUSE & KEYBOARD ====================
    
    async def click(self, x: int = None, y: int = None, button: str = "left", clicks: int = 1) -> Dict[str, Any]:
        """Click mouse"""
        try:
            if x and y:
                pyautogui.click(x, y, clicks=clicks, button=button)
            else:
                pyautogui.click(clicks=clicks, button=button)
            return {"success": True, "x": x, "y": y, "button": button}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def type_text(self, text: str, interval: float = 0.05) -> Dict[str, Any]:
        """Type text"""
        try:
            pyautogui.write(text, interval=interval)
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def press_key(self, key: str, presses: int = 1) -> Dict[str, Any]:
        """Press keyboard key"""
        try:
            pyautogui.press(key, presses=presses)
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def screenshot(self, path: str = None) -> Dict[str, Any]:
        """Take screenshot"""
        try:
            if not path:
                path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            screenshot = pyautogui.screenshot()
            screenshot.save(path)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== SYSTEM COMMANDS ====================
    
    async def run_command(self, command: str, shell: bool = True, timeout: int = 30) -> Dict[str, Any]:
        """Run system command"""
        try:
            result = subprocess.run(
                command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        try:
            import platform
            return {
                "success": True,
                "system": platform.system(),
                "platform": platform.platform(),
                "processor": platform.processor(),
                "cpu_count": psutil.cpu_count(),
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
                "memory_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_total_gb": round(psutil.disk_usage('/').total / (1024**3), 2),
                "disk_used_gb": round(psutil.disk_usage('/').used / (1024**3), 2),
                "disk_percent": psutil.disk_usage('/').percent
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def shutdown(self, delay: int = 60) -> Dict[str, Any]:
        """Shutdown system"""
        try:
            if self.safe_mode:
                return {"success": False, "error": "Shutdown disabled in safe mode"}
            import platform
            if platform.system() == "Windows":
                os.system(f"shutdown /s /t {delay}")
            else:
                os.system(f"shutdown -h +{delay//60}")
            return {"success": True, "delay": delay}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def restart(self, delay: int = 60) -> Dict[str, Any]:
        """Restart system"""
        try:
            if self.safe_mode:
                return {"success": False, "error": "Restart disabled in safe mode"}
            import platform
            if platform.system() == "Windows":
                os.system(f"shutdown /r /t {delay}")
            else:
                os.system(f"shutdown -r +{delay//60}")
            return {"success": True, "delay": delay}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # ==================== CLIPBOARD ====================
    
    async def copy_to_clipboard(self, text: str) -> Dict[str, Any]:
        """Copy text to clipboard"""
        try:
            import pyperclip
            pyperclip.copy(text)
            return {"success": True, "text": text[:100]}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def paste_from_clipboard(self) -> Dict[str, Any]:
        """Paste from clipboard"""
        try:
            import pyperclip
            text = pyperclip.paste()
            return {"success": True, "text": text}
        except Exception as e:
            return {"success": False, "error": str(e)}


_instance = None

def get_desktop_automation() -> DesktopAutomation:
    """Get singleton instance"""
    global _instance
    if _instance is None:
        _instance = DesktopAutomation()
    return _instance
