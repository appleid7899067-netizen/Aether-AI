from typing import Optional, List, Dict, Any
from enum import Enum
import os
from .providers.base import BaseAIProvider, TaskType, AIResponse
from .providers import (
    OpenAIProvider,
    AnthropicProvider,
    GoogleProvider,
    GroqProvider,
    FireworksProvider,
    OpenRouterProvider
)
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ModelRouter:
    def __init__(self, skip_provider_init: bool = False):
        self.providers: Dict[str, BaseAIProvider] = {}
        if not skip_provider_init:
            self._initialize_providers()
        
        self.task_routing = {
            TaskType.CONVERSATION: self._get_provider_by_name(settings.router_conversation),
            TaskType.ANALYSIS: self._get_provider_by_name(settings.router_analysis),
            TaskType.CODE: self._get_provider_by_name(settings.router_code),
            TaskType.CREATIVE: self._get_provider_by_name(settings.router_creative),
            TaskType.FAST: self._get_provider_by_name(settings.router_fast),
            TaskType.VISION: self._get_provider_by_name(settings.router_vision),
            TaskType.REASONING: self._get_provider_by_name(settings.router_reasoning),
        }

    def _initialize_providers(self):
        # Priority order: Fireworks → Groq → Anthropic → Google → OpenRouter → OpenAI (last)
        
        if settings.fireworks_api_key:
            try:
                self.providers["fireworks"] = FireworksProvider(settings.fireworks_api_key)
                logger.info("Fireworks provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Fireworks: {e}")

        if settings.groq_api_key:
            try:
                self.providers["groq"] = GroqProvider(settings.groq_api_key)
                logger.info("Groq provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq: {e}")

        if settings.anthropic_api_key:
            try:
                self.providers["anthropic"] = AnthropicProvider(settings.anthropic_api_key)
                self.providers["claude"] = self.providers["anthropic"]
                logger.info("Anthropic provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Anthropic: {e}")

        if settings.google_api_key:
            try:
                self.providers["google"] = GoogleProvider(settings.google_api_key)
                self.providers["gemini"] = self.providers["google"]
                logger.info("Google provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Google: {e}")

        if settings.openrouter_api_key:
            try:
                self.providers["openrouter"] = OpenRouterProvider(settings.openrouter_api_key)
                logger.info("OpenRouter provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenRouter: {e}")

        if settings.openai_api_key:
            try:
                self.providers["openai"] = OpenAIProvider(settings.openai_api_key)
                self.providers["gpt-4"] = self.providers["openai"]
                self.providers["gpt-4-vision"] = self.providers["openai"]
                logger.info("OpenAI provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI: {e}")

        if not self.providers and not os.getenv("TESTING"):
            logger.warning("No AI providers configured. Please add API keys to .env file")
            logger.warning("API will start but AI endpoints will not function without provider keys")

    def _get_provider_by_name(self, name: str) -> Optional[BaseAIProvider]:
        return self.providers.get(name)

    def get_provider_for_task(self, task_type: TaskType) -> BaseAIProvider:
        provider = self.task_routing.get(task_type)
        if provider:
            return provider
        
        fallback = self._get_provider_by_name(settings.fallback_provider)
        if fallback:
            logger.info(f"Using fallback provider for task type {task_type}")
            return fallback
        
        logger.info(f"Using first available provider for task type {task_type}")
        return list(self.providers.values())[0]

    async def route_request(
        self,
        messages: List[Dict[str, str]],
        task_type: TaskType = TaskType.CONVERSATION,
        provider_override: Optional[str] = None,
        model_override: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stream: bool = False,
        **kwargs
    ) -> AIResponse:
        if provider_override:
            provider = self._get_provider_by_name(provider_override)
            if not provider:
                logger.warning(f"Provider {provider_override} not found, using router")
                provider = self.get_provider_for_task(task_type)
        else:
            provider = self.get_provider_for_task(task_type)

        logger.info(f"Routing {task_type.value} task to {provider.get_provider_name()}")

        if stream:
            return provider.stream_generate(
                messages=messages,
                model=model_override,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        else:
            return await provider.generate(
                messages=messages,
                model=model_override,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )

    async def route_with_fallback(
        self,
        messages: List[Dict[str, str]],
        task_type: TaskType = TaskType.CONVERSATION,
        max_retries: int = 2,
        **kwargs
    ) -> AIResponse:
        """
        Enhanced fallback with self-healing mechanism
        
        Fallback chain:
        1. Primary provider (OpenAI/Groq/etc)
        2. Fallback provider
        3. Other configured providers
        
        Self-healing: Auto-recovers when primary API returns
        """
        providers_to_try = [
            self.get_provider_for_task(task_type),
            self._get_provider_by_name(settings.fallback_provider),
        ] + [p for p in self.providers.values() if p not in [
            self.get_provider_for_task(task_type),
            self._get_provider_by_name(settings.fallback_provider)
        ]]

        last_error = None
        for provider in providers_to_try[:max_retries + 1]:
            if provider is None:
                continue
            
            try:
                logger.info(f"Attempting request with {provider.get_provider_name()}")
                response = await provider.generate(messages=messages, **kwargs)
                return response
            except Exception as e:
                error_str = str(e).lower()
                
                if "429" in error_str or "rate limit" in error_str:
                    logger.warning(f"Rate limit hit on {provider.get_provider_name()}")
                elif "timeout" in error_str:
                    logger.warning(f"Timeout on {provider.get_provider_name()}")
                elif "500" in error_str or "503" in error_str:
                    logger.warning(f"Server error on {provider.get_provider_name()}")
                
                logger.error(f"Provider {provider.get_provider_name()} failed: {e}")
                last_error = e
                continue

        raise Exception(f"All providers failed. Last error: {last_error}")
    

    def get_available_providers(self) -> List[str]:
        return list(self.providers.keys())

    def get_provider_stats(self) -> Dict[str, Any]:
        stats = {}
        for name, provider in self.providers.items():
            stats[name] = {
                "models": provider.get_available_models(),
                "supports_vision": provider.supports_vision(),
                "supports_function_calling": provider.supports_function_calling(),
            }
        return stats


router = ModelRouter()


# Module level singleton accessor used by the security / bug-bounty modules.
_ai_router = router


async def get_ai_router() -> ModelRouter:
    """Return the shared :class:`ModelRouter` instance."""
    return _ai_router


def get_model_router() -> ModelRouter:
    """Synchronous accessor for the shared :class:`ModelRouter` instance."""
    return _ai_router
