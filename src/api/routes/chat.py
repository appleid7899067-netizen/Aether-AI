from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import AsyncGenerator, Optional
from pydantic import BaseModel
from src.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ProvidersResponse,
    ProviderInfo,
    CostStats
)
from src.cognitive.llm.model_loader import model_loader
from src.cognitive.llm.providers.base import TaskType
from src.cognitive.llm.inference import conversation_engine, ConversationRequest
from src.utils.logger import get_logger
from src.config import settings

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["chat"])

NO_PROVIDER_MESSAGE = (
    "No AI provider is configured. Add at least one API key in the environment "
    "(GROQ_API_KEY is free and fastest: https://console.groq.com/keys) and restart "
    "the service. Check the current state with GET /api/v1/chat/providers."
)


def _ensure_provider_configured() -> None:
    """Fail with a helpful 503 instead of a raw provider stack trace."""
    try:
        from src.cognitive.llm.model_router import router as model_router

        if not model_router.get_available_providers():
            raise HTTPException(status_code=503, detail=NO_PROVIDER_MESSAGE)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"Provider check skipped: {exc}")


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    _ensure_provider_configured()
    try:
        task_type = TaskType(request.task_type.value)
        
        conversation_history = None
        if request.conversation_history:
            conversation_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.conversation_history
            ]

        if request.stream:
            async def generate_stream():
                async for chunk in model_loader.stream_generate(
                    prompt=request.prompt,
                    task_type=task_type,
                    system_prompt=request.system_prompt,
                    conversation_history=conversation_history,
                    provider=request.provider,
                    model=request.model,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens
                ):
                    yield f"data: {chunk}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )

        response = await model_loader.generate(
            prompt=request.prompt,
            task_type=task_type,
            system_prompt=request.system_prompt,
            conversation_history=conversation_history,
            provider=request.provider,
            model=request.model,
            temperature=request.temperature,
            max_tokens=request.max_tokens
        )

        return ChatResponse(
            content=response.content,
            model=response.model,
            provider=response.provider,
            tokens_used=response.tokens_used,
            cost_usd=response.cost_usd,
            latency_ms=response.latency_ms,
            metadata=response.metadata
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/providers", response_model=ProvidersResponse)
async def get_providers():
    try:
        stats = model_loader.get_provider_stats()
        
        providers = {
            name: ProviderInfo(
                name=name,
                models=info["models"],
                supports_vision=info["supports_vision"],
                supports_function_calling=info["supports_function_calling"]
            )
            for name, info in stats.items()
        }

        return ProvidersResponse(providers=providers)

    except Exception as e:
        logger.error(f"Error fetching providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost-stats", response_model=CostStats)
async def get_cost_stats(hours: int = 24):
    try:
        stats = model_loader.get_cost_stats(hours=hours)
        return CostStats(**stats)

    except Exception as e:
        logger.error(f"Error fetching cost stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/recommended-provider/{task_type}")
async def get_recommended_provider(task_type: str):
    try:
        task = TaskType(task_type)
        provider = model_loader.get_recommended_provider(task)
        return {"task_type": task_type, "recommended_provider": provider}

    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid task type: {task_type}")
    except Exception as e:
        logger.error(f"Error getting recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ConversationRequestBody(BaseModel):
    message: str
    session_id: str = "default"
    use_context: bool = True
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


@router.post("/conversation")
async def conversation(body: ConversationRequestBody):
    _ensure_provider_configured()
    try:
        request = ConversationRequest(
            user_input=body.message,
            session_id=body.session_id,
            stream=body.stream,
            temperature=body.temperature,
            max_tokens=body.max_tokens
        )

        # Helper to trigger TTS
        def trigger_tts(text: str, session_id: str):
            if settings.voice_output_enabled:
                try:
                    from src.pipeline import get_pipeline
                    pipeline = get_pipeline()
                    if not pipeline.tts:
                        pipeline.initialize()
                    
                    pipeline.response_queue.put({
                        "text": text,
                        "session_id": session_id
                    })
                except Exception as e:
                    logger.error(f"Failed to trigger TTS: {e}")

        if body.stream:
            async def generate_stream():
                full_response = ""
                async for chunk in conversation_engine.stream_conversation(request):
                    full_response += chunk
                    yield f"data: {chunk}\n\n"
                
                # Trigger TTS after stream completes
                trigger_tts(full_response, body.session_id)
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                generate_stream(),
                media_type="text/event-stream"
            )

        response = await conversation_engine.process_conversation(request)

        # Trigger TTS for non-streaming response
        trigger_tts(response.content, response.session_id)

        return {
            "content": response.content,
            "intent": response.intent.value,
            "session_id": response.session_id,
            "provider": response.ai_response.provider,
            "model": response.ai_response.model,
            "tokens_used": response.ai_response.tokens_used,
            "cost_usd": response.ai_response.cost_usd,
            "latency_ms": response.ai_response.latency_ms,
            "context_stats": response.context_stats,
            "metadata": response.metadata
        }

    except Exception as e:
        logger.error(f"Conversation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/history/{session_id}")
async def get_conversation_history(session_id: str, max_messages: int = None):
    try:
        context = conversation_engine.get_session_context(session_id)
        if not context:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        history = context.get_history(max_messages=max_messages)
        stats = context.get_context_stats()

        return {
            "session_id": session_id,
            "history": history,
            "stats": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversation/session/{session_id}")
async def clear_session(session_id: str):
    try:
        conversation_engine.clear_session(session_id)
        return {"message": f"Session {session_id} cleared successfully"}

    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation/sessions")
async def list_sessions():
    try:
        sessions = conversation_engine.list_sessions()
        stats = conversation_engine.get_all_sessions_stats()

        return {
            "sessions": sessions,
            "stats": stats
        }

    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))
