import asyncio
from typing import Optional, Tuple
from src.utils.optional_import import optional_import

_pynput = optional_import(
    "pynput", hint="Keyboard and mouse control needs a graphical session (X11 / Windows / macOS)."
)
mouse = _pynput.mouse  # resolved lazily so a headless server can still import this module
keyboard = _pynput.keyboard

from src.control.models import MouseButton, ActionType, ControlAction, ActionResult
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MouseKeyboardController:
    
    def __init__(self):
        # pynput needs a graphical session; when it is missing (headless server)
        # the controllers stay ``None`` and every action returns a clear error
        # instead of crashing on import.
        self.available = True
        try:
            self.mouse_controller = mouse.Controller()
            self.keyboard_controller = keyboard.Controller()
        except Exception as exc:  # noqa: BLE001
            self.available = False
            self.mouse_controller = None
            self.keyboard_controller = None
            logger.warning(f"Keyboard/mouse control unavailable ({exc})")
        self.screen_bounds = self._get_screen_bounds()
    
    def _get_screen_bounds(self) -> Tuple[int, int]:
        try:
            import tkinter as tk
            root = tk.Tk()
            width = root.winfo_screenwidth()
            height = root.winfo_screenheight()
            root.destroy()
            return (width, height)
        except Exception as e:
            logger.warning(f"Could not get screen bounds: {e}")
            return (1920, 1080)
    
    def _validate_position(self, x: int, y: int) -> bool:
        max_x, max_y = self.screen_bounds
        if x < 0 or x > max_x or y < 0 or y > max_y:
            logger.warning(f"Position ({x}, {y}) out of screen bounds")
            return False
        return True
    
    async def move_mouse(self, x: int, y: int) -> ActionResult:
        if not self._validate_position(x, y):
            return ActionResult(
                success=False,
                action_type=ActionType.MOUSE_MOVE,
                error=f"Position ({x}, {y}) out of screen bounds ({self.screen_bounds})"
            )
        
        try:
            await asyncio.to_thread(lambda: setattr(self.mouse_controller, 'position', (x, y)))
            logger.info(f"Mouse moved to ({x}, {y})")
            return ActionResult(
                success=True,
                action_type=ActionType.MOUSE_MOVE,
                message=f"Mouse moved to ({x}, {y})",
                executed=True
            )
        except Exception as e:
            logger.error(f"Failed to move mouse: {e}")
            return ActionResult(
                success=False,
                action_type=ActionType.MOUSE_MOVE,
                error=str(e)
            )
    
    async def click_mouse(self, button: MouseButton = MouseButton.LEFT, x: Optional[int] = None, y: Optional[int] = None) -> ActionResult:
        try:
            if x is not None and y is not None:
                if not self._validate_position(x, y):
                    return ActionResult(
                        success=False,
                        action_type=ActionType.MOUSE_CLICK,
                        error=f"Position ({x}, {y}) out of screen bounds"
                    )
                self.mouse_controller.position = (x, y)
            
            mouse_button = mouse.Button.left
            if button == MouseButton.RIGHT:
                mouse_button = mouse.Button.right
            elif button == MouseButton.MIDDLE:
                mouse_button = mouse.Button.middle
            
            await asyncio.to_thread(self.mouse_controller.click, mouse_button)
            
            position = self.mouse_controller.position
            logger.info(f"Mouse {button.value} clicked at {position}")
            return ActionResult(
                success=True,
                action_type=ActionType.MOUSE_CLICK,
                message=f"Mouse {button.value} clicked at {position}",
                executed=True
            )
        except Exception as e:
            logger.error(f"Failed to click mouse: {e}")
            return ActionResult(
                success=False,
                action_type=ActionType.MOUSE_CLICK,
                error=str(e)
            )
    
    async def type_text(self, text: str, delay: float = 0.0) -> ActionResult:
        if not text:
            return ActionResult(
                success=False,
                action_type=ActionType.KEYBOARD_TYPE,
                error="Empty text provided"
            )
        
        if len(text) > 1000:
            return ActionResult(
                success=False,
                action_type=ActionType.KEYBOARD_TYPE,
                error="Text too long (max 1000 characters)"
            )
        
        try:
            for char in text:
                await asyncio.to_thread(self.keyboard_controller.press, char)
                await asyncio.to_thread(self.keyboard_controller.release, char)
                if delay > 0:
                    await asyncio.sleep(delay)
            
            logger.info(f"Typed {len(text)} characters")
            return ActionResult(
                success=True,
                action_type=ActionType.KEYBOARD_TYPE,
                message=f"Typed {len(text)} characters",
                executed=True
            )
        except Exception as e:
            logger.error(f"Failed to type text: {e}")
            return ActionResult(
                success=False,
                action_type=ActionType.KEYBOARD_TYPE,
                error=str(e)
            )
    
    async def press_key(self, key_name: str) -> ActionResult:
        if not key_name:
            return ActionResult(
                success=False,
                action_type=ActionType.KEYBOARD_PRESS,
                error="Empty key name provided"
            )
        
        try:
            key_obj = self._get_key_object(key_name)
            
            await asyncio.to_thread(self.keyboard_controller.press, key_obj)
            await asyncio.to_thread(self.keyboard_controller.release, key_obj)
            
            logger.info(f"Pressed key: {key_name}")
            return ActionResult(
                success=True,
                action_type=ActionType.KEYBOARD_PRESS,
                message=f"Pressed key: {key_name}",
                executed=True
            )
        except Exception as e:
            logger.error(f"Failed to press key {key_name}: {e}")
            return ActionResult(
                success=False,
                action_type=ActionType.KEYBOARD_PRESS,
                error=str(e)
            )
    
    def _get_key_object(self, key_name: str):
        key_name_lower = key_name.lower()
        
        key_map = {
            'enter': keyboard.Key.enter,
            'return': keyboard.Key.enter,
            'tab': keyboard.Key.tab,
            'space': keyboard.Key.space,
            'backspace': keyboard.Key.backspace,
            'delete': keyboard.Key.delete,
            'esc': keyboard.Key.esc,
            'escape': keyboard.Key.esc,
            'shift': keyboard.Key.shift,
            'ctrl': keyboard.Key.ctrl,
            'control': keyboard.Key.ctrl,
            'alt': keyboard.Key.alt,
            'cmd': keyboard.Key.cmd,
            'command': keyboard.Key.cmd,
            'win': keyboard.Key.cmd,
            'windows': keyboard.Key.cmd,
            'up': keyboard.Key.up,
            'down': keyboard.Key.down,
            'left': keyboard.Key.left,
            'right': keyboard.Key.right,
            'home': keyboard.Key.home,
            'end': keyboard.Key.end,
            'pageup': keyboard.Key.page_up,
            'pagedown': keyboard.Key.page_down,
            'f1': keyboard.Key.f1,
            'f2': keyboard.Key.f2,
            'f3': keyboard.Key.f3,
            'f4': keyboard.Key.f4,
            'f5': keyboard.Key.f5,
            'f6': keyboard.Key.f6,
            'f7': keyboard.Key.f7,
            'f8': keyboard.Key.f8,
            'f9': keyboard.Key.f9,
            'f10': keyboard.Key.f10,
            'f11': keyboard.Key.f11,
            'f12': keyboard.Key.f12,
        }
        
        if key_name_lower in key_map:
            return key_map[key_name_lower]
        
        if len(key_name) == 1:
            return key_name
        
        raise ValueError(f"Unknown key: {key_name}")
    
    def get_mouse_position(self) -> Tuple[int, int]:
        return self.mouse_controller.position
