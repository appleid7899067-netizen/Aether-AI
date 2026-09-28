from typing import List, Dict, Optional, Any
from collections import deque
from datetime import datetime, timezone
import tiktoken
from src.config import settings
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager:
    def __init__(self, session_id: str = "default", max_messages: int = None, max_tokens: int = 8000, load_from_db: bool = True, db_path: str = None):
        self.session_id = session_id
        self.max_messages = max_messages or settings.max_context_messages
        self.max_tokens = max_tokens
        self.conversation_history: deque = deque(maxlen=self.max_messages)
        self.token_count = 0
        self.encoder = self._load_encoder()
        
        # Initialize Long-Term Memory
        from src.cognitive.memory.conversation_history import ConversationHistory
        self.history_db = ConversationHistory(db_path=db_path) if db_path else ConversationHistory()
        
        # Load recent context from DB
        if load_from_db:
            try:
                recent_msgs = self.history_db.get_recent_context(session_id=self.session_id, max_messages=self.max_messages)
                for msg in recent_msgs:
                    self.conversation_history.append({
                        "role": msg["role"],
                        "content": msg["content"],
                        "timestamp": datetime.now(timezone.utc).isoformat(), # Approximate for loaded msgs
                        "token_count": self.count_tokens(msg["content"])
                    })
                self._update_token_count()
                logger.info(f"Loaded {len(recent_msgs)} messages from long-term memory for session {self.session_id}")
            except Exception as e:
                logger.error(f"Failed to load memory for session {self.session_id}: {e}")
        else:
            logger.info("Skipping DB load for test mode")

        logger.info(f"Context Manager initialized: session={self.session_id}, max_messages={self.max_messages}, max_tokens={self.max_tokens}")

    @staticmethod
    def _load_encoder():
        """Load the cl100k_base tokenizer, tolerating an offline/sandboxed host.

        ``tiktoken`` downloads its BPE file the first time it is used; when that
        download is blocked (corporate proxy, air-gapped container, Render build
        without egress) we fall back to a cheap character based estimate so that
        chat keeps working.  ``None`` means "use the fallback".
        """
        try:
            return tiktoken.get_encoding("cl100k_base")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"tiktoken encoder unavailable ({exc}); using character estimate")
            return None

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None):
        if role not in ["user", "assistant", "system"]:
            raise ValueError(f"Invalid role: {role}. Must be 'user', 'assistant', or 'system'")

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {}
        }
        
        # Persist to Long-Term Memory
        try:
            self.history_db.add_message(
                session_id=self.session_id,
                role=role,
                content=content,
                metadata=metadata
            )
        except Exception as e:
            logger.error(f"Failed to persist message: {e}")

        message_tokens = self.count_tokens(content)
        message["token_count"] = message_tokens

        self.conversation_history.append(message)
        self._update_token_count()

        if self.token_count > self.max_tokens:
            logger.warning(f"Token count ({self.token_count}) exceeds max ({self.max_tokens}), truncating...")
            self._truncate_to_fit()

        logger.debug(f"Added {role} message: {message_tokens} tokens, total={self.token_count}")

    def get_history(
        self,
        max_messages: Optional[int] = None,
        include_metadata: bool = False
    ) -> List[Dict[str, str]]:
        messages = list(self.conversation_history)
        
        if max_messages:
            messages = messages[-max_messages:]

        if not include_metadata:
            messages = [
                {"role": msg["role"], "content": msg["content"]}
                for msg in messages
            ]

        return messages

    def get_formatted_history(self, max_messages: Optional[int] = None) -> str:
        messages = self.get_history(max_messages, include_metadata=True)
        formatted = []
        
        for msg in messages:
            timestamp = msg.get("timestamp", "")
            role = msg["role"].upper()
            content = msg["content"]
            formatted.append(f"[{timestamp}] {role}: {content}")
        
        return "\n".join(formatted)

    def count_tokens(self, text: str) -> int:
        try:
            if self.encoder is None:
                return max(1, len(text) // 4)  # ~4 characters per token
            return len(self.encoder.encode(text))
        except Exception as e:
            logger.error(f"Error counting tokens: {e}")
            return len(text.split()) * 2

    def get_total_tokens(self) -> int:
        return self.token_count

    def _update_token_count(self):
        total = sum(msg.get("token_count", 0) for msg in self.conversation_history)
        self.token_count = total

    def _truncate_to_fit(self):
        while self.token_count > self.max_tokens and len(self.conversation_history) > 1:
            removed = self.conversation_history.popleft()
            logger.debug(f"Removed message to fit token limit: {removed.get('token_count', 0)} tokens")
            self._update_token_count()

    def summarize_context(self) -> str:
        if len(self.conversation_history) == 0:
            return "No conversation history"

        messages = list(self.conversation_history)
        user_messages = [msg for msg in messages if msg["role"] == "user"]
        assistant_messages = [msg for msg in messages if msg["role"] == "assistant"]

        summary = f"""**Conversation Summary**
Total Messages: {len(messages)}
User Messages: {len(user_messages)}
Assistant Messages: {len(assistant_messages)}
Total Tokens: {self.token_count}

**Recent Topics:**
"""
        recent_topics = []
        for msg in messages[-5:]:
            if msg["role"] == "user":
                preview = msg["content"][:100] + "..." if len(msg["content"]) > 100 else msg["content"]
                recent_topics.append(f"- {preview}")

        summary += "\n".join(recent_topics)
        return summary

    def get_compressed_context(self, target_tokens: int = 2000) -> List[Dict[str, str]]:
        messages = list(self.conversation_history)
        
        system_messages = [msg for msg in messages if msg["role"] == "system"]
        other_messages = [msg for msg in messages if msg["role"] != "system"]

        compressed = system_messages.copy()
        current_tokens = sum(msg.get("token_count", 0) for msg in compressed)

        for msg in reversed(other_messages):
            msg_tokens = msg.get("token_count", 0)
            if current_tokens + msg_tokens <= target_tokens:
                compressed.insert(len(system_messages), msg)
                current_tokens += msg_tokens
            else:
                break

        logger.info(f"Compressed context: {len(compressed)} messages, {current_tokens} tokens")
        return [{"role": msg["role"], "content": msg["content"]} for msg in compressed]

    def clear_history(self):
        self.conversation_history.clear()
        self.token_count = 0
        logger.info("Conversation history cleared")

    def get_last_n_messages(self, n: int) -> List[Dict[str, str]]:
        return self.get_history(max_messages=n)

    def get_messages_by_role(self, role: str) -> List[Dict[str, str]]:
        return [
            {"role": msg["role"], "content": msg["content"]}
            for msg in self.conversation_history
            if msg["role"] == role
        ]

    def get_context_stats(self) -> Dict[str, Any]:
        messages = list(self.conversation_history)
        return {
            "total_messages": len(messages),
            "user_messages": len([m for m in messages if m["role"] == "user"]),
            "assistant_messages": len([m for m in messages if m["role"] == "assistant"]),
            "system_messages": len([m for m in messages if m["role"] == "system"]),
            "total_tokens": self.token_count,
            "max_tokens": self.max_tokens,
            "token_usage_percentage": (self.token_count / self.max_tokens * 100) if self.max_tokens > 0 else 0,
            "oldest_message_time": messages[0]["timestamp"] if messages else None,
            "newest_message_time": messages[-1]["timestamp"] if messages else None
        }

    def import_history(self, messages: List[Dict[str, str]]):
        self.clear_history()
        for msg in messages:
            self.add_message(
                role=msg["role"],
                content=msg["content"],
                metadata=msg.get("metadata")
            )
        logger.info(f"Imported {len(messages)} messages into context")

    def export_history(self, include_metadata: bool = True) -> List[Dict[str, Any]]:
        if include_metadata:
            return list(self.conversation_history)
        else:
            return self.get_history(include_metadata=False)


class SessionContextManager:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path
        self.sessions: Dict[str, ContextManager] = {}
        logger.info("Session Context Manager initialized")

    def get_or_create_session(
        self,
        session_id: str,
        max_messages: Optional[int] = None,
        max_tokens: int = 8000
    ) -> ContextManager:
        if session_id not in self.sessions:
            self.sessions[session_id] = ContextManager(
                max_messages=max_messages,
                max_tokens=max_tokens,
                db_path=self.db_path
            )
            logger.info(f"Created new session: {session_id}")
        return self.sessions[session_id]

    def get_session(self, session_id: str) -> Optional[ContextManager]:
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str):
        if session_id in self.sessions:
            del self.sessions[session_id]
            logger.info(f"Deleted session: {session_id}")

    def list_sessions(self) -> List[str]:
        return list(self.sessions.keys())

    def get_all_sessions_stats(self) -> Dict[str, Dict[str, Any]]:
        return {
            session_id: context.get_context_stats()
            for session_id, context in self.sessions.items()
        }


session_manager = SessionContextManager()
