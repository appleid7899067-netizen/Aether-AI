"""
Gesture Recognition - Control Aether with Hand Gestures
Webcam-based gesture detection for touchless interaction
"""

import cv2
import numpy as np
from typing import Optional, List, Dict, Tuple, Callable
from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
from collections import deque
import time

try:
    import mediapipe as mp
    MEDIAPIPE_AVAILABLE = True
except ImportError:
    MEDIAPIPE_AVAILABLE = False


class GestureControl:
    """
    Advanced gesture recognition and control
    
    Features:
    - Hand tracking with MediaPipe
    - Gesture recognition (thumbs up, peace sign, etc.)
    - Air mouse control
    - Custom gesture commands
    - Touchless interface
    """
    
    # Gesture definitions
    GESTURES = {
        'thumbs_up': 'Approve/Like',
        'thumbs_down': 'Disapprove/Dislike',
        'peace_sign': 'Screenshot',
        'fist': 'Click',
        'open_palm': 'Stop/Cancel',
        'pointing': 'Select/Point',
        'ok_sign': 'OK/Confirm',
        'swipe_left': 'Previous',
        'swipe_right': 'Next',
        'swipe_up': 'Scroll Up',
        'swipe_down': 'Scroll Down'
    }
    
    def __init__(self):
        """Initialize GestureControl"""
        self.mp_hands = None
        self.mp_drawing = None
        self.hands = None
        
        if MEDIAPIPE_AVAILABLE:
            self.mp_hands = mp.solutions.hands
            self.mp_drawing = mp.solutions.drawing_utils
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5
            )
        
        # Gesture callbacks
        self.gesture_callbacks = {}
        
        # Air mouse state
        self.air_mouse_enabled = False
        self.last_position = None
        self.smoothing_buffer = deque(maxlen=5)
        
        # Gesture history for swipe detection
        self.position_history = deque(maxlen=30)
    
    def detect_gesture(self, frame: np.ndarray) -> Optional[Dict[str, any]]:
        """
        Detect hand gesture in frame
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            Dict with gesture info or None
        """
        if not MEDIAPIPE_AVAILABLE or self.hands is None:
            return self._detect_gesture_opencv(frame)
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process frame
        results = self.hands.process(rgb_frame)
        
        if not results.multi_hand_landmarks:
            return None
        
        # Analyze first detected hand
        hand_landmarks = results.multi_hand_landmarks[0]
        
        # Extract finger states
        finger_states = self._get_finger_states(hand_landmarks)
        
        # Detect gesture from finger states
        gesture = self._classify_gesture(finger_states, hand_landmarks)
        
        # Get hand position
        h, w, _ = frame.shape
        wrist = hand_landmarks.landmark[self.mp_hands.HandLandmark.WRIST]
        position = (int(wrist.x * w), int(wrist.y * h))
        
        # Add to position history
        self.position_history.append(position)
        
        # Detect swipe gestures
        swipe = self._detect_swipe()
        if swipe:
            gesture = swipe
        
        return {
            'gesture': gesture,
            'position': position,
            'finger_states': finger_states,
            'hand_landmarks': hand_landmarks
        }
    
    def _get_finger_states(self, hand_landmarks) -> Dict[str, bool]:
        """
        Determine which fingers are extended
        
        Returns:
            Dict with finger states (True=extended, False=folded)
        """
        landmarks = hand_landmarks.landmark
        
        # Finger tip and PIP indices
        finger_tips = [
            self.mp_hands.HandLandmark.THUMB_TIP,
            self.mp_hands.HandLandmark.INDEX_FINGER_TIP,
            self.mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
            self.mp_hands.HandLandmark.RING_FINGER_TIP,
            self.mp_hands.HandLandmark.PINKY_TIP
        ]
        
        finger_pips = [
            self.mp_hands.HandLandmark.THUMB_IP,
            self.mp_hands.HandLandmark.INDEX_FINGER_PIP,
            self.mp_hands.HandLandmark.MIDDLE_FINGER_PIP,
            self.mp_hands.HandLandmark.RING_FINGER_PIP,
            self.mp_hands.HandLandmark.PINKY_PIP
        ]
        
        states = {}
        
        for i, (tip, pip) in enumerate(zip(finger_tips, finger_pips)):
            if i == 0:  # Thumb (check x-axis)
                states['thumb'] = landmarks[tip].x < landmarks[pip].x
            else:  # Other fingers (check y-axis)
                finger_names = ['index', 'middle', 'ring', 'pinky']
                states[finger_names[i-1]] = landmarks[tip].y < landmarks[pip].y
        
        return states
    
    def _classify_gesture(self, finger_states: Dict[str, bool], hand_landmarks) -> str:
        """
        Classify gesture based on finger states
        
        Returns:
            Gesture name
        """
        # Count extended fingers
        extended_count = sum(finger_states.values())
        
        # Thumbs up: only thumb extended
        if finger_states['thumb'] and extended_count == 1:
            return 'thumbs_up'
        
        # Peace sign: index and middle fingers extended
        if (finger_states['index'] and finger_states['middle'] and 
            not finger_states['ring'] and not finger_states['pinky']):
            return 'peace_sign'
        
        # Fist: no fingers extended
        if extended_count == 0:
            return 'fist'
        
        # Open palm: all fingers extended
        if extended_count == 5:
            return 'open_palm'
        
        # Pointing: only index finger extended
        if finger_states['index'] and extended_count == 1:
            return 'pointing'
        
        # OK sign: thumb and index forming circle
        thumb_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.THUMB_TIP]
        index_tip = hand_landmarks.landmark[self.mp_hands.HandLandmark.INDEX_FINGER_TIP]
        
        distance = np.sqrt((thumb_tip.x - index_tip.x)**2 + (thumb_tip.y - index_tip.y)**2)
        
        if distance < 0.05 and extended_count >= 3:
            return 'ok_sign'
        
        return 'unknown'
    
    def _detect_swipe(self) -> Optional[str]:
        """
        Detect swipe gestures from position history
        
        Returns:
            Swipe direction or None
        """
        if len(self.position_history) < 20:
            return None
        
        # Get start and end positions
        start_pos = self.position_history[0]
        end_pos = self.position_history[-1]
        
        dx = end_pos[0] - start_pos[0]
        dy = end_pos[1] - start_pos[1]
        
        # Minimum swipe distance
        min_distance = 100
        
        # Horizontal swipe
        if abs(dx) > min_distance and abs(dx) > abs(dy) * 2:
            if dx > 0:
                return 'swipe_right'
            else:
                return 'swipe_left'
        
        # Vertical swipe
        if abs(dy) > min_distance and abs(dy) > abs(dx) * 2:
            if dy > 0:
                return 'swipe_down'
            else:
                return 'swipe_up'
        
        return None
    
    def _detect_gesture_opencv(self, frame: np.ndarray) -> Optional[Dict[str, any]]:
        """
        Fallback gesture detection using OpenCV
        Detects hand presence and basic shapes
        """
        # Convert to HSV for skin detection
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        
        # Skin color range
        lower_skin = np.array([0, 20, 70])
        upper_skin = np.array([20, 255, 255])
        
        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return None
        
        # Get largest contour (assumed to be hand)
        hand_contour = max(contours, key=cv2.contourArea)
        
        # Get bounding rect
        x, y, w, h = cv2.boundingRect(hand_contour)
        
        return {
            'gesture': 'hand_detected',
            'position': (x + w//2, y + h//2),
            'finger_states': {},
            'hand_landmarks': None
        }
    
    def enable_air_mouse(self, enabled: bool = True):
        """Enable/disable air mouse control"""
        self.air_mouse_enabled = enabled
        if not enabled:
            self.last_position = None
            self.smoothing_buffer.clear()
    
    def update_air_mouse(self, position: Tuple[int, int], screen_size: Tuple[int, int]):
        """
        Update cursor position based on hand position
        
        Args:
            position: Hand position in frame (x, y)
            screen_size: Screen dimensions (width, height)
        """
        if not self.air_mouse_enabled:
            return
        
        # Add to smoothing buffer
        self.smoothing_buffer.append(position)
        
        # Calculate smoothed position
        avg_x = int(np.mean([p[0] for p in self.smoothing_buffer]))
        avg_y = int(np.mean([p[1] for p in self.smoothing_buffer]))
        
        # Map to screen coordinates (invert and scale)
        screen_x = int(avg_x / 640 * screen_size[0])
        screen_y = int(avg_y / 480 * screen_size[1])
        
        # Move mouse
        pyautogui.moveTo(screen_x, screen_y, duration=0.1)
        
        self.last_position = (screen_x, screen_y)
    
    def register_gesture_callback(self, gesture: str, callback: Callable):
        """
        Register callback for specific gesture
        
        Args:
            gesture: Gesture name
            callback: Function to call when gesture detected
        """
        self.gesture_callbacks[gesture] = callback
    
    def process_gesture(self, gesture_result: Dict[str, any]):
        """
        Process detected gesture and trigger callbacks
        
        Args:
            gesture_result: Result from detect_gesture()
        """
        if gesture_result is None:
            return
        
        gesture = gesture_result['gesture']
        
        # Trigger callback if registered
        if gesture in self.gesture_callbacks:
            self.gesture_callbacks[gesture](gesture_result)
    
    def draw_hand_landmarks(self, frame: np.ndarray, gesture_result: Dict[str, any]) -> np.ndarray:
        """
        Draw hand landmarks on frame
        
        Args:
            frame: Input frame
            gesture_result: Result from detect_gesture()
            
        Returns:
            Annotated frame
        """
        if gesture_result is None or gesture_result['hand_landmarks'] is None:
            return frame
        
        if not MEDIAPIPE_AVAILABLE:
            return frame
        
        annotated = frame.copy()
        
        # Draw hand landmarks
        self.mp_drawing.draw_landmarks(
            annotated,
            gesture_result['hand_landmarks'],
            self.mp_hands.HAND_CONNECTIONS
        )
        
        # Draw gesture label
        gesture = gesture_result['gesture']
        cv2.putText(
            annotated,
            f"Gesture: {gesture}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )
        
        return annotated
    
    def run_interactive(self, camera_index: int = 0):
        """
        Run interactive gesture control with webcam
        
        Args:
            camera_index: Webcam index (default: 0)
        """
        cap = cv2.VideoCapture(camera_index)
        
        print("Gesture Control Started")
        print("Press 'a' to toggle air mouse")
        print("Press 'q' to quit")
        print(f"\nAvailable gestures: {', '.join(self.GESTURES.keys())}")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Flip for mirror effect
            frame = cv2.flip(frame, 1)
            
            # Detect gesture
            result = self.detect_gesture(frame)
            
            if result:
                # Process gesture
                self.process_gesture(result)
                
                # Update air mouse
                if self.air_mouse_enabled:
                    screen_size = pyautogui.size()
                    self.update_air_mouse(result['position'], screen_size)
                
                # Draw annotations
                frame = self.draw_hand_landmarks(frame, result)
            
            # Show air mouse status
            status = "Air Mouse: ON" if self.air_mouse_enabled else "Air Mouse: OFF"
            cv2.putText(frame, status, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
            
            cv2.imshow('Gesture Control', frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('a'):
                self.enable_air_mouse(not self.air_mouse_enabled)
        
        cap.release()
        cv2.destroyAllWindows()


# Example usage
if __name__ == "__main__":
    gesture_control = GestureControl()
    
    # Register gesture callbacks
    def on_thumbs_up(result):
        print("👍 Thumbs up detected!")
    
    def on_peace_sign(result):
        print("✌️ Peace sign - Taking screenshot!")
        # Take screenshot
        from datetime import datetime
        filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        pyautogui.screenshot(filename)
        print(f"Saved: {filename}")
    
    def on_fist(result):
        print("👊 Fist - Click!")
        pyautogui.click()
    
    gesture_control.register_gesture_callback('thumbs_up', on_thumbs_up)
    gesture_control.register_gesture_callback('peace_sign', on_peace_sign)
    gesture_control.register_gesture_callback('fist', on_fist)
    
    # Run interactive mode
    gesture_control.run_interactive()
