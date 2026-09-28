"""
Verification Engine
Vision-based and rule-based verification system for workflow steps
"""
import time
from src.utils.optional_import import optional_import

pyautogui = optional_import(
    "pyautogui", hint="Desktop automation needs a graphical session (X11 / Windows / macOS)."
)
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum

from src.autonomous.vision_system import VisionSystem
from src.automation.element_detector import element_detector
from src.automation.window_manager import window_manager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class VerificationType(Enum):
    """Types of verification strategies"""
    VISION_ANALYSIS = "vision_analysis"
    ELEMENT_EXISTS = "element_exists"
    WINDOW_EXISTS = "window_exists"
    PROCESS_RUNNING = "process_running"
    FILE_EXISTS = "file_exists"
    NETWORK_REACHABLE = "network_reachable"
    CUSTOM_FUNCTION = "custom_function"


class VerificationResult(Enum):
    """Verification outcomes"""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    INCONCLUSIVE = "inconclusive"


@dataclass
class VerificationRule:
    """Single verification rule"""
    rule_id: str
    verification_type: VerificationType
    description: str
    parameters: Dict[str, Any]
    expected_result: Any
    timeout: float = 10.0
    required: bool = True
    
    def __str__(self):
        return f"{self.rule_id}: {self.description}"


@dataclass
class VerificationOutcome:
    """Result of verification"""
    result: VerificationResult
    rule_id: str
    actual_result: Any
    expected_result: Any
    confidence: float
    details: Optional[str] = None
    screenshot_path: Optional[str] = None
    
    def is_success(self) -> bool:
        return self.result == VerificationResult.SUCCESS


class VerificationEngine:
    """
    Verifies workflow step completion using multiple strategies
    Integrates vision system, element detection, and custom validators
    """
    
    def __init__(self):
        self.vision = VisionSystem()
        self.element_detector = element_detector
        self.window_manager = window_manager
        self.verification_history: List[VerificationOutcome] = []
        
        logger.info("VerificationEngine initialized")
    
    def verify_step(
        self,
        step_id: str,
        rules: List[VerificationRule],
        take_screenshot: bool = True
    ) -> List[VerificationOutcome]:
        """
        Verify a workflow step using multiple rules
        
        Args:
            step_id: Step identifier
            rules: List of verification rules to apply
            take_screenshot: Whether to capture screenshot for evidence
            
        Returns:
            List of VerificationOutcome results
        """
        logger.info(f"[VERIFY] Starting verification for step '{step_id}' with {len(rules)} rules")
        
        outcomes = []
        screenshot_path = None
        
        # Capture screenshot once for all visual verifications
        if take_screenshot:
            screenshot_path = self._capture_verification_screenshot(step_id)
        
        for rule in rules:
            outcome = self._verify_rule(rule, screenshot_path)
            outcomes.append(outcome)
            
            # Store in history
            self.verification_history.append(outcome)
            
            # Log result
            status_icon = "✓" if outcome.is_success() else "✗"
            logger.info(f"[VERIFY] {status_icon} {rule.rule_id}: {outcome.result.value} (confidence: {outcome.confidence:.2f})")
            
            # If required rule fails, short-circuit
            if rule.required and not outcome.is_success():
                logger.warning(f"[VERIFY] Required rule '{rule.rule_id}' failed - stopping verification")
                break
        
        # Summary
        success_count = sum(1 for o in outcomes if o.is_success())
        logger.info(f"[VERIFY] Step '{step_id}': {success_count}/{len(outcomes)} rules passed")
        
        return outcomes
    
    def _verify_rule(self, rule: VerificationRule, screenshot_path: Optional[str]) -> VerificationOutcome:
        """Verify a single rule"""
        try:
            if rule.verification_type == VerificationType.VISION_ANALYSIS:
                return self._verify_vision(rule, screenshot_path)
            
            elif rule.verification_type == VerificationType.ELEMENT_EXISTS:
                return self._verify_element_exists(rule)
            
            elif rule.verification_type == VerificationType.WINDOW_EXISTS:
                return self._verify_window_exists(rule)
            
            elif rule.verification_type == VerificationType.PROCESS_RUNNING:
                return self._verify_process_running(rule)
            
            elif rule.verification_type == VerificationType.FILE_EXISTS:
                return self._verify_file_exists(rule)
            
            elif rule.verification_type == VerificationType.NETWORK_REACHABLE:
                return self._verify_network_reachable(rule)
            
            elif rule.verification_type == VerificationType.CUSTOM_FUNCTION:
                return self._verify_custom_function(rule)
            
            else:
                return VerificationOutcome(
                    result=VerificationResult.INCONCLUSIVE,
                    rule_id=rule.rule_id,
                    actual_result=None,
                    expected_result=rule.expected_result,
                    confidence=0.0,
                    details=f"Unknown verification type: {rule.verification_type}"
                )
        
        except Exception as e:
            logger.error(f"[VERIFY] Rule '{rule.rule_id}' raised exception: {e}")
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=rule.expected_result,
                confidence=0.0,
                details=f"Error: {str(e)}"
            )
    
    def _verify_vision(self, rule: VerificationRule, screenshot_path: Optional[str]) -> VerificationOutcome:
        """Verify using vision system analysis"""
        import asyncio
        
        try:
            expected_description = rule.parameters.get("expected_state", rule.expected_result)
            
            # Use existing screenshot or capture new one
            if not screenshot_path:
                screenshot_path = self._capture_verification_screenshot(rule.rule_id)
            
            # Run vision analysis
            analysis = asyncio.run(self.vision.analyze_screen(screenshot_path))
            
            if not analysis.get("success"):
                return VerificationOutcome(
                    result=VerificationResult.FAILURE,
                    rule_id=rule.rule_id,
                    actual_result=analysis.get("error"),
                    expected_result=expected_description,
                    confidence=0.0,
                    screenshot_path=screenshot_path,
                    details="Vision analysis failed"
                )
            
            # Check if expected state matches analysis
            analysis_text = str(analysis.get("analysis", {}))
            
            # Simple keyword matching (can be enhanced with LLM-based semantic matching)
            keywords = expected_description.lower().split()
            matches = sum(1 for kw in keywords if kw in analysis_text.lower())
            confidence = matches / len(keywords) if keywords else 0.0
            
            result = VerificationResult.SUCCESS if confidence > 0.7 else VerificationResult.PARTIAL if confidence > 0.3 else VerificationResult.FAILURE
            
            return VerificationOutcome(
                result=result,
                rule_id=rule.rule_id,
                actual_result=analysis_text[:200],
                expected_result=expected_description,
                confidence=confidence,
                screenshot_path=screenshot_path,
                details=f"Vision match: {confidence:.2%}"
            )
        
        except Exception as e:
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=str(e),
                expected_result=rule.expected_result,
                confidence=0.0,
                screenshot_path=screenshot_path
            )
    
    def _verify_element_exists(self, rule: VerificationRule) -> VerificationOutcome:
        """Verify UI element exists"""
        element_id = rule.parameters.get("element_id")
        
        if not element_id:
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=rule.expected_result,
                confidence=0.0,
                details="No element_id provided"
            )
        
        exists = self.element_detector.element_exists(element_id, use_cache=False)
        
        return VerificationOutcome(
            result=VerificationResult.SUCCESS if exists else VerificationResult.FAILURE,
            rule_id=rule.rule_id,
            actual_result=exists,
            expected_result=True,
            confidence=1.0 if exists else 0.0,
            details=f"Element '{element_id}' {'found' if exists else 'not found'}"
        )
    
    def _verify_window_exists(self, rule: VerificationRule) -> VerificationOutcome:
        """Verify window exists"""
        window_title = rule.parameters.get("window_title")
        
        if not window_title:
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=rule.expected_result,
                confidence=0.0,
                details="No window_title provided"
            )
        
        window_info = self.window_manager.find_window_by_title(window_title)
        exists = window_info is not None
        
        return VerificationOutcome(
            result=VerificationResult.SUCCESS if exists else VerificationResult.FAILURE,
            rule_id=rule.rule_id,
            actual_result=window_info.title if window_info else None,
            expected_result=window_title,
            confidence=1.0 if exists else 0.0,
            details=f"Window '{window_title}' {'found' if exists else 'not found'}"
        )
    
    def _verify_process_running(self, rule: VerificationRule) -> VerificationOutcome:
        """Verify process is running"""
        import psutil
        
        process_name = rule.parameters.get("process_name")
        
        if not process_name:
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=rule.expected_result,
                confidence=0.0,
                details="No process_name provided"
            )
        
        try:
            running = any(process_name.lower() in proc.name().lower() for proc in psutil.process_iter(['name']))
            
            return VerificationOutcome(
                result=VerificationResult.SUCCESS if running else VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=running,
                expected_result=True,
                confidence=1.0 if running else 0.0,
                details=f"Process '{process_name}' {'running' if running else 'not running'}"
            )
        except Exception as e:
            return VerificationOutcome(
                result=VerificationResult.INCONCLUSIVE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=True,
                confidence=0.0,
                details=f"Process check error: {str(e)}"
            )
    
    def _verify_file_exists(self, rule: VerificationRule) -> VerificationOutcome:
        """Verify file exists"""
        import os
        
        file_path = rule.parameters.get("file_path")
        
        if not file_path:
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=rule.expected_result,
                confidence=0.0,
                details="No file_path provided"
            )
        
        exists = os.path.exists(file_path)
        
        return VerificationOutcome(
            result=VerificationResult.SUCCESS if exists else VerificationResult.FAILURE,
            rule_id=rule.rule_id,
            actual_result=exists,
            expected_result=True,
            confidence=1.0 if exists else 0.0,
            details=f"File '{file_path}' {'exists' if exists else 'not found'}"
        )
    
    def _verify_network_reachable(self, rule: VerificationRule) -> VerificationOutcome:
        """Verify network endpoint is reachable"""
        import socket
        
        host = rule.parameters.get("host")
        port = rule.parameters.get("port", 80)
        timeout_secs = rule.parameters.get("timeout", 5)
        
        if not host:
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=rule.expected_result,
                confidence=0.0,
                details="No host provided"
            )
        
        try:
            socket.setdefaulttimeout(timeout_secs)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            result_code = sock.connect_ex((host, port))
            sock.close()
            
            reachable = result_code == 0
            
            return VerificationOutcome(
                result=VerificationResult.SUCCESS if reachable else VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=reachable,
                expected_result=True,
                confidence=1.0 if reachable else 0.0,
                details=f"Network {host}:{port} {'reachable' if reachable else 'unreachable'}"
            )
        except Exception as e:
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=False,
                expected_result=True,
                confidence=0.0,
                details=f"Network check error: {str(e)}"
            )
    
    def _verify_custom_function(self, rule: VerificationRule) -> VerificationOutcome:
        """Verify using custom validation function"""
        validator_func = rule.parameters.get("validator")
        
        if not validator_func or not callable(validator_func):
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=rule.expected_result,
                confidence=0.0,
                details="No valid validator function provided"
            )
        
        try:
            actual_result = validator_func()
            matches = actual_result == rule.expected_result
            
            return VerificationOutcome(
                result=VerificationResult.SUCCESS if matches else VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=actual_result,
                expected_result=rule.expected_result,
                confidence=1.0 if matches else 0.0,
                details=f"Custom validator: {actual_result}"
            )
        except Exception as e:
            return VerificationOutcome(
                result=VerificationResult.FAILURE,
                rule_id=rule.rule_id,
                actual_result=None,
                expected_result=rule.expected_result,
                confidence=0.0,
                details=f"Validator error: {str(e)}"
            )
    
    def _capture_verification_screenshot(self, step_id: str) -> str:
        """Capture screenshot for verification evidence"""
        import os
        from pathlib import Path
        
        screenshots_dir = Path("verification_screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        
        timestamp = int(time.time())
        filename = f"{step_id}_{timestamp}.png"
        filepath = screenshots_dir / filename
        
        screenshot = pyautogui.screenshot()
        screenshot.save(str(filepath))
        
        logger.debug(f"[VERIFY] Screenshot captured: {filepath}")
        return str(filepath)
    
    def all_passed(self, outcomes: List[VerificationOutcome], required_only: bool = False) -> bool:
        """Check if all verifications passed"""
        return all(o.is_success() for o in outcomes)
    
    def get_failure_details(self, outcomes: List[VerificationOutcome]) -> List[str]:
        """Get details of failed verifications"""
        failures = [o for o in outcomes if not o.is_success()]
        return [f"{o.rule_id}: {o.details}" for o in failures]


# Pre-defined verification rule templates for common scenarios
class CommonVerifications:
    """Common verification rule templates"""
    
    @staticmethod
    def burpsuite_opened() -> VerificationRule:
        """Verify BurpSuite is opened"""
        return VerificationRule(
            rule_id="burpsuite_window",
            verification_type=VerificationType.WINDOW_EXISTS,
            description="Verify BurpSuite window is open",
            parameters={"window_title": "Burp Suite"},
            expected_result=True,
            required=True
        )
    
    @staticmethod
    def intercept_enabled() -> VerificationRule:
        """Verify BurpSuite intercept is enabled"""
        return VerificationRule(
            rule_id="intercept_on",
            verification_type=VerificationType.ELEMENT_EXISTS,
            description="Verify intercept is ON",
            parameters={"element_id": "Intercept is on"},
            expected_result=True,
            required=True
        )
    
    @staticmethod
    def vision_state(expected_state: str) -> VerificationRule:
        """Verify visual state matches description"""
        return VerificationRule(
            rule_id="vision_state",
            verification_type=VerificationType.VISION_ANALYSIS,
            description=f"Verify visual state: {expected_state}",
            parameters={"expected_state": expected_state},
            expected_result=expected_state,
            required=True,
            timeout=30.0
        )


# Global instance
verification_engine = VerificationEngine()
